import json
from uuid import uuid4

from openai import OpenAI
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import settings
from ..models import GeneratedCourse, Learner, Topic, TopicPrerequisite
from ..schemas import CurriculumTopic, GeneratedCurriculum


def _fallback_curriculum(learner: Learner) -> GeneratedCurriculum:
    goal = learner.goal_text
    normalized = goal.lower()
    if "agent" in normalized:
        titles = ["LLM Foundations", "Tool Use", "Agent Planning", "Agent Evaluation", "Production Agents"]
    elif "rag" in normalized or "retriev" in normalized:
        titles = ["LLM Foundations", "Embeddings", "Vector Search", "Retrieval", "RAG Evaluation"]
    elif "prompt" in normalized:
        titles = ["LLM Foundations", "Prompt Structure", "Few-Shot Examples", "Structured Outputs", "Prompt Evaluation"]
    else:
        titles = ["AI Foundations", "Language Models", "Prompt Engineering", "LLM Applications", "Evaluation and Safety"]
    topics = []
    for index, title in enumerate(titles):
        topics.append(
            CurriculumTopic(
                title=title,
                description=f"A focused {learner.experience_level}-level lesson in {title.lower()} for the goal: {goal}.",
                learning_objectives=[f"Explain the core ideas in {title.lower()}", "Apply the idea in a Generative AI workflow"],
                difficulty=("beginner" if index < 2 else learner.experience_level),
                concepts=[title.lower().replace(" ", "_")],
                prerequisites=[titles[index - 1]] if index else [],
                estimated_minutes=30 + index * 10,
            )
        )
    return GeneratedCurriculum(
        course_title=f"{goal}: a practical learning path",
        description=f"A personalized curriculum for {learner.experience_level} learners pursuing {goal}.",
        goal=goal,
        level=learner.experience_level,
        estimated_duration=f"{len(topics) * 40} minutes",
        topics=topics,
    )


def _openrouter_curriculum(learner: Learner) -> GeneratedCurriculum:
    prompt = {
        "goal": learner.goal_text,
        "experience_level": learner.experience_level,
        "track": "Artificial Intelligence",
        "requirements": "Generate 4 to 8 original topics, prerequisites by title, and a coherent beginner/intermediate/advanced progression.",
    }
    client = OpenAI(api_key=settings.openrouter_api_key, base_url=settings.openrouter_base_url)
    response = client.chat.completions.create(
        model=settings.openrouter_model,
        temperature=0.4,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": "Generate a personalized AI learning curriculum. Return only JSON matching the supplied curriculum schema. Do not return database IDs."},
            {"role": "user", "content": json.dumps({"schema": GeneratedCurriculum.model_json_schema(), "learner": prompt})},
        ],
    )
    content = response.choices[0].message.content
    if not content:
        raise ValueError("OpenRouter returned empty curriculum")
    curriculum = GeneratedCurriculum.model_validate_json(content)
    if curriculum.goal != learner.goal_text or curriculum.level != learner.experience_level:
        raise ValueError("Curriculum does not match learner context")
    return curriculum


def generate_curriculum(learner: Learner) -> tuple[GeneratedCurriculum, str]:
    if settings.openrouter_api_key:
        try:
            return _openrouter_curriculum(learner), "openrouter"
        except (Exception, ValidationError):
            pass
    return _fallback_curriculum(learner), "deterministic_fallback"


def persist_curriculum(database: Session, learner: Learner, user_id: int) -> tuple[GeneratedCourse, str]:
    existing = database.scalar(select(GeneratedCourse).where(GeneratedCourse.learner_id == learner.id))
    if existing:
        return existing, "persisted"
    curriculum, source = generate_curriculum(learner)
    course = GeneratedCourse(
        user_id=user_id,
        learner_id=learner.id,
        title=curriculum.course_title,
        description=curriculum.description,
        goal=curriculum.goal,
        level=curriculum.level,
        estimated_duration=curriculum.estimated_duration,
    )
    database.add(course)
    database.flush()
    topic_ids: dict[str, str] = {}
    for topic in curriculum.topics:
        topic_id = f"generated-{uuid4().hex}"
        topic_ids[topic.title] = topic_id
        database.add(
            Topic(
                id=topic_id,
                title=f"{topic.title} · {course.id}",
                description=topic.description,
                difficulty=topic.difficulty,
                concept_tags=topic.concepts,
                goal_relevance={"generated": 1.0},
                content_source="AI-generated learner curriculum",
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