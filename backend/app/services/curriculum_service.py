from uuid import uuid4

from pydantic import ValidationError
from sqlalchemy import and_, func, or_, select, update
from sqlalchemy.orm import Session

from ..config import settings
from ..models import Assessment, GeneratedCourse, Learner, SkillScore, Topic, TopicPrerequisite, TopicProgress, Weakness
from ..schemas import CurriculumTopic, GeneratedCurriculum
from ..track_catalog import TRACK_BY_ID
from .ai_provider import request_structured_json


def _fallback_curriculum(learner: Learner) -> GeneratedCurriculum:
    goal = learner.goal_text
    track = TRACK_BY_ID.get(learner.track, TRACK_BY_ID["generative_ai"])
    titles = [
        f"{track.name} Foundations",
        f"Core Concepts in {track.name}",
        f"Practical {track.name} Workflows",
        f"Evaluation for {track.name}",
        f"Build: {goal[:100]}",
    ]
    topics = []
    for index, title in enumerate(titles):
        concept = track.id if index < 2 else title.lower().replace(" ", "_")
        topics.append(
            CurriculumTopic(
                title=title,
                description=f"A focused {learner.experience_level}-level lesson in {title.lower()} for the goal: {goal}.",
                learning_objectives=[f"Explain the core ideas in {title.lower()}", "Apply the idea in a Generative AI workflow"],
                difficulty=("beginner" if index < 2 else learner.experience_level),
                concepts=[concept],
                prerequisites=[titles[index - 1]] if index else [],
                estimated_minutes=30 + index * 10,
            )
        )
    return GeneratedCurriculum(
        course_title=f"{goal}: a practical learning path",
        description=f"A fallback {track.name} curriculum for {learner.experience_level} learners pursuing {goal}.",
        track_id=track.id,
        goal=goal,
        level=learner.experience_level,
        estimated_duration=f"{len(topics) * 40} minutes",
        topics=topics,
    )


def _openrouter_curriculum(learner: Learner, database: Session) -> GeneratedCurriculum:
    skills = database.scalars(
        select(SkillScore).where(SkillScore.learner_id == learner.id)
    ).all()
    weaknesses = database.scalars(
        select(Weakness).where(
            Weakness.learner_id == learner.id,
            Weakness.status == "open",
        )
    ).all()
    assessments = database.scalars(
        select(Assessment)
        .where(
            Assessment.learner_id == learner.id,
            Assessment.completed_at.is_not(None),
        )
        .order_by(Assessment.completed_at.desc())
        .limit(5)
    ).all()
    completed_topics = [
        topic.title
        for progress in database.scalars(
            select(TopicProgress).where(
                TopicProgress.learner_id == learner.id,
                TopicProgress.status == "completed",
            )
        ).all()
        if (topic := database.get(Topic, progress.topic_id)) is not None
    ]
    existing_course = database.scalar(
        select(GeneratedCourse).where(GeneratedCourse.learner_id == learner.id)
    )
    topic_catalog = database.scalars(
        select(Topic).where(
            or_(
                Topic.owner_user_id.is_(None),
                and_(
                    Topic.owner_user_id == learner.user_id,
                    Topic.track_id == learner.track,
                    Topic.is_active.is_(True),
                ),
            )
        )
    ).all()
    topic_ids = [topic.id for topic in topic_catalog]
    prerequisite_edges = database.scalars(
        select(TopicPrerequisite).where(TopicPrerequisite.topic_id.in_(topic_ids))
    ).all()
    prerequisites_by_topic: dict[str, list[str]] = {}
    for edge in prerequisite_edges:
        prerequisites_by_topic.setdefault(edge.topic_id, []).append(edge.prerequisite_id)
    context = {
        "learner": {
            "goal": learner.goal_text,
            "experience_level": learner.experience_level,
            "track": learner.track,
            "track_name": TRACK_BY_ID.get(learner.track, TRACK_BY_ID["generative_ai"]).name,
            "track_prerequisites": TRACK_BY_ID.get(learner.track, TRACK_BY_ID["generative_ai"]).prerequisite_tracks,
            "completed_topics": completed_topics,
            "previous_track": existing_course.track_id if existing_course else None,
            "track_history": existing_course.track_history_json if existing_course else [],
            "target_outcome": learner.target_outcome,
            "preferred_learning_style": learner.preferred_learning_style,
            "skill_gaps": [
                {"concept": item.concept, "score": item.score}
                for item in sorted(skills, key=lambda item: item.score)[:8]
            ],
            "weak_concepts": [item.concept for item in weaknesses],
            "recent_assessments": [
                {
                    "assessment_type": item.assessment_type,
                    "topic_id": item.topic_id,
                    "score": item.score,
                }
                for item in assessments
            ],
        },
        "topic_catalog": [
            {
                "title": topic.title,
                "concepts": topic.concept_tags,
                "prerequisites": prerequisites_by_topic.get(topic.id, []),
            }
            for topic in topic_catalog
        ],
        "requirements": "Generate 4 to 8 original modules for the selected track, prerequisites by title, and a coherent level-appropriate progression. The track prerequisites are guidance, not mandatory modules when diagnostic skills show mastery. Do not return database IDs.",
        "schema": GeneratedCurriculum.model_json_schema(),
    }
    curriculum = request_structured_json(
        system_prompt=(
            "Generate a personalized AI learning curriculum for exactly the selected track_id and track_name. "
            "Use the learner's goal, target outcome, experience, skill gaps, prerequisite guidance, and recent assessment evidence. "
            "Do not force a prerequisite topic when the diagnostic shows mastery. Respect prerequisite ordering. "
            "Return JSON matching the supplied schema; do not create database IDs."
        ),
        user_payload=context,
        response_model=GeneratedCurriculum,
        temperature=0.4,
        max_tokens=3000,
    )
    if (
        curriculum.goal != learner.goal_text
        or curriculum.level != learner.experience_level
        or curriculum.track_id != learner.track
    ):
        raise ValueError("Curriculum does not match learner context")
    return curriculum


def generate_curriculum(
    learner: Learner, database: Session | None = None
) -> tuple[GeneratedCurriculum, str]:
    if settings.openrouter_api_key:
        try:
            if database is None:
                raise ValueError("A database session is required for personalized curriculum generation")
            return _openrouter_curriculum(learner, database), "openrouter"
        except (Exception, ValidationError):
            pass
    return _fallback_curriculum(learner), "deterministic_fallback"


def persist_curriculum(database: Session, learner: Learner, user_id: int) -> tuple[GeneratedCourse, str]:
    existing = database.scalar(select(GeneratedCourse).where(GeneratedCourse.learner_id == learner.id))
    if (
        existing
        and existing.track_id == learner.track
        and existing.goal == learner.goal_text
        and existing.target_outcome == learner.target_outcome
    ):
        return existing, "persisted"
    curriculum, source = generate_curriculum(learner, database)
    if existing:
        archived_topics = database.scalars(
            select(Topic).where(Topic.course_id == existing.id, Topic.is_active.is_(True))
        ).all()
        existing.track_history_json = [
            *(existing.track_history_json or []),
            {
                "track_id": existing.track_id,
                "course_title": existing.title,
                "goal": existing.goal,
                "target_outcome": existing.target_outcome,
                "generation_source": existing.generation_source,
                "topics": [
                    {
                        "topic_id": topic.id,
                        "title": topic.title,
                        "description": topic.description,
                        "difficulty": topic.difficulty,
                        "concepts": topic.concept_tags,
                    }
                    for topic in archived_topics
                ],
            },
        ]
        database.execute(
            update(Topic)
            .where(Topic.course_id == existing.id, Topic.is_active.is_(True))
            .values(is_active=False)
        )
        course = existing
    else:
        course = GeneratedCourse(
            user_id=user_id,
            learner_id=learner.id,
            title=curriculum.course_title,
            description=curriculum.description,
            goal=curriculum.goal,
            target_outcome=learner.target_outcome,
            level=curriculum.level,
            estimated_duration=curriculum.estimated_duration,
            track_id=curriculum.track_id,
            generation_source=source,
        )
        database.add(course)
        database.flush()
    course.title = curriculum.course_title
    course.description = curriculum.description
    course.goal = curriculum.goal
    course.target_outcome = learner.target_outcome
    course.level = curriculum.level
    course.estimated_duration = curriculum.estimated_duration
    course.track_id = curriculum.track_id
    course.generation_source = source
    database.flush()
    generation_index = (database.scalar(select(func.count(Topic.id)).where(Topic.course_id == course.id)) or 0) + 1
    topic_ids: dict[str, str] = {}
    for topic in curriculum.topics:
        topic_id = f"generated-{uuid4().hex}"
        topic_ids[topic.title] = topic_id
        database.add(
            Topic(
                id=topic_id,
                title=f"{topic.title} · {course.id}-{generation_index}",
                description=topic.description,
                difficulty=topic.difficulty,
                concept_tags=topic.concepts,
                goal_relevance={"generated": 1.0},
                content_source="AI-generated learner curriculum",
                track_id=curriculum.track_id,
                is_active=True,
                owner_user_id=user_id,
                course_id=course.id,
            )
        )
    database.flush()
    for topic in curriculum.topics:
        for prerequisite_title in topic.prerequisites:
            database.add(
                TopicPrerequisite(
                    topic_id=topic_ids[topic.title],
                    prerequisite_id=topic_ids[prerequisite_title],
                )
            )
    database.commit()
    database.refresh(course)
    return course, source