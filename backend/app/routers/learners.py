import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from ..database import get_db
from ..goal_catalog import GOAL_BY_KEY, GOAL_OPTIONS
from ..models import (
    Assessment,
    AssessmentQuestionRecord,
    GeneratedCourse,
    Learner,
    LearningGoal,
    LearningPath,
    Recommendation,
    SkillScore,
    Topic,
    TopicProgress,
    TutorConversation,
    TutorMessage,
    User,
)
from ..schemas import (
    AITrackOption,
    GoalOption,
    LearnerCreate,
    LearnerResponse,
    SkillAnalysisResponse,
    SkillScoreResponse,
    LatestAssessmentSummary,
    LearnerSummaryResponse,
    DashboardActivityItem,
    DashboardAssessmentItem,
    DashboardAssessmentPerformance,
    DashboardSummaryResponse,
    DashboardTopicResponse,
    RecommendationResponse,
    TutorRequest,
    TutorResponse,
    TutorContextResponse,
    TutorConversationCreate,
    TutorConversationResponse,
    TutorConversationSummary,
    TutorMessageCreate,
    TutorMessageResponse,
    TutorMessageSendResponse,
    TutorResponsePayload,
)
from ..topic_titles import display_topic_title
from ..security import ensure_learner_access, get_optional_user, require_user
from ..services.tutor_conversation_service import (
    RECENT_HISTORY_LIMIT,
    build_tutor_context,
    generate_tutor_response,
)
from ..services.tutor_service import module_matches_question
from ..track_catalog import AI_TRACKS, LEGACY_GOAL_TRACK, TRACK_BY_ID, infer_track_id


router = APIRouter(prefix="/api", tags=["learners"])
logger = logging.getLogger(__name__)


def _skill_level(score: float) -> str:
    if score < 0.5:
        return "weak"
    if score < 0.75:
        return "developing"
    return "strong"


def _skill_response(skill: SkillScore) -> SkillScoreResponse:
    return SkillScoreResponse(
        concept=skill.concept,
        score=round(skill.score, 3),
        percentage=round(skill.score * 100),
        level=_skill_level(skill.score),
        evidence_count=skill.evidence_count,
    )


def build_skill_analysis(learner_id: int, skills: list[SkillScore]) -> SkillAnalysisResponse:
    results = sorted((_skill_response(skill) for skill in skills), key=lambda item: item.score)
    total_evidence = sum(skill.evidence_count for skill in skills)
    overall_score = (
        sum(skill.score * skill.evidence_count for skill in skills) / total_evidence
        if total_evidence
        else 0.0
    )

    return SkillAnalysisResponse(
        learner_id=learner_id,
        overall_score=round(overall_score, 3),
        overall_percentage=round(overall_score * 100),
        strong_areas=[item for item in results if item.level == "strong"],
        developing_areas=[item for item in results if item.level == "developing"],
        weak_areas=[item for item in results if item.level == "weak"],
        skills=results,
    )


def _selected_goal(payload: LearnerCreate) -> str:
    if payload.custom_goal:
        return payload.custom_goal
    if payload.goal_key in GOAL_BY_KEY:
        return GOAL_BY_KEY[payload.goal_key].label
    raise HTTPException(status_code=422, detail="Select a learning goal or provide a custom goal")


def _selected_track(payload: LearnerCreate, learner: Learner | None = None) -> str:
    if payload.track_id:
        if payload.track_id not in TRACK_BY_ID:
            raise HTTPException(status_code=422, detail="Unknown AI learning track")
        return payload.track_id
    if payload.goal_key in LEGACY_GOAL_TRACK:
        return LEGACY_GOAL_TRACK[payload.goal_key]
    if learner and learner.track in TRACK_BY_ID:
        return learner.track
    return infer_track_id(payload.custom_goal or "", payload.goal_key)


def _replace_active_goal(learner: Learner, goal_text: str, track_id: str) -> None:
    for goal in learner.goals:
        goal.is_active = False
    learner.goals.append(LearningGoal(title=goal_text, track=track_id, is_active=True))


def _current_course(database: Session, learner: Learner) -> GeneratedCourse | None:
    return database.scalar(
        select(GeneratedCourse).where(
            GeneratedCourse.learner_id == learner.id,
            GeneratedCourse.track_id == learner.track,
            GeneratedCourse.goal == learner.goal_text,
            GeneratedCourse.level == learner.experience_level,
            GeneratedCourse.target_outcome == learner.target_outcome,
        )
    )


@router.get("/goals", response_model=list[GoalOption])
def list_goals() -> list[GoalOption]:
    return GOAL_OPTIONS


@router.get("/tracks", response_model=list[AITrackOption])
def list_ai_tracks() -> list[AITrackOption]:
    return AI_TRACKS


@router.get("/learners/me", response_model=LearnerResponse)
def get_my_learner(user: User = Depends(require_user), database: Session = Depends(get_db)) -> Learner:
    learner = database.scalar(select(Learner).where(Learner.user_id == user.id))
    if not learner:
        raise HTTPException(status_code=404, detail="Complete onboarding to create your learner profile.")
    return learner


@router.put("/learners/me", response_model=LearnerResponse)
def update_my_learner(
    payload: LearnerCreate,
    user: User = Depends(require_user),
    database: Session = Depends(get_db),
) -> Learner:
    learner = database.scalar(select(Learner).where(Learner.user_id == user.id))
    if not learner:
        raise HTTPException(status_code=404, detail="Learner profile not found")
    goal_text = _selected_goal(payload)
    learner.track = _selected_track(payload, learner)
    learner.name = payload.name
    learner.experience_level = payload.experience_level
    learner.goal_text = goal_text
    learner.preferred_learning_style = payload.preferred_learning_style
    learner.target_outcome = payload.target_outcome
    _replace_active_goal(learner, goal_text, learner.track)
    database.commit()
    database.refresh(learner)
    return learner


@router.post("/learners", response_model=LearnerResponse, status_code=status.HTTP_201_CREATED)
def create_learner(
    payload: LearnerCreate,
    database: Session = Depends(get_db),
    user: User | None = Depends(get_optional_user),
) -> Learner:
    selected_goal = _selected_goal(payload)
    selected_track = _selected_track(payload)
    if user:
        existing = database.scalar(select(Learner).where(Learner.user_id == user.id))
        if existing:
            ensure_learner_access(existing, user)
            existing.track = _selected_track(payload, existing)
            existing.name = payload.name
            existing.experience_level = payload.experience_level
            existing.goal_text = selected_goal
            existing.preferred_learning_style = payload.preferred_learning_style
            existing.target_outcome = payload.target_outcome
            _replace_active_goal(existing, selected_goal, existing.track)
            database.commit()
            database.refresh(existing)
            return existing
    learner = Learner(
        user_id=user.id if user else None,
        name=payload.name,
        experience_level=payload.experience_level,
        goal_text=selected_goal,
        track=selected_track,
        preferred_learning_style=payload.preferred_learning_style,
        target_outcome=payload.target_outcome,
    )
    learner.goals.append(
        LearningGoal(
            title=selected_goal,
            track=selected_track,
            is_active=True,
        )
    )
    database.add(learner)
    database.commit()
    database.refresh(learner)
    return learner


@router.get("/learners/{learner_id}", response_model=LearnerResponse)
def get_learner(learner_id: int, database: Session = Depends(get_db), user: User | None = Depends(get_optional_user)) -> Learner:
    learner = database.get(Learner, learner_id)
    if not learner:
        raise HTTPException(status_code=404, detail="Learner not found")
    ensure_learner_access(learner, user)
    return learner


@router.get("/learners/{learner_id}/skills", response_model=SkillAnalysisResponse)
def get_skill_analysis(
    learner_id: int, database: Session = Depends(get_db), user: User | None = Depends(get_optional_user)
) -> SkillAnalysisResponse:
    learner = database.get(Learner, learner_id)
    if not learner:
        raise HTTPException(status_code=404, detail="Learner not found")
    ensure_learner_access(learner, user)
    skills = database.scalars(
        select(SkillScore).where(SkillScore.learner_id == learner_id)
    ).all()
    return build_skill_analysis(learner_id, skills)


@router.post("/learners/{learner_id}/tutor", response_model=TutorResponse)
def ask_learner_tutor(
    learner_id: int,
    payload: TutorRequest,
    database: Session = Depends(get_db),
    user: User = Depends(require_user),
) -> TutorResponse:
    learner = _owned_tutor_learner(learner_id, database, user)

    topic = database.get(Topic, payload.topic_id) if payload.topic_id else None
    course = _current_course(database, learner)
    course_id = topic.course_id if topic else course.id if course else None
    path = database.scalar(
        select(LearningPath)
        .where(
            LearningPath.learner_id == learner_id,
            LearningPath.course_id == course_id,
        )
        .order_by(LearningPath.created_at.desc())
    )
    if payload.topic_id:
        path_topic_ids = {item.get("topic_id") for item in path.path_json} if path else set()
        if payload.topic_id not in path_topic_ids:
            raise HTTPException(status_code=404, detail="Tutor topic is not part of the learner's path")
        if not topic or (topic.owner_user_id is not None and topic.owner_user_id != learner.user_id):
            raise HTTPException(status_code=404, detail="Tutor topic is not part of the learner's path")
    else:
        current_topic_id = (
            path.path_json[path.current_index].get("topic_id")
            if path and path.current_index < len(path.path_json)
            else None
        )
        topic = database.get(Topic, current_topic_id) if current_topic_id else None
    course = database.get(GeneratedCourse, course_id) if course_id else None
    course_topics = [item.get("title", "") for item in path.path_json] if path else []
    path_topic_ids = {item.get("topic_id") for item in path.path_json} if path else set()
    question_lower = payload.question.lower()
    asks_for_module = any(term in question_lower for term in ("course", "module", "lesson"))
    matching_module = module_matches_question(payload.question, course_topics)
    module_available = not asks_for_module or matching_module

    if topic is None:
        raise HTTPException(status_code=404, detail="A current learning topic is required for the tutor")
    try:
        context = build_tutor_context(database, learner_id, topic.id)
    except ValueError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    tutor_answer, source = generate_tutor_response(context, payload.question, [])
    weak_concepts = [item["concept"] for item in context.weak_concepts[:3]]
    return TutorResponse(
        learner_id=learner_id,
        topic_id=topic.id if topic else payload.topic_id,
        topic_title=display_topic_title(topic.title) if topic else "Current learning topic",
        answer=tutor_answer.answer,
        simple_explanation=tutor_answer.answer,
        example=tutor_answer.suggested_follow_up,
        coding_example=None,
        key_points=tutor_answer.related_concepts[:4] or [context.current_topic["title"]],
        weak_concepts=weak_concepts,
        related_topic=None,
        suggested_next_action=tutor_answer.suggested_follow_up,
        follow_up=tutor_answer.suggested_follow_up,
        course_title=course.title if course else None,
        course_connection=(
            f"No matching module was found in {course.title if course else 'your current learning path'}; no module was invented."
            if not module_available
            else f"{display_topic_title(topic.title)} is part of {course.title} and supports your goal: {learner.goal_text}."
            if topic and course
            else f"This explanation is scoped to {display_topic_title(topic.title)}."
            if topic
            else "No course module is currently selected."
        ),
        module_title=display_topic_title(topic.title) if topic and module_available else None,
        source=source,
    )


def _owned_tutor_learner(learner_id: int, database: Session, user: User) -> Learner:
    learner = database.get(Learner, learner_id)
    if not learner:
        raise HTTPException(status_code=404, detail="Learner not found")
    if learner.user_id != user.id:
        raise HTTPException(
            status_code=403,
            detail="This learner profile is not available to your account.",
        )
    return learner


def _conversation_or_404(
    learner_id: int, conversation_id: int, database: Session
) -> TutorConversation:
    conversation = database.scalar(
        select(TutorConversation).where(
            TutorConversation.id == conversation_id,
            TutorConversation.learner_id == learner_id,
        )
    )
    if not conversation:
        raise HTTPException(status_code=404, detail="Tutor conversation not found")
    return conversation


def _tutor_message_response(message: TutorMessage) -> TutorMessageResponse:
    response = (
        TutorResponsePayload.model_validate(message.response_json)
        if message.response_json
        else None
    )
    return TutorMessageResponse(
        id=message.id,
        role=message.role,
        content=message.content,
        response=response,
        created_at=message.created_at,
    )


@router.get(
    "/learners/{learner_id}/tutor/context",
    response_model=TutorContextResponse,
)
def get_tutor_context(
    learner_id: int,
    topic_id: str | None = None,
    current_topic_id: str | None = None,
    database: Session = Depends(get_db),
    user: User = Depends(require_user),
) -> TutorContextResponse:
    _owned_tutor_learner(learner_id, database, user)
    selected_topic_id = current_topic_id or topic_id
    if not selected_topic_id:
        raise HTTPException(status_code=422, detail="Select the current topic for tutor context")
    try:
        return build_tutor_context(database, learner_id, selected_topic_id)
    except ValueError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error


@router.post(
    "/learners/{learner_id}/tutor/conversations",
    response_model=TutorConversationSummary,
    status_code=status.HTTP_201_CREATED,
)
def create_tutor_conversation(
    learner_id: int,
    payload: TutorConversationCreate,
    database: Session = Depends(get_db),
    user: User = Depends(require_user),
) -> TutorConversation:
    _owned_tutor_learner(learner_id, database, user)
    try:
        context = build_tutor_context(database, learner_id, payload.topic_id)
    except ValueError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    title = (payload.title or context.current_topic["title"]).strip()[:160]
    conversation = TutorConversation(
        learner_id=learner_id,
        topic_id=payload.topic_id,
        title=title or context.current_topic["title"],
    )
    database.add(conversation)
    database.commit()
    database.refresh(conversation)
    return conversation


@router.get(
    "/learners/{learner_id}/tutor/conversations",
    response_model=list[TutorConversationSummary],
)
def list_tutor_conversations(
    learner_id: int,
    topic_id: str | None = None,
    database: Session = Depends(get_db),
    user: User = Depends(require_user),
) -> list[TutorConversation]:
    _owned_tutor_learner(learner_id, database, user)
    query = select(TutorConversation).where(TutorConversation.learner_id == learner_id)
    if topic_id:
        try:
            build_tutor_context(database, learner_id, topic_id)
        except ValueError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        query = query.where(TutorConversation.topic_id == topic_id)
    return list(database.scalars(query.order_by(TutorConversation.updated_at.desc()).limit(50)).all())


@router.get(
    "/learners/{learner_id}/tutor/conversations/{conversation_id}",
    response_model=TutorConversationResponse,
)
def get_tutor_conversation(
    learner_id: int,
    conversation_id: int,
    database: Session = Depends(get_db),
    user: User = Depends(require_user),
) -> TutorConversationResponse:
    _owned_tutor_learner(learner_id, database, user)
    conversation = _conversation_or_404(learner_id, conversation_id, database)
    messages = database.scalars(
        select(TutorMessage)
        .where(TutorMessage.conversation_id == conversation.id)
        .order_by(TutorMessage.created_at, TutorMessage.id)
    ).all()
    return TutorConversationResponse(
        id=conversation.id,
        learner_id=conversation.learner_id,
        topic_id=conversation.topic_id,
        title=conversation.title,
        created_at=conversation.created_at,
        updated_at=conversation.updated_at,
        messages=[_tutor_message_response(message) for message in messages],
    )


@router.post(
    "/learners/{learner_id}/tutor/conversations/{conversation_id}/messages",
    response_model=TutorMessageSendResponse,
)
def send_tutor_message(
    learner_id: int,
    conversation_id: int,
    payload: TutorMessageCreate,
    database: Session = Depends(get_db),
    user: User = Depends(require_user),
) -> TutorMessageSendResponse:
    _owned_tutor_learner(learner_id, database, user)
    conversation = _conversation_or_404(learner_id, conversation_id, database)
    try:
        context = build_tutor_context(database, learner_id, conversation.topic_id)
    except ValueError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error

    question = payload.content.strip()
    if not question:
        raise HTTPException(status_code=422, detail="Tutor message cannot be blank")
    user_message = TutorMessage(
        conversation_id=conversation.id,
        role="user",
        content=question,
    )
    if conversation.title == context.current_topic["title"]:
        conversation.title = question[:157].rstrip() + ("..." if len(question) > 160 else "")
    database.add(user_message)
    conversation_id = conversation.id
    try:
        database.commit()
        database.refresh(user_message)
        user_message_created_at = user_message.created_at
        history_rows = list(
            database.execute(
                select(TutorMessage.role, TutorMessage.content)
                .where(TutorMessage.conversation_id == conversation_id)
                .order_by(TutorMessage.created_at.desc(), TutorMessage.id.desc())
                .limit(RECENT_HISTORY_LIMIT)
            ).all()
        )
        history_rows.reverse()
        history = [
            TutorMessage(
                conversation_id=conversation_id,
                role=role,
                content=content,
            )
            for role, content in history_rows
        ]
        database.commit()
    except OperationalError as error:
        database.rollback()
        logger.warning(
            "Tutor message could not be stored; learner_id=%s conversation_id=%s reason=%s",
            learner_id,
            conversation_id,
            type(error).__name__,
        )
        raise HTTPException(
            status_code=503,
            detail="Tutor is temporarily busy saving your message. Please try again.",
        ) from None
    response, source = generate_tutor_response(
        context,
        question,
        history[:-1],
        payload.section_context,
        payload.teaching_style,
    )
    assistant_message = TutorMessage(
        conversation_id=conversation_id,
        role="assistant",
        content=response.answer,
        response_json=response.model_dump(mode="json"),
    )
    database.add(assistant_message)
    try:
        current_conversation = database.get(TutorConversation, conversation_id)
        if current_conversation is None:
            raise HTTPException(status_code=404, detail="Tutor conversation not found")
        current_conversation.updated_at = user_message_created_at
        database.commit()
    except OperationalError as error:
        database.rollback()
        logger.warning(
            "Tutor response could not be stored; learner_id=%s conversation_id=%s reason=%s",
            learner_id,
            conversation_id,
            type(error).__name__,
        )
        raise HTTPException(
            status_code=503,
            detail="Tutor response could not be saved. Your question was saved; please retry.",
        ) from None
    database.refresh(assistant_message)
    database.refresh(user_message)
    return TutorMessageSendResponse(
        conversation_id=conversation_id,
        user_message=_tutor_message_response(user_message),
        assistant_message=_tutor_message_response(assistant_message),
        response=response,
        source=source,
    )


@router.get("/learners/{learner_id}/summary", response_model=LearnerSummaryResponse)
@router.get(
    "/learners/{learner_id}/dashboard",
    response_model=DashboardSummaryResponse,
    dependencies=[Depends(require_user)],
)
def get_learner_summary(
    learner_id: int,
    course_id: int | None = None,
    database: Session = Depends(get_db),
    user: User | None = Depends(get_optional_user),
) -> DashboardSummaryResponse:
    learner = database.get(Learner, learner_id)
    if not learner:
        raise HTTPException(status_code=404, detail="Learner not found")
    ensure_learner_access(learner, user)
    if course_id is not None:
        course = database.scalar(
            select(GeneratedCourse).where(
                GeneratedCourse.id == course_id,
                GeneratedCourse.learner_id == learner_id,
            )
        )
        if not course:
            raise HTTPException(status_code=404, detail="Course not found")
    else:
        course = _current_course(database, learner)
    path_query = select(LearningPath).where(LearningPath.learner_id == learner_id)
    if course:
        path_query = path_query.where(LearningPath.course_id == course.id)
    path = database.scalar(
        path_query.order_by(LearningPath.created_at.desc())
    )
    path_topic_ids = {
        item.get("topic_id") for item in path.path_json if item.get("topic_id")
    } if path else set()
    course_topics = (
        database.scalars(
            select(Topic).where(Topic.course_id == course.id).order_by(Topic.id)
        ).all()
        if course
        else []
    )
    course_topic_ids = {topic.id for topic in course_topics}
    ordered_topic_ids = (
        [item["topic_id"] for item in path.path_json if item.get("topic_id")]
        if path
        else [topic.id for topic in course_topics]
    )
    active_topic_ids = path_topic_ids or course_topic_ids
    topics_by_id = {topic.id: topic for topic in course_topics}
    if path_topic_ids:
        for topic in database.scalars(select(Topic).where(Topic.id.in_(path_topic_ids))).all():
            topics_by_id[topic.id] = topic
    skills = database.scalars(
        select(SkillScore).where(SkillScore.learner_id == learner_id)
    ).all()
    if course:
        relevant_concepts = {
            str(concept).strip().casefold()
            for topic in topics_by_id.values()
            for concept in (topic.concept_tags or [])
            if str(concept).strip()
        }
        if active_topic_ids:
            relevant_concepts.update(
                str(concept).strip().casefold()
                for concept in database.scalars(
                    select(AssessmentQuestionRecord.concept)
                    .join(Assessment, Assessment.id == AssessmentQuestionRecord.assessment_id)
                    .where(
                        Assessment.learner_id == learner_id,
                        Assessment.topic_id.in_(active_topic_ids),
                        Assessment.completed_at.is_not(None),
                    )
                ).all()
                if str(concept).strip()
            )
        skills = [
            skill for skill in skills
            if skill.concept.strip().casefold() in relevant_concepts
        ]
    analysis = build_skill_analysis(learner_id, skills)
    progress_query = select(TopicProgress).where(TopicProgress.learner_id == learner_id)
    if active_topic_ids:
        progress_query = progress_query.where(TopicProgress.topic_id.in_(active_topic_ids))
    progress = database.scalars(progress_query).all()
    progress_by_topic = {item.topic_id: item for item in progress}
    topic_summaries: list[DashboardTopicResponse] = []
    current_topic_id = None
    current_index = None
    if path and path.path_json:
        if path.current_index < len(path.path_json):
            candidate_id = path.path_json[path.current_index].get("topic_id")
            candidate_progress = progress_by_topic.get(candidate_id)
            if not candidate_progress or candidate_progress.status != "completed":
                current_topic_id = candidate_id
                current_index = path.current_index
        if current_topic_id is None:
            for index, item in enumerate(path.path_json):
                item_progress = progress_by_topic.get(item.get("topic_id"))
                if not item_progress or item_progress.status != "completed":
                    current_topic_id = item.get("topic_id")
                    current_index = index
                    break

    for index, topic_id in enumerate(ordered_topic_ids):
        topic = topics_by_id.get(topic_id)
        if not topic:
            continue
        record = progress_by_topic.get(topic_id)
        if record and record.status == "completed":
            item_status = "completed"
        elif record and record.status == "remediation":
            item_status = "remediation"
        elif record and record.status == "in_progress":
            item_status = "in_progress"
        elif topic_id == current_topic_id:
            item_status = "current"
        else:
            item_status = "pending"
        topic_summaries.append(
            DashboardTopicResponse(
                topic_id=topic_id,
                title=display_topic_title(topic.title),
                course_id=topic.course_id or (course.id if course else None),
                course_title=course.title if course else None,
                status=item_status,
                completed_at=record.last_activity_at if record and record.status == "completed" else None,
                lesson_completed=record.lesson_completed if record else False,
            )
        )

    current_topic = next(
        (item for item in topic_summaries if item.topic_id == current_topic_id),
        None,
    )
    completed_topics = [item for item in topic_summaries if item.status == "completed"]
    total_topics = len(ordered_topic_ids)
    completed_count = len(completed_topics)
    latest_assessment_query = select(Assessment).where(
        Assessment.learner_id == learner_id,
        Assessment.completed_at.is_not(None),
    )
    if path:
        latest_assessment_query = latest_assessment_query.where(
            Assessment.topic_id.in_(path_topic_ids)
        )
    elif course:
        latest_assessment_query = latest_assessment_query.where(
            Assessment.topic_id.in_(course_topic_ids)
        )
    latest_assessment = database.scalar(
        latest_assessment_query.order_by(Assessment.completed_at.desc())
    )
    latest_summary = None
    if latest_assessment and latest_assessment.score is not None:
        topic = database.get(Topic, latest_assessment.topic_id) if latest_assessment.topic_id else None
        if topic or latest_assessment.assessment_type == "diagnostic":
            latest_summary = LatestAssessmentSummary(
                topic_id=topic.id if topic else None,
                topic_title=display_topic_title(topic.title) if topic else "Diagnostic assessment",
                percentage=round(latest_assessment.score * 100, 1),
            )
    path_completed = bool(total_topics and completed_count == total_topics)
    recommendation_record = (
        database.scalar(
            select(Recommendation)
            .where(
                Recommendation.learner_id == learner_id,
                Recommendation.topic_id.in_(path_topic_ids),
            )
            .order_by(Recommendation.created_at.desc())
        )
        if path_topic_ids and not path_completed
        else None
    )
    recommendation = None
    if recommendation_record:
        target = database.get(Topic, recommendation_record.topic_id) if recommendation_record.topic_id else None
        recommendation = RecommendationResponse(
            action_type=recommendation_record.action_type,
            target_topic_id=recommendation_record.topic_id,
            target_topic_title=display_topic_title(target.title) if target else None,
            summary=recommendation_record.reason,
            next_action=(
                "Review weak concepts and reassess before continuing."
                if recommendation_record.action_type == "remediate"
                else "Review focused examples before continuing."
                if recommendation_record.action_type == "practice"
                else "Continue to the next recommended topic."
            ),
            remediation=None,
        )
    if recommendation is None and current_topic:
        path_item = (
            path.path_json[current_index]
            if path and current_index is not None and current_index < len(path.path_json)
            else {}
        )
        recommendation = RecommendationResponse(
            action_type="continue",
            target_topic_id=current_topic.topic_id,
            target_topic_title=current_topic.title,
            summary=path_item.get("reason") or (path.overall_rationale if path else "Continue with your current topic."),
            next_action=f"Continue learning {current_topic.title}.",
            remediation=None,
        )

    assessment_query = select(Assessment).where(
        Assessment.learner_id == learner_id,
        Assessment.completed_at.is_not(None),
    )
    completed_assessments = database.scalars(
        assessment_query.order_by(Assessment.completed_at.desc(), Assessment.id.desc())
    ).all()
    completed_assessments = [
        assessment
        for assessment in completed_assessments
        if (
            assessment.topic_id in active_topic_ids
            or assessment.assessment_type == "diagnostic"
        )
    ]
    assessment_items: list[DashboardAssessmentItem] = []
    for assessment in completed_assessments:
        percentage = (
            assessment.percentage
            if assessment.percentage is not None
            else assessment.score * 100
            if assessment.score is not None
            else None
        )
        if percentage is None:
            continue
        topic = topics_by_id.get(assessment.topic_id) if assessment.topic_id else None
        if assessment.topic_id and not topic:
            topic = database.get(Topic, assessment.topic_id)
        assessment_items.append(
            DashboardAssessmentItem(
                assessment_id=assessment.id,
                topic_id=assessment.topic_id,
                topic_title=(
                    display_topic_title(topic.title)
                    if topic
                    else "Diagnostic assessment"
                    if assessment.assessment_type == "diagnostic"
                    else "Assessment"
                ),
                assessment_type=assessment.assessment_type,
                course_id=topic.course_id if topic else None,
                percentage=round(float(percentage), 1),
                completed_at=assessment.completed_at,
            )
        )
    recent_assessments = list(reversed(assessment_items[:5]))
    average_percentage = (
        round(sum(item.percentage for item in assessment_items) / len(assessment_items), 1)
        if assessment_items
        else None
    )
    assessment_performance = DashboardAssessmentPerformance(
        average_percentage=average_percentage,
        latest_percentage=assessment_items[0].percentage if assessment_items else None,
        completed_count=len(assessment_items),
        recent_scores=recent_assessments,
    )

    activity: list[DashboardActivityItem] = []
    for record in progress:
        if not record.last_activity_at:
            continue
        topic = topics_by_id.get(record.topic_id) or database.get(Topic, record.topic_id)
        topic_title = display_topic_title(topic.title) if topic else "Learning topic"
        completed = record.status == "completed"
        lesson_completed = record.lesson_completed and not completed
        activity.append(
            DashboardActivityItem(
                activity_type=(
                    "topic_completed"
                    if completed
                    else "lesson_completed"
                    if lesson_completed
                    else "progress_updated"
                ),
                title=(
                    f"Completed {topic_title}"
                    if completed
                    else f"Lesson completed: {topic_title}"
                    if lesson_completed
                    else f"Learning progress updated: {topic_title}"
                ),
                description=(
                    "Topic completion recorded."
                    if completed
                    else "Lesson marked complete; an assessment pass is still required."
                    if lesson_completed
                    else f"Recorded learning status: {record.status.replace('_', ' ')}."
                ),
                occurred_at=record.last_activity_at,
                topic_id=record.topic_id,
                course_id=topic.course_id if topic else (course.id if course else None),
            )
        )
    for item in assessment_items:
        activity.append(
            DashboardActivityItem(
                activity_type="assessment_completed",
                title=f"Completed assessment: {item.topic_title}",
                description=f"Score: {item.percentage:g}%",
                occurred_at=item.completed_at,
                topic_id=item.topic_id,
                course_id=item.course_id,
                assessment_id=item.assessment_id,
            )
        )
    if active_topic_ids:
        tutor_messages = database.scalars(
            select(TutorMessage)
            .join(TutorConversation, TutorConversation.id == TutorMessage.conversation_id)
            .where(
                TutorConversation.learner_id == learner_id,
                TutorConversation.topic_id.in_(active_topic_ids),
                TutorMessage.role == "user",
            )
            .order_by(TutorMessage.created_at.desc(), TutorMessage.id.desc())
            .limit(20)
        ).all()
        for message in tutor_messages:
            conversation = database.get(TutorConversation, message.conversation_id)
            topic = topics_by_id.get(conversation.topic_id) if conversation else None
            title = display_topic_title(topic.title) if topic else "your topic"
            activity.append(
                DashboardActivityItem(
                    activity_type="tutor_message",
                    title=f"Asked AI Tutor about {title}",
                    description=message.content[:160],
                    occurred_at=message.created_at,
                    topic_id=conversation.topic_id if conversation else None,
                    course_id=course.id if course else None,
                )
            )
    activity.sort(key=lambda item: item.occurred_at, reverse=True)

    return DashboardSummaryResponse(
        learner_id=learner.id,
        name=learner.name,
        goal=learner.goal_text,
        current_topic_id=current_topic.topic_id if current_topic else None,
        current_topic_title=current_topic.title if current_topic else None,
        completed_topics=completed_count,
        total_topics=total_topics,
        progress_percentage=round((completed_count / total_topics) * 100) if total_topics else 0,
        overall_skill_percentage=analysis.overall_percentage,
        strong_concepts=analysis.strong_areas,
        developing_concepts=analysis.developing_areas,
        weak_concepts=analysis.weak_areas,
        latest_assessment=latest_summary,
        recommendation=recommendation,
        course_id=course.id if course else (path.course_id if path else None),
        course_title=course.title if course else None,
        completed_topic_items=completed_topics,
        current_topic=current_topic,
        assessment_performance=assessment_performance,
        recent_activity=activity[:10],
        path_completed=path_completed,
    )
