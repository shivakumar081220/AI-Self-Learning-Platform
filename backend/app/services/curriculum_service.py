import logging
from uuid import uuid4

from pydantic import ValidationError
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..config import settings
from ..models import Assessment, GeneratedCourse, Learner, SkillScore, Topic, TopicPrerequisite, TopicProgress, Weakness
from ..schemas import CurriculumTopic, GeneratedCurriculum
from ..topic_titles import display_topic_title
from ..track_catalog import TRACK_BY_ID
from .ai_provider import AIProviderError, log_ai_fallback, request_structured_json


logger = logging.getLogger(__name__)

_FALLBACK_TRACK_CONCEPTS = {
    "python_for_ai": [
        ("python_syntax", "variables_and_types"),
        ("functions", "control_flow"),
        ("data_structures", "data_cleaning"),
        ("numerical_computing", "feature_preparation"),
        ("reproducible_scripts", "dataset_pipelines"),
    ],
    "machine_learning": [
        ("training_data", "feature_engineering"),
        ("supervised_learning", "classification"),
        ("loss_functions", "model_optimization"),
        ("validation_sets", "overfitting"),
        ("evaluation_metrics", "error_analysis"),
    ],
    "deep_learning": [
        ("tensors", "neural_network_layers"),
        ("forward_pass", "activation_functions"),
        ("backpropagation", "gradient_descent"),
        ("regularization", "generalization"),
        ("training_loops", "model_evaluation"),
    ],
    "nlp": [
        ("text_normalization", "tokenization"),
        ("bag_of_words", "tf_idf"),
        ("text_classification", "sequence_labeling"),
        ("word_embeddings", "language_models"),
        ("precision_recall", "nlp_evaluation"),
    ],
    "generative_ai": [
        ("prompt_design", "context"),
        ("constraints", "structured_outputs"),
        ("generation_parameters", "sampling"),
        ("grounding", "guardrails"),
        ("quality_metrics", "safety_evaluation"),
    ],
    "llms": [
        ("tokens", "context_windows"),
        ("transformers", "attention"),
        ("inference", "decoding"),
        ("structured_generation", "tool_calling"),
        ("latency", "model_evaluation"),
    ],
    "rag": [
        ("document_chunking", "metadata"),
        ("embeddings", "vector_search"),
        ("retrieval_ranking", "hybrid_search"),
        ("grounded_generation", "citations"),
        ("retrieval_metrics", "answer_faithfulness"),
    ],
    "ai_agents": [
        ("tool_schemas", "argument_validation"),
        ("task_decomposition", "planning"),
        ("state_management", "orchestration"),
        ("permissions", "guardrails"),
        ("trajectory_evaluation", "agent_reliability"),
    ],
}


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
        concepts = _FALLBACK_TRACK_CONCEPTS[track.id][index]
        topics.append(
            CurriculumTopic(
                title=title,
                description=f"A focused {learner.experience_level}-level lesson in {title.lower()} for the goal: {goal}.",
                learning_objectives=[
                    f"Explain {concepts[0].replace('_', ' ')} and {concepts[1].replace('_', ' ')}",
                    f"Apply these concepts to {track.name} tasks related to the learner's goal",
                ],
                difficulty=("beginner" if index < 2 else learner.experience_level),
                concepts=list(concepts),
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
        learning_objectives=[
            track.learning_objective,
            "Apply the concepts to the learner's stated goal",
            f"Evaluate {track.name} workflows using relevant quality checks",
        ],
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
    global_topics = database.scalars(
        select(Topic).where(Topic.owner_user_id.is_(None))
    ).all()
    relevant_global_topics = [
        topic
        for topic in global_topics
        if topic.goal_relevance.get(learner.track, 0) > 0
    ]
    if not relevant_global_topics:
        relevant_global_topics = global_topics
    owned_topics = database.scalars(
        select(Topic).where(
            Topic.owner_user_id == learner.user_id,
            Topic.track_id == learner.track,
            Topic.is_active.is_(True),
        )
    ).all()
    topic_catalog = [
        *relevant_global_topics,
        *owned_topics,
    ]
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
    }
    curriculum = request_structured_json(
        operation="curriculum_generation",
        system_prompt=(
            "Generate a personalized AI learning curriculum for exactly the selected track_id and track_name. "
            "Use the learner's goal, target outcome, experience, skill gaps, prerequisite guidance, and recent assessment evidence. "
            "Return course learning objectives as well as ordered topics. Each topic must include its objectives, "
            "prerequisites by exact generated topic title, difficulty, and estimated_minutes. "
            "Do not force a prerequisite topic when the diagnostic shows mastery. Respect prerequisite ordering. "
            "Return only the exact schema fields with their declared JSON types; include all required properties, "
            "do not add unsupported properties, and do not create database IDs."
        ),
        user_payload=context,
        response_model=GeneratedCurriculum,
        temperature=0.4,
        max_tokens=2400,
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
        except (AIProviderError, ValidationError, ValueError) as error:
            logger.warning(
                "AI operation used deterministic fallback; operation=curriculum_generation reason=%s",
                type(error).__name__,
            )
    log_ai_fallback(
        "curriculum_generation",
        "provider_not_configured" if not settings.openrouter_api_key else "generation_failed",
    )
    return _fallback_curriculum(learner), "deterministic_fallback"


def persist_curriculum(database: Session, learner: Learner, user_id: int) -> tuple[GeneratedCourse, str]:
    existing = database.scalar(
        select(GeneratedCourse).where(
            GeneratedCourse.learner_id == learner.id,
            GeneratedCourse.track_id == learner.track,
            GeneratedCourse.goal == learner.goal_text,
            GeneratedCourse.level == learner.experience_level,
            GeneratedCourse.target_outcome == learner.target_outcome,
        )
    )
    if existing:
        return existing, "persisted"
    curriculum, source = generate_curriculum(learner, database)
    course = GeneratedCourse(
        user_id=user_id,
        learner_id=learner.id,
        title=curriculum.course_title,
        description=curriculum.description,
        goal=curriculum.goal,
        target_outcome=learner.target_outcome,
        level=curriculum.level,
        estimated_duration=curriculum.estimated_duration,
        learning_objectives_json=curriculum.learning_objectives,
        track_id=curriculum.track_id,
        generation_source=source,
    )
    database.add(course)
    database.flush()
    generation_index = (
        database.scalar(select(func.count(Topic.id)).where(Topic.course_id == course.id)) or 0
    ) + 1
    topic_ids: dict[str, str] = {}
    for topic in curriculum.topics:
        topic_id = f"generated-{uuid4().hex}"
        topic_ids[topic.title] = topic_id
        database.add(
            Topic(
                id=topic_id,
                # Topic titles are globally unique; this internal suffix is removed from responses.
                title=f"{display_topic_title(topic.title)} · {course.id}-{generation_index}",
                description=topic.description,
                difficulty=topic.difficulty,
                concept_tags=topic.concepts,
                learning_objectives_json=topic.learning_objectives,
                estimated_minutes=topic.estimated_minutes,
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