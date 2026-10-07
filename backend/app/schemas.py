from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


ExperienceLevel = Literal["beginner", "intermediate", "advanced"]


class GoalOption(BaseModel):
    key: str
    label: str
    description: str


class LearnerCreate(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    experience_level: ExperienceLevel
    goal_key: str | None = None
    custom_goal: str | None = Field(default=None, max_length=240)

    @field_validator("name", "custom_goal", mode="before")
    @classmethod
    def strip_text(cls, value: str | None) -> str | None:
        return value.strip() if isinstance(value, str) else value

    @model_validator(mode="after")
    def require_goal(self) -> "LearnerCreate":
        if not self.goal_key and not self.custom_goal:
            raise ValueError("Select a learning goal or provide a custom goal")
        return self


class LearnerResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    experience_level: ExperienceLevel
    goal_text: str
    track: str
    created_at: datetime


class DiagnosticQuestion(BaseModel):
    id: str = Field(min_length=2, max_length=80)
    question: str = Field(min_length=10, max_length=600)
    options: list[str] = Field(min_length=3, max_length=5)
    correct_option: int = Field(ge=0)
    concept: str = Field(min_length=2, max_length=100)
    explanation: str = Field(min_length=5, max_length=500)

    @model_validator(mode="after")
    def validate_correct_option(self) -> "DiagnosticQuestion":
        if self.correct_option >= len(self.options):
            raise ValueError("correct_option must reference an available option")
        return self


class DiagnosticQuestionSet(BaseModel):
    questions: list[DiagnosticQuestion] = Field(min_length=6, max_length=12)

    @model_validator(mode="after")
    def validate_question_set(self) -> "DiagnosticQuestionSet":
        question_ids = [question.id for question in self.questions]
        if len(question_ids) != len(set(question_ids)):
            raise ValueError("Diagnostic question IDs must be unique")
        concepts = {question.concept for question in self.questions}
        if len(concepts) < 3:
            raise ValueError("Diagnostic must cover at least three concepts")
        return self


class DiagnosticQuestionPublic(BaseModel):
    id: str
    question: str
    options: list[str]


class DiagnosticGenerateResponse(BaseModel):
    assessment_id: int
    questions: list[DiagnosticQuestionPublic]
    generated_by: Literal["openai", "curated_fallback"]


class AnswerSubmission(BaseModel):
    question_id: str = Field(min_length=2, max_length=80)
    selected_option: int = Field(ge=0)


class DiagnosticSubmitRequest(BaseModel):
    answers: list[AnswerSubmission] = Field(min_length=1, max_length=20)


class SkillScoreResponse(BaseModel):
    concept: str
    score: float
    percentage: int
    level: Literal["weak", "developing", "strong"]
    evidence_count: int


class SkillAnalysisResponse(BaseModel):
    learner_id: int
    overall_score: float
    overall_percentage: int
    strong_areas: list[SkillScoreResponse]
    developing_areas: list[SkillScoreResponse]
    weak_areas: list[SkillScoreResponse]
    skills: list[SkillScoreResponse]


class DiagnosticSubmitResponse(SkillAnalysisResponse):
    assessment_id: int
    answered_questions: int
