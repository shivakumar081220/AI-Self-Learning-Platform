from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import GeneratedCourse, Learner, Topic, TopicProgress, User
from ..schemas import CurriculumResponse
from ..security import require_user
from ..services.curriculum_service import persist_curriculum
from ..topic_titles import display_topic_title
from ..track_catalog import TRACK_BY_ID


router = APIRouter(prefix="/api/curriculum", tags=["curriculum"])


def _course_topics(course: GeneratedCourse, database: Session) -> list[dict]:
    topics = database.scalars(
        select(Topic).where(Topic.course_id == course.id, Topic.is_active.is_(True))
    ).all()
    topic_by_id = {topic.id: topic for topic in topics}
    progress = {
        item.topic_id: item
        for item in database.scalars(
            select(TopicProgress).where(
                TopicProgress.learner_id == course.learner_id,
                TopicProgress.topic_id.in_(topic_by_id),
            )
        ).all()
    } if topic_by_id else {}
    modules = course.modules_json or []
    module_by_topic = {
        topic_id: module
        for module in modules
        for topic_id in module.get("topic_ids", [])
    }
    topic_ids = [
        topic_id
        for module in modules
        for topic_id in module.get("topic_ids", [])
        if topic_id in topic_by_id
    ]
    topic_ids.extend(
        topic.id for topic in topics if topic.id not in module_by_topic
    )
    return [
        {
            "topic_id": topic.id,
            "title": display_topic_title(topic.title),
            "description": topic.description,
            "difficulty": topic.difficulty,
            "concepts": topic.concept_tags,
            "learning_objectives": topic.learning_objectives_json or [],
            "prerequisites": [
                display_topic_title(edge.prerequisite.title)
                for edge in topic.prerequisites
                if edge.prerequisite
            ],
            "estimated_minutes": topic.estimated_minutes,
            "module_id": module_by_topic.get(topic.id, {}).get("module_id"),
            "module_title": module_by_topic.get(topic.id, {}).get("title"),
            "status": progress[topic.id].status if topic.id in progress else "pending",
        }
        for topic_id in topic_ids
        if (topic := topic_by_id.get(topic_id)) is not None
    ]


def _course_modules(course: GeneratedCourse, database: Session) -> list[dict]:
    topic_items = _course_topics(course, database)
    topic_by_id = {item["topic_id"]: item for item in topic_items}
    modules = course.modules_json or []
    if not modules:
        modules = [
            {
                "module_id": f"legacy-{topic['topic_id']}",
                "order": index + 1,
                "title": topic["title"],
                "description": topic["description"],
                "learning_objectives": topic["learning_objectives"],
                "difficulty": topic["difficulty"],
                "estimated_minutes": topic["estimated_minutes"],
                "practical_exercises": [],
                "assessment_objectives": topic["learning_objectives"][:3],
                "skills_to_revise": [],
                "skills_to_learn": topic["concepts"],
                "prerequisites": [],
                "topic_ids": [topic["topic_id"]],
            }
            for index, topic in enumerate(topic_items)
        ]
    module_titles = {
        module["module_id"]: module["title"]
        for module in modules
    }
    result = []
    for module in modules:
        topics = [
            topic_by_id[topic_id]
            for topic_id in module.get("topic_ids", [])
            if topic_id in topic_by_id
        ]
        completed_count = sum(topic["status"] == "completed" for topic in topics)
        result.append(
            {
                "module_id": module["module_id"],
                "order": module.get("order", len(result) + 1),
                "title": module["title"],
                "description": module["description"],
                "learning_objectives": module.get("learning_objectives", []),
                "difficulty": module.get("difficulty", course.level),
                "estimated_minutes": module.get("estimated_minutes"),
                "practical_exercises": module.get("practical_exercises", []),
                "assessment_objectives": module.get("assessment_objectives", []),
                "skills_to_revise": module.get("skills_to_revise", []),
                "skills_to_learn": module.get("skills_to_learn", []),
                "prerequisites": [
                    module_titles[item]
                    for item in module.get("prerequisites", [])
                    if item in module_titles
                ],
                "topics": topics,
                "completed_topics": completed_count,
                "total_topics": len(topics),
                "status": (
                    "completed" if topics and completed_count == len(topics)
                    else "in_progress" if any(topic["status"] != "pending" for topic in topics)
                    else "pending"
                ),
            }
        )
    return result


def _response(
    course: GeneratedCourse, database: Session, source: str, learner: Learner
) -> CurriculumResponse:
    current_topics = _course_topics(course, database)
    courses = database.scalars(
        select(GeneratedCourse)
        .where(GeneratedCourse.learner_id == learner.id)
        .order_by(GeneratedCourse.updated_at.desc(), GeneratedCourse.id.desc())
    ).all()
    course_list = [
        {
            "course_id": item.id,
            "track_id": item.track_id,
            "track_name": TRACK_BY_ID.get(item.track_id, TRACK_BY_ID["generative_ai"]).name,
            "course_title": item.title,
            "description": item.description,
            "goal": item.goal,
            "target_outcome": item.target_outcome,
            "level": item.level,
            "estimated_duration": item.estimated_duration,
            "learning_objectives": item.learning_objectives_json or [],
            "generation_source": item.generation_source,
            "modules": _course_modules(item, database),
            "topics": _course_topics(item, database),
            "is_current": item.id == course.id,
        }
        for item in courses
    ]
    return CurriculumResponse(
        course_id=course.id,
        track_id=course.track_id,
        track_name=TRACK_BY_ID.get(course.track_id, TRACK_BY_ID["generative_ai"]).name,
        course_title=course.title,
        description=course.description,
        goal=course.goal,
        level=course.level,
        estimated_duration=course.estimated_duration,
        learning_objectives=course.learning_objectives_json or [],
        modules=_course_modules(course, database),
        topics=current_topics,
        track_history=course.track_history_json or [],
        courses=course_list,
        source=source,
        generation_source=course.generation_source,
    )


@router.post("/generate", response_model=CurriculumResponse)
def generate_my_curriculum(user: User = Depends(require_user), database: Session = Depends(get_db)) -> CurriculumResponse:
    learner = database.scalar(select(Learner).where(Learner.user_id == user.id))
    if not learner:
        raise HTTPException(status_code=400, detail="Complete your learner profile before generating a curriculum.")
    course, source = persist_curriculum(database, learner, user.id)
    return _response(course, database, source, learner)


@router.get("/current", response_model=CurriculumResponse)
def get_my_curriculum(user: User = Depends(require_user), database: Session = Depends(get_db)) -> CurriculumResponse:
    learner = database.scalar(select(Learner).where(Learner.user_id == user.id))
    if not learner:
        raise HTTPException(status_code=404, detail="Learner profile not found.")
    course = database.scalar(
        select(GeneratedCourse).where(
            GeneratedCourse.learner_id == learner.id,
            GeneratedCourse.track_id == learner.track,
            GeneratedCourse.goal == learner.goal_text,
            GeneratedCourse.level == learner.experience_level,
            GeneratedCourse.target_outcome == learner.target_outcome,
        )
    )
    if not course:
        course = database.scalar(
            select(GeneratedCourse)
            .where(GeneratedCourse.learner_id == learner.id)
            .order_by(GeneratedCourse.updated_at.desc(), GeneratedCourse.id.desc())
        )
    if not course:
        raise HTTPException(status_code=404, detail="No curriculum has been generated yet.")
    return _response(course, database, "persisted", learner)