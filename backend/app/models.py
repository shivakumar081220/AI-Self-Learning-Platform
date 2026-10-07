from datetime import datetime

from typing import Any

from sqlalchemy import DateTime, Float, ForeignKey, Integer, JSON, String, Text, UniqueConstraint
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
    learner_id: Mapped[int] = mapped_column(ForeignKey("learners.id"), unique=True, index=True)
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text)
    goal: Mapped[str] = mapped_column(Text)
    level: Mapped[str] = mapped_column(String(30))
    estimated_duration: Mapped[str] = mapped_column(String(80))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    topics: Mapped[list["Topic"]] = relationship(back_populates="course", cascade="all, delete-orphan")
    learner: Mapped["Learner"] = relationship(back_populates="course")


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
    course: Mapped[GeneratedCourse | None] = relationship(back_populates="learner")


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
    goal_relevance: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    content_source: Mapped[str] = mapped_column(String(240))
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
    score: Mapped[float | None] = mapped_column(Float, nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    learner: Mapped[Learner] = relationship(back_populates="assessments")
    topic: Mapped[Topic | None] = relationship(back_populates="assessments")


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
