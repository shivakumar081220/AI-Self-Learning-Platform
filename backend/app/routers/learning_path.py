from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Learner, LearningPath, Topic, TopicProgress
from ..schemas import LearningPathResponse
from ..services.path_engine import generate_path_plan, path_response, validate_path_payload
from ..models import User
from ..security import ensure_learner_access, get_optional_user


router = APIRouter(prefix="/api/learners/{learner_id}/learning-path", tags=["learning-path"])


def _topic_catalog(database: Session) -> dict[str, Topic]:
    return {
        topic.id: topic
        for topic in database.scalars(select(Topic).where(Topic.is_active.is_(True))).all()
    }


def _serialize_path(path: LearningPath, database: Session) -> LearningPathResponse:
    topic_by_id = _topic_catalog(database)
    payload = path_response(path, topic_by_id)
    progress = {
        item.topic_id: item
        for item in database.scalars(
            select(TopicProgress).where(TopicProgress.learner_id == path.learner_id)
        ).all()
    }
    topics = payload["topics"]
    for index, topic in enumerate(topics):
        record = progress.get(topic["topic_id"])
        if record and (record.status == "completed" or record.mastery_score >= 0.8):
            topic["status"] = "completed"
        elif record and record.status == "remediation":
            topic["status"] = "remediation"
        else:
            topic["status"] = "pending"
        if index == path.current_index and topic["status"] != "completed":
            topic["status"] = "current"
    payload["topics"] = topics
    return LearningPathResponse.model_validate(payload)


def _persist_path(
    learner_id: int, database: Session, preserve_current: bool
) -> LearningPathResponse:
    learner = database.get(Learner, learner_id)
    if not learner:
        raise HTTPException(status_code=404, detail="Learner not found")

    previous_path = database.scalar(
        select(LearningPath)
        .where(LearningPath.learner_id == learner_id)
        .order_by(LearningPath.created_at.desc())
    )
    plan = generate_path_plan(database, learner)
    topic_by_id = _topic_catalog(database)
    validate_path_payload(plan, topic_by_id)

    current_topic_id = None
    if preserve_current and previous_path and previous_path.current_index < len(previous_path.path_json):
        current_topic_id = previous_path.path_json[previous_path.current_index]["topic_id"]
    if current_topic_id not in {item["topic_id"] for item in plan["topics"]}:
        current_topic_id = next(
            (
                item["topic_id"]
                for item in plan["topics"]
                if item["status"] != "completed"
            ),
            None,
        )
    current_index = next(
        (
            index
            for index, item in enumerate(plan["topics"])
            if item["topic_id"] == current_topic_id
        ),
        len(plan["topics"]),
    )

    path = LearningPath(
        learner_id=learner_id,
        goal=plan["goal"],
        path_json=plan["topics"],
        overall_rationale=plan["overall_rationale"],
        current_index=current_index,
    )
    database.add(path)
    database.commit()
    database.refresh(path)
    return _serialize_path(path, database)


@router.get("", response_model=LearningPathResponse)
def get_learning_path(
    learner_id: int, database: Session = Depends(get_db), user: User | None = Depends(get_optional_user)
) -> LearningPathResponse:
    learner = database.get(Learner, learner_id)
    if not learner:
        raise HTTPException(status_code=404, detail="Learner not found")
    ensure_learner_access(learner, user)
    path = database.scalar(
        select(LearningPath)
        .where(LearningPath.learner_id == learner_id)
        .order_by(LearningPath.created_at.desc())
    )
    if path:
        active_topic_ids = set(_topic_catalog(database))
        if all(item.get("topic_id") in active_topic_ids for item in path.path_json):
            return _serialize_path(path, database)
    return _persist_path(learner_id, database, False)


@router.post("/generate", response_model=LearningPathResponse)
def generate_learning_path(
    learner_id: int, database: Session = Depends(get_db), user: User | None = Depends(get_optional_user)
) -> LearningPathResponse:
    learner = database.get(Learner, learner_id)
    if not learner:
        raise HTTPException(status_code=404, detail="Learner not found")
    ensure_learner_access(learner, user)
    return _persist_path(learner_id, database, False)


@router.post("/regenerate", response_model=LearningPathResponse)
def regenerate_learning_path(
    learner_id: int, database: Session = Depends(get_db), user: User | None = Depends(get_optional_user)
) -> LearningPathResponse:
    learner = database.get(Learner, learner_id)
    if not learner:
        raise HTTPException(status_code=404, detail="Learner not found")
    ensure_learner_access(learner, user)
    return _persist_path(learner_id, database, True)
