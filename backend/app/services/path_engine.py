from collections import defaultdict
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..goal_catalog import GOAL_BY_KEY
from ..models import Assessment, Learner, LearningPath, SkillScore, Topic, TopicPrerequisite, TopicProgress
from ..track_catalog import TRACK_BY_ID


MASTERY_THRESHOLD = 0.80
WEAK_THRESHOLD = 0.50
FOCUSED_PRACTICE_THRESHOLD = 0.60


def infer_goal_key(goal_text: str) -> str:
    normalized_goal = goal_text.lower()
    if "rag" in normalized_goal or "retriev" in normalized_goal or "ground" in normalized_goal:
        return "rag"
    if "agent" in normalized_goal or "tool use" in normalized_goal or "tool-use" in normalized_goal:
        return "ai_agents"
    if "prompt" in normalized_goal:
        return "prompt_engineering"
    if goal_text in {goal.label for goal in GOAL_BY_KEY.values()}:
        return next(key for key, goal in GOAL_BY_KEY.items() if goal.label == goal_text)
    return "llm_apps"


def _learner_track_key(learner: Learner) -> str:
    if learner.track in TRACK_BY_ID and learner.track != "generative_ai":
        return learner.track
    return infer_goal_key(learner.goal_text)


def _topic_relevance(topic: Topic, goal_key: str) -> float:
    return float(topic.goal_relevance.get(goal_key, topic.goal_relevance.get("generated", 0.0)))


def validate_topic_graph(
    topics: list[Topic], relationships: list[TopicPrerequisite]
) -> dict[str, Topic]:
    topic_by_id = {topic.id: topic for topic in topics}
    for relationship in relationships:
        if relationship.topic_id not in topic_by_id:
            raise ValueError(f"Unknown topic in prerequisite graph: {relationship.topic_id}")
        if relationship.prerequisite_id not in topic_by_id:
            raise ValueError(
                f"Unknown prerequisite in topic graph: {relationship.prerequisite_id}"
            )
    return topic_by_id


def _topic_scores(skills: dict[str, SkillScore], topic: Topic) -> dict[str, Any]:
    tagged_scores = [skills[tag].score for tag in topic.concept_tags if tag in skills]
    weak_concepts = [
        tag for tag in topic.concept_tags if tag in skills and skills[tag].score < WEAK_THRESHOLD
    ]
    developing_concepts = [
        tag
        for tag in topic.concept_tags
        if tag in skills and WEAK_THRESHOLD <= skills[tag].score < MASTERY_THRESHOLD
    ]
    return {
        "score": sum(tagged_scores) / len(tagged_scores) if tagged_scores else 0.0,
        "weak_concepts": weak_concepts,
        "developing_concepts": developing_concepts,
    }


def _mastered_topic_ids(
    topics: list[Topic], progress: dict[str, TopicProgress], skills: dict[str, SkillScore]
) -> set[str]:
    mastered = {
        topic_id
        for topic_id, record in progress.items()
        if record.status == "completed" or record.mastery_score >= MASTERY_THRESHOLD
    }
    for topic in topics:
        topic_metrics = _topic_scores(skills, topic)
        if topic_metrics["score"] >= MASTERY_THRESHOLD and topic_metrics["score"] > 0:
            mastered.add(topic.id)
    return mastered


def _assessment_scores(assessments: list[Assessment]) -> dict[str, float]:
    recent_scores: dict[str, float] = {}
    for assessment in sorted(assessments, key=lambda item: item.created_at):
        if assessment.topic_id and assessment.score is not None:
            recent_scores[assessment.topic_id] = assessment.score
    return recent_scores


def _required_topics(
    topic_id: str,
    prerequisites: dict[str, list[str]],
    mastered: set[str],
    topic_by_id: dict[str, Topic],
    required: set[str],
) -> None:
    if topic_id in mastered or topic_id in required:
        return
    if topic_id not in topic_by_id:
        raise ValueError(f"Unknown topic selected by path engine: {topic_id}")
    for prerequisite_id in prerequisites.get(topic_id, []):
        _required_topics(prerequisite_id, prerequisites, mastered, topic_by_id, required)
    required.add(topic_id)


def _topic_priority(
    topic: Topic,
    learner: Learner,
    goal_key: str,
    skills: dict[str, SkillScore],
    recent_scores: dict[str, float],
    downstream_pressure: dict[str, int],
) -> tuple[float, ...]:
    metrics = _topic_scores(skills, topic)
    goal_relevance = _topic_relevance(topic, goal_key)
    recent_score = recent_scores.get(topic.id)
    recent_pressure = (
        3.0 if recent_score < FOCUSED_PRACTICE_THRESHOLD else 1.0 if recent_score < MASTERY_THRESHOLD else 0.0
    ) if recent_score is not None else 0.0
    experience_fit = {
        "beginner": {"beginner": 1.0, "intermediate": 0.2, "advanced": 0.0},
        "intermediate": {"beginner": 0.3, "intermediate": 1.0, "advanced": 0.6},
        "advanced": {"beginner": 0.0, "intermediate": 0.7, "advanced": 1.0},
    }[learner.experience_level][topic.difficulty]
    weak_priority = len(metrics["weak_concepts"]) * 5.0
    developing_priority = len(metrics["developing_concepts"]) * 1.5
    pressure = downstream_pressure.get(topic.id, 0) * 0.25
    return (
        weak_priority + recent_pressure,
        goal_relevance,
        pressure + experience_fit,
        developing_priority,
        -len(topic.prerequisites),
    )


def _topic_reason(
    topic: Topic,
    goal_key: str,
    skills: dict[str, SkillScore],
    recent_scores: dict[str, float],
    mastered: set[str],
) -> str:
    metrics = _topic_scores(skills, topic)
    track_name = TRACK_BY_ID.get(goal_key).name if goal_key in TRACK_BY_ID else "Generative AI"
    reasons = [f"It supports your {track_name} track and goal."]
    if metrics["weak_concepts"]:
        reasons.append(
            "It targets weak concepts: "
            + ", ".join(concept.replace("_", " ") for concept in metrics["weak_concepts"])
            + "."
        )
    if topic.id in recent_scores and recent_scores[topic.id] < FOCUSED_PRACTICE_THRESHOLD:
        reasons.append("Your recent assessment shows this topic needs focused practice.")
    missing_prerequisites = [
        prerequisite_id
        for prerequisite_id in (item.prerequisite_id for item in topic.prerequisites)
        if prerequisite_id not in mastered
    ]
    if missing_prerequisites:
        reasons.append("It is included in prerequisite order before a dependent topic.")
    if not metrics["weak_concepts"] and not missing_prerequisites:
        reasons.append("Its prerequisites are ready, so it is a suitable next progression.")
    return " ".join(reasons)


def generate_path_plan(database: Session, learner: Learner) -> dict[str, Any]:
    if learner.user_id is not None:
        topics = database.scalars(
            select(Topic).where(
                Topic.owner_user_id == learner.user_id,
                Topic.is_active.is_(True),
            )
        ).all()
        topic_ids = {topic.id for topic in topics}
        relationships = database.scalars(
            select(TopicPrerequisite).where(
                TopicPrerequisite.topic_id.in_(topic_ids),
                TopicPrerequisite.prerequisite_id.in_(topic_ids),
            )
        ).all()
    else:
        topics = database.scalars(
            select(Topic).where(Topic.owner_user_id.is_(None), Topic.is_active.is_(True))
        ).all()
        relationships = database.scalars(select(TopicPrerequisite)).all()
    topic_by_id = validate_topic_graph(topics, relationships)
    prerequisites: dict[str, list[str]] = defaultdict(list)
    for relationship in relationships:
        prerequisites[relationship.topic_id].append(relationship.prerequisite_id)

    skills = {
        skill.concept: skill
        for skill in database.scalars(select(SkillScore).where(SkillScore.learner_id == learner.id)).all()
    }
    progress = {
        item.topic_id: item
        for item in database.scalars(
            select(TopicProgress).where(TopicProgress.learner_id == learner.id)
        ).all()
    }
    assessments = database.scalars(
        select(Assessment).where(Assessment.learner_id == learner.id)
    ).all()
    recent_scores = _assessment_scores(assessments)
    mastered = _mastered_topic_ids(topics, progress, skills)
    goal_key = _learner_track_key(learner)

    completed_progress_ids = {
        topic_id for topic_id, record in progress.items() if record.status == "completed"
    }
    target_topics = [topic for topic in topics if topic.id not in mastered]
    required: set[str] = set()
    for topic in target_topics:
        _required_topics(topic.id, prerequisites, mastered, topic_by_id, required)

    downstream_pressure: dict[str, int] = defaultdict(int)
    for topic_id in required:
        for prerequisite_id in prerequisites.get(topic_id, []):
            if prerequisite_id in required:
                downstream_pressure[prerequisite_id] += 1

    ordered_ids: list[str] = []
    remaining = set(required)
    while remaining:
        available = [
            topic_id
            for topic_id in remaining
            if all(
                prerequisite_id in mastered or prerequisite_id in ordered_ids
                for prerequisite_id in prerequisites.get(topic_id, [])
            )
        ]
        if not available:
            raise ValueError("Topic prerequisite graph contains a cycle")
        selected_id = max(
            available,
            key=lambda topic_id: _topic_priority(
                topic_by_id[topic_id],
                learner,
                goal_key,
                skills,
                recent_scores,
                downstream_pressure,
            ),
        )
        ordered_ids.append(selected_id)
        remaining.remove(selected_id)

    topics_json = []
    for topic in sorted(topics, key=lambda item: item.id):
        if topic.id in completed_progress_ids:
            topics_json.append(
                {
                    "topic_id": topic.id,
                    "title": topic.title,
                    "difficulty": topic.difficulty,
                    "status": "completed",
                    "prerequisites": prerequisites.get(topic.id, []),
                    "reason": "Already completed in your learning history, so it will not be recommended again.",
                    "relevance_score": _topic_relevance(topic, goal_key),
                }
            )
    for topic_id in ordered_ids:
        topic = topic_by_id[topic_id]
        relevance = _topic_relevance(topic, goal_key)
        progress_record = progress.get(topic.id)
        topics_json.append(
            {
                "topic_id": topic.id,
                "title": topic.title,
                "difficulty": topic.difficulty,
                "status": "remediation" if progress_record and progress_record.status == "remediation" else "pending",
                "prerequisites": prerequisites.get(topic.id, []),
                "reason": _topic_reason(topic, goal_key, skills, recent_scores, mastered),
                "relevance_score": relevance,
            }
        )

    return {
        "goal": learner.goal_text,
        "topics": topics_json,
        "overall_rationale": (
            f"This {TRACK_BY_ID.get(goal_key).name if goal_key in TRACK_BY_ID else 'Generative AI'} path is ordered for your "
            f"{learner.experience_level} experience level and selected goal. It places unmet prerequisites before dependent topics, prioritizes "
            "weak concepts and recent assessment gaps, and skips mastered topics."
        ),
    }


def validate_path_payload(path_payload: dict[str, Any], topic_by_id: dict[str, Topic]) -> None:
    for item in path_payload.get("topics", []):
        if item["topic_id"] not in topic_by_id:
            raise ValueError(f"Unknown topic in stored learning path: {item['topic_id']}")
        for prerequisite_id in item.get("prerequisites", []):
            if prerequisite_id not in topic_by_id:
                raise ValueError(f"Unknown prerequisite in stored learning path: {prerequisite_id}")


def path_response(path: LearningPath, topic_by_id: dict[str, Topic]) -> dict[str, Any]:
    validate_path_payload({"topics": path.path_json}, topic_by_id)
    topic_items = path.path_json
    current_item = topic_items[path.current_index] if path.current_index < len(topic_items) else None
    return {
        "path_id": path.id,
        "learner_id": path.learner_id,
        "goal": path.goal,
        "current_index": path.current_index,
        "current_topic_id": current_item["topic_id"] if current_item else None,
        "current_topic_title": current_item["title"] if current_item else None,
        "overall_rationale": getattr(path, "overall_rationale", None) or "",
        "topics": topic_items,
    }
