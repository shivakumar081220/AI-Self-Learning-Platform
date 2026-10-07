from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import GeneratedCourse, Learner, Topic, User
from ..schemas import CurriculumResponse
from ..security import require_user
from ..services.curriculum_service import persist_curriculum


router = APIRouter(prefix="/api/curriculum", tags=["curriculum"])


def _response(course: GeneratedCourse, database: Session, source: str) -> CurriculumResponse:
    topics = database.scalars(select(Topic).where(Topic.course_id == course.id)).all()
    return CurriculumResponse(
        course_id=course.id,
        course_title=course.title,
        description=course.description,
        goal=course.goal,
        level=course.level,
        estimated_duration=course.estimated_duration,
        topics=[
            {"topic_id": topic.id, "title": topic.title, "description": topic.description, "difficulty": topic.difficulty, "concepts": topic.concept_tags}
            for topic in topics
        ],
        source=source,
    )


@router.post("/generate", response_model=CurriculumResponse)
def generate_my_curriculum(user: User = Depends(require_user), database: Session = Depends(get_db)) -> CurriculumResponse:
    learner = database.scalar(select(Learner).where(Learner.user_id == user.id))
    if not learner:
        raise HTTPException(status_code=400, detail="Complete your learner profile before generating a curriculum.")
    course, source = persist_curriculum(database, learner, user.id)
    return _response(course, database, source)


@router.get("/current", response_model=CurriculumResponse)
def get_my_curriculum(user: User = Depends(require_user), database: Session = Depends(get_db)) -> CurriculumResponse:
    course = database.scalar(select(GeneratedCourse).where(GeneratedCourse.user_id == user.id))
    if not course:
        raise HTTPException(status_code=404, detail="No curriculum has been generated yet.")
    return _response(course, database, "persisted")