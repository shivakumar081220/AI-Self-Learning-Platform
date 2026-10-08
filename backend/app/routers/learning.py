from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import GeneratedCourse, Learner, LearningPath, Topic, TopicProgress
from ..schemas import CurrentTopicResponse, LearningContentResponse
from ..services.content_service import generate_learning_content
from ..services.path_engine import validate_path_payload
from ..models import User
from ..security import ensure_learner_access, get_optional_user
from ..topic_titles import display_topic_title


router = APIRouter(prefix="/api/learners/{learner_id}", tags=["learning"])


def _latest_path(
    learner_id: int, database: Session, course_id: int | None = None
) -> LearningPath:
    query = select(LearningPath).where(LearningPath.learner_id == learner_id)
    if course_id is not None:
        query = query.where(LearningPath.course_id == course_id)
    path = database.scalar(query.order_by(LearningPath.created_at.desc()))
    if not path:
        raise HTTPException(status_code=404, detail="Learning path not found")
    return path


def _path_for_topic(learner_id: int, topic_id: str, database: Session) -> LearningPath:
    topic = database.get(Topic, topic_id)
    if not topic:
        raise HTTPException(status_code=404, detail="Topic not found")
    return _latest_path(learner_id, database, topic.course_id)


def _path_topic(path: LearningPath, topic_id: str) -> tuple[dict, int]:
    for index, item in enumerate(path.path_json):
        if item.get("topic_id") == topic_id:
            return item, index
    raise HTTPException(status_code=404, detail="Topic is not part of this learner's path")


def _current_item(path: LearningPath) -> tuple[dict, int] | None:
    if path.current_index >= len(path.path_json):
        return None
    return path.path_json[path.current_index], path.current_index


def _progress_record(
    learner_id: int, topic_id: str, database: Session, create: bool = False
) -> TopicProgress | None:
    progress = database.scalar(
        select(TopicProgress).where(
            TopicProgress.learner_id == learner_id,
            TopicProgress.topic_id == topic_id,
        )
    )
    if not progress and create:
        progress = TopicProgress(
            learner_id=learner_id,
            topic_id=topic_id,
            status="in_progress",
            last_activity_at=datetime.utcnow(),
        )
        database.add(progress)
    return progress


def _authorize_topic(
    learner_id: int, topic_id: str, path: LearningPath, database: Session, user: User | None
) -> tuple[Learner, Topic, TopicProgress | None, dict]:
    learner = database.get(Learner, learner_id)
    if not learner:
        raise HTTPException(status_code=404, detail="Learner not found")
    ensure_learner_access(learner, user)
    topic = database.get(Topic, topic_id)
    if not topic:
        raise HTTPException(status_code=404, detail="Topic not found in curated catalog")
    path_item, _ = _path_topic(path, topic_id)
    current = _current_item(path)
    progress = _progress_record(learner_id, topic_id, database)
    is_current = current is not None and current[0].get("topic_id") == topic_id
    is_completed = progress is not None and progress.status == "completed"
    if not is_current and not is_completed:
        raise HTTPException(
            status_code=403,
            detail="Only the current recommended topic or a completed topic can be opened",
        )
    return learner, topic, progress, path_item


@router.get("/learning-path/current", response_model=CurrentTopicResponse)
def get_current_topic(
    learner_id: int,
    course_id: int | None = None,
    database: Session = Depends(get_db),
    user: User | None = Depends(get_optional_user),
) -> CurrentTopicResponse:
    learner = database.get(Learner, learner_id)
    if not learner:
        raise HTTPException(status_code=404, detail="Learner not found")
    ensure_learner_access(learner, user)
    path = _latest_path(learner_id, database, course_id)
    current = _current_item(path)
    if not current:
        raise HTTPException(status_code=404, detail="Learner has completed the current learning path")
    item, index = current
    topic = database.get(Topic, item["topic_id"])
    if not topic:
        raise HTTPException(status_code=500, detail="Stored path references an unavailable topic")
    course = database.get(GeneratedCourse, topic.course_id) if topic.course_id else None
    progress = _progress_record(learner_id, topic.id, database)
    return CurrentTopicResponse(
        learner_id=learner_id,
        topic_id=topic.id,
        title=display_topic_title(topic.title),
        course_id=topic.course_id,
        course_title=course.title if course else None,
        difficulty=topic.difficulty,
        position=index + 1,
        total_topics=len(path.path_json),
        status=progress.status if progress else item.get("status", "pending"),
        prerequisites=item.get("prerequisites", []),
    )


def _content_response(
    learner_id: int, topic: Topic, progress: TopicProgress | None, database: Session
) -> LearningContentResponse:
    learner = database.get(Learner, learner_id)
    content, source = generate_learning_content(topic, learner, database)
    return LearningContentResponse(
        learner_id=learner_id,
        content=content,
        source=source,
        topic_status=progress.status if progress else "in_progress",
    )


@router.get("/topics/{topic_id}/content", response_model=LearningContentResponse)
def get_topic_content(
    learner_id: int, topic_id: str, database: Session = Depends(get_db), user: User | None = Depends(get_optional_user)
) -> LearningContentResponse:
    path = _path_for_topic(learner_id, topic_id, database)
    learner, topic, progress, _ = _authorize_topic(learner_id, topic_id, path, database, user)
    if not progress:
        progress = _progress_record(learner_id, topic_id, database, create=True)
    elif progress.status == "pending":
        progress.status = "in_progress"
        progress.last_activity_at = datetime.utcnow()
    database.commit()
    return _content_response(learner.id, topic, progress, database)


@router.post("/topics/{topic_id}/content/generate", response_model=LearningContentResponse)
def generate_topic_content(
    learner_id: int, topic_id: str, database: Session = Depends(get_db), user: User | None = Depends(get_optional_user)
) -> LearningContentResponse:
    return get_topic_content(learner_id, topic_id, database, user)


@router.post("/topics/{topic_id}/complete", response_model=CurrentTopicResponse)
def complete_topic(
    learner_id: int, topic_id: str, database: Session = Depends(get_db), user: User | None = Depends(get_optional_user)
) -> CurrentTopicResponse:
    path = _path_for_topic(learner_id, topic_id, database)
    learner, topic, progress, path_item = _authorize_topic(learner_id, topic_id, path, database, user)
    progress = progress or _progress_record(learner_id, topic_id, database, create=True)
    progress.status = "completed"
    progress.last_activity_at = datetime.utcnow()
    path_item["status"] = "completed"

    next_index = path.current_index
    while next_index < len(path.path_json) and path.path_json[next_index].get("topic_id") != topic_id:
        next_index += 1
    if next_index < len(path.path_json):
        next_index += 1
    while next_index < len(path.path_json):
        next_progress = _progress_record(learner_id, path.path_json[next_index]["topic_id"], database)
        if not next_progress or next_progress.status != "completed":
            break
        next_index += 1
    path.current_index = next_index
    path.path_json = list(path.path_json)
    database.commit()
    current = _current_item(path)
    if not current:
        course = database.get(GeneratedCourse, topic.course_id) if topic.course_id else None
        return CurrentTopicResponse(
            learner_id=learner.id,
            topic_id=topic.id,
            title=display_topic_title(topic.title),
            course_id=topic.course_id,
            course_title=course.title if course else None,
            difficulty=topic.difficulty,
            position=len(path.path_json),
            total_topics=len(path.path_json),
            status="completed",
            prerequisites=path_item.get("prerequisites", []),
        )
    next_item, current_index = current
    next_topic = database.get(Topic, next_item["topic_id"])
    next_course = (
        database.get(GeneratedCourse, next_topic.course_id) if next_topic.course_id else None
    )
    next_progress = _progress_record(learner_id, next_topic.id, database)
    return CurrentTopicResponse(
        learner_id=learner.id,
        topic_id=next_topic.id,
        title=display_topic_title(next_topic.title),
        course_id=next_topic.course_id,
        course_title=next_course.title if next_course else None,
        difficulty=next_topic.difficulty,
        position=current_index + 1,
        total_topics=len(path.path_json),
        status=next_progress.status if next_progress else "pending",
        prerequisites=next_item.get("prerequisites", []),
    )
