from datetime import datetime

from typing import Any

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    is_active: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )
    learner: Mapped["Learner | None"] = relationship(back_populates="user", uselist=False)


class GeneratedCourse(Base):
    __tablename__ = "generated_courses"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    learner_id: Mapped[int] = mapped_column(ForeignKey("learners.id"), index=True)
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text)
    goal: Mapped[str] = mapped_column(Text)
    target_outcome: Mapped[str | None] = mapped_column(Text, nullable=True)
    level: Mapped[str] = mapped_column(String(30))
    estimated_duration: Mapped[str] = mapped_column(String(80))
    learning_objectives_json: Mapped[list[Any]] = mapped_column(JSON, default=list)
    modules_json: Mapped[list[Any]] = mapped_column(JSON, default=list)
    track_id: Mapped[str] = mapped_column(String(50), default="generative_ai")
    track_history_json: Mapped[list[Any]] = mapped_column(JSON, default=list)
    generation_source: Mapped[str] = mapped_column(String(30), default="unknown")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    topics: Mapped[list["Topic"]] = relationship(back_populates="course", cascade="all, delete-orphan")
    learner: Mapped["Learner"] = relationship(back_populates="courses")


class AIArtifactCache(Base):
    __tablename__ = "ai_artifact_cache"
    __table_args__ = (UniqueConstraint("learner_id", "operation", "cache_key"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    learner_id: Mapped[int] = mapped_column(ForeignKey("learners.id"), index=True)
    operation: Mapped[str] = mapped_column(String(80))
    cache_key: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(20), default="pending")
    source: Mapped[str | None] = mapped_column(String(30), nullable=True)
    result_json: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )


class Learner(Base):
    __tablename__ = "learners"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), unique=True, nullable=True, index=True)
    name: Mapped[str] = mapped_column(String(120))
    experience_level: Mapped[str] = mapped_column(String(30))
    goal_text: Mapped[str] = mapped_column(Text)
    preferred_learning_style: Mapped[str | None] = mapped_column(String(80), nullable=True)
    target_outcome: Mapped[str | None] = mapped_column(Text, nullable=True)
    track: Mapped[str] = mapped_column(String(50), default="generative_ai")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )
    goals: Mapped[list["LearningGoal"]] = relationship(
        back_populates="learner", cascade="all, delete-orphan"
    )
    skill_scores: Mapped[list["SkillScore"]] = relationship(
        back_populates="learner", cascade="all, delete-orphan"
    )
    learning_paths: Mapped[list["LearningPath"]] = relationship(
        back_populates="learner", cascade="all, delete-orphan"
    )
    topic_progress: Mapped[list["TopicProgress"]] = relationship(
        back_populates="learner", cascade="all, delete-orphan"
    )
    assessments: Mapped[list["Assessment"]] = relationship(
        back_populates="learner", cascade="all, delete-orphan"
    )
    weaknesses: Mapped[list["Weakness"]] = relationship(
        back_populates="learner", cascade="all, delete-orphan"
    )
    recommendations: Mapped[list["Recommendation"]] = relationship(
        back_populates="learner", cascade="all, delete-orphan"
    )
    user: Mapped[User | None] = relationship(back_populates="learner")
    courses: Mapped[list[GeneratedCourse]] = relationship(back_populates="learner")


class LearningGoal(Base):
    __tablename__ = "learning_goals"

    id: Mapped[int] = mapped_column(primary_key=True)
    learner_id: Mapped[int] = mapped_column(ForeignKey("learners.id"), index=True)
    title: Mapped[str] = mapped_column(String(160))
    track: Mapped[str] = mapped_column(String(50), default="generative_ai")
    is_active: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    learner: Mapped[Learner] = relationship(back_populates="goals")


class Topic(Base):
    __tablename__ = "topics"

    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    title: Mapped[str] = mapped_column(String(160), unique=True)
    description: Mapped[str] = mapped_column(Text)
    difficulty: Mapped[str] = mapped_column(String(30))
    concept_tags: Mapped[list[Any]] = mapped_column(JSON, default=list)
    learning_objectives_json: Mapped[list[Any]] = mapped_column(JSON, default=list)
    estimated_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    goal_relevance: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    content_source: Mapped[str] = mapped_column(String(240))
    track_id: Mapped[str] = mapped_column(String(50), default="generative_ai")
    is_active: Mapped[bool] = mapped_column(default=True)
    owner_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)
    course_id: Mapped[int | None] = mapped_column(ForeignKey("generated_courses.id"), nullable=True, index=True)

    prerequisites: Mapped[list["TopicPrerequisite"]] = relationship(
        foreign_keys="TopicPrerequisite.topic_id",
        back_populates="topic",
        cascade="all, delete-orphan",
    )
    required_by: Mapped[list["TopicPrerequisite"]] = relationship(
        foreign_keys="TopicPrerequisite.prerequisite_id",
        back_populates="prerequisite",
        cascade="all, delete-orphan",
    )
    progress_records: Mapped[list["TopicProgress"]] = relationship(
        back_populates="topic", cascade="all, delete-orphan"
    )
    assessments: Mapped[list["Assessment"]] = relationship(back_populates="topic")
    weaknesses: Mapped[list["Weakness"]] = relationship(back_populates="topic")
    recommendations: Mapped[list["Recommendation"]] = relationship(back_populates="topic")
    course: Mapped[GeneratedCourse | None] = relationship(back_populates="topics")


class TopicPrerequisite(Base):
    __tablename__ = "topic_prerequisites"
    __table_args__ = (UniqueConstraint("topic_id", "prerequisite_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    topic_id: Mapped[str] = mapped_column(ForeignKey("topics.id"), index=True)
    prerequisite_id: Mapped[str] = mapped_column(ForeignKey("topics.id"), index=True)

    topic: Mapped[Topic] = relationship(
        foreign_keys=[topic_id], back_populates="prerequisites"
    )
    prerequisite: Mapped[Topic] = relationship(
        foreign_keys=[prerequisite_id], back_populates="required_by"
    )


class SkillScore(Base):
    __tablename__ = "skill_scores"
    __table_args__ = (UniqueConstraint("learner_id", "concept"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    learner_id: Mapped[int] = mapped_column(ForeignKey("learners.id"), index=True)
    concept: Mapped[str] = mapped_column(String(100))
    score: Mapped[float] = mapped_column(Float, default=0.0)
    evidence_count: Mapped[int] = mapped_column(Integer, default=0)
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    source: Mapped[str] = mapped_column(String(30))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    learner: Mapped[Learner] = relationship(back_populates="skill_scores")


class LearningPath(Base):
    __tablename__ = "learning_paths"

    id: Mapped[int] = mapped_column(primary_key=True)
    learner_id: Mapped[int] = mapped_column(ForeignKey("learners.id"), index=True)
    course_id: Mapped[int | None] = mapped_column(ForeignKey("generated_courses.id"), nullable=True, index=True)
    goal: Mapped[str] = mapped_column(Text)
    path_json: Mapped[list[Any]] = mapped_column(JSON, default=list)
    overall_rationale: Mapped[str] = mapped_column(Text, default="")
    current_index: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    learner: Mapped[Learner] = relationship(back_populates="learning_paths")


class TopicProgress(Base):
    __tablename__ = "topic_progress"
    __table_args__ = (UniqueConstraint("learner_id", "topic_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    learner_id: Mapped[int] = mapped_column(ForeignKey("learners.id"), index=True)
    topic_id: Mapped[str] = mapped_column(ForeignKey("topics.id"), index=True)
    status: Mapped[str] = mapped_column(String(30), default="pending")
    lesson_completed: Mapped[bool] = mapped_column(Boolean, default=False)
    mastery_score: Mapped[float] = mapped_column(Float, default=0.0)
    attempt_count: Mapped[int] = mapped_column(Integer, default=0)
    last_activity_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    learner: Mapped[Learner] = relationship(back_populates="topic_progress")
    topic: Mapped[Topic] = relationship(back_populates="progress_records")


class Assessment(Base):
    __tablename__ = "assessments"

    id: Mapped[int] = mapped_column(primary_key=True)
    learner_id: Mapped[int] = mapped_column(ForeignKey("learners.id"), index=True)
    topic_id: Mapped[str | None] = mapped_column(ForeignKey("topics.id"), nullable=True)
    assessment_type: Mapped[str] = mapped_column(String(30), default="diagnostic")
    questions_json: Mapped[list[Any]] = mapped_column(JSON, default=list)
    answers_json: Mapped[list[Any]] = mapped_column(JSON, default=list)
    feedback_json: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    selected_types: Mapped[list[str]] = mapped_column(JSON, default=lambda: ["mcq"])
    status: Mapped[str] = mapped_column(String(20), default="pending")
    total_points: Mapped[int] = mapped_column(Integer, default=0)
    earned_points: Mapped[float] = mapped_column(Float, default=0.0)
    percentage: Mapped[float | None] = mapped_column(Float, nullable=True)
    assessment_version: Mapped[str] = mapped_column(String(40), default="multi-type-v1")
    score: Mapped[float | None] = mapped_column(Float, nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    learner: Mapped[Learner] = relationship(back_populates="assessments")
    topic: Mapped[Topic | None] = relationship(back_populates="assessments")
    questions: Mapped[list["AssessmentQuestionRecord"]] = relationship(
        back_populates="assessment", cascade="all, delete-orphan"
    )


class AssessmentQuestionRecord(Base):
    __tablename__ = "assessment_questions"

    id: Mapped[int] = mapped_column(primary_key=True)
    assessment_id: Mapped[int] = mapped_column(ForeignKey("assessments.id"), index=True)
    question_id: Mapped[str] = mapped_column(String(80))
    question_type: Mapped[str] = mapped_column(String(30), index=True)
    question: Mapped[str] = mapped_column(Text)
    concept: Mapped[str] = mapped_column(String(100))
    difficulty: Mapped[str] = mapped_column(String(30))
    points: Mapped[int] = mapped_column(Integer, default=1)
    options_json: Mapped[list[Any] | None] = mapped_column(JSON, nullable=True)
    code: Mapped[str | None] = mapped_column(Text, nullable=True)
    starter_code: Mapped[str | None] = mapped_column(Text, nullable=True)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    evaluation_data_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)

    assessment: Mapped[Assessment] = relationship(back_populates="questions")
    response: Mapped["AssessmentResponseRecord | None"] = relationship(
        back_populates="question", cascade="all, delete-orphan", uselist=False
    )


class AssessmentResponseRecord(Base):
    __tablename__ = "assessment_responses"

    id: Mapped[int] = mapped_column(primary_key=True)
    assessment_question_id: Mapped[int] = mapped_column(
        ForeignKey("assessment_questions.id"), unique=True, index=True
    )
    learner_answer_json: Mapped[Any] = mapped_column(JSON)
    score: Mapped[float] = mapped_column(Float, default=0.0)
    feedback_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    evaluation_source: Mapped[str] = mapped_column(String(30))
    evaluated_at: Mapped[datetime | None] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=True
    )

    question: Mapped[AssessmentQuestionRecord] = relationship(back_populates="response")


class Weakness(Base):
    __tablename__ = "weaknesses"

    id: Mapped[int] = mapped_column(primary_key=True)
    learner_id: Mapped[int] = mapped_column(ForeignKey("learners.id"), index=True)
    topic_id: Mapped[str | None] = mapped_column(ForeignKey("topics.id"), nullable=True)
    concept: Mapped[str] = mapped_column(String(100))
    severity: Mapped[str] = mapped_column(String(20))
    evidence: Mapped[list[Any]] = mapped_column(JSON, default=list)
    status: Mapped[str] = mapped_column(String(30), default="open")
    detected_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    learner: Mapped[Learner] = relationship(back_populates="weaknesses")
    topic: Mapped[Topic | None] = relationship(back_populates="weaknesses")


class Recommendation(Base):
    __tablename__ = "recommendations"

    id: Mapped[int] = mapped_column(primary_key=True)
    learner_id: Mapped[int] = mapped_column(ForeignKey("learners.id"), index=True)
    action_type: Mapped[str] = mapped_column(String(30))
    topic_id: Mapped[str | None] = mapped_column(ForeignKey("topics.id"), nullable=True)
    reason: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    learner: Mapped[Learner] = relationship(back_populates="recommendations")
    topic: Mapped[Topic | None] = relationship(back_populates="recommendations")


class TutorConversation(Base):
    __tablename__ = "tutor_conversations"

    id: Mapped[int] = mapped_column(primary_key=True)
    learner_id: Mapped[int] = mapped_column(ForeignKey("learners.id", ondelete="CASCADE"), index=True)
    topic_id: Mapped[str] = mapped_column(ForeignKey("topics.id", ondelete="CASCADE"), index=True)
    title: Mapped[str] = mapped_column(String(160), default="Tutor conversation")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, index=True
    )


class TutorMessage(Base):
    __tablename__ = "tutor_messages"

    id: Mapped[int] = mapped_column(primary_key=True)
    conversation_id: Mapped[int] = mapped_column(
        ForeignKey("tutor_conversations.id", ondelete="CASCADE"), index=True
    )
    role: Mapped[str] = mapped_column(String(20))
    content: Mapped[str] = mapped_column(Text)
    response_json: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
