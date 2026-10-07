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


class LearningPathTopic(BaseModel):
    topic_id: str
    title: str
    difficulty: str
    status: Literal["completed", "current", "pending", "remediation"]
    prerequisites: list[str]
    reason: str
    relevance_score: float


class LearningPathResponse(BaseModel):
    path_id: int
    learner_id: int
    goal: str
    current_index: int
    current_topic_id: str | None
    current_topic_title: str | None
    overall_rationale: str
    topics: list[LearningPathTopic]


class CurrentTopicResponse(BaseModel):
    learner_id: int
    topic_id: str
    title: str
    difficulty: str
    position: int
    total_topics: int
    status: Literal["in_progress", "completed", "pending", "remediation"]
    prerequisites: list[str]


class LearningContent(BaseModel):
    topic_id: str = Field(min_length=2, max_length=80)
    topic_title: str = Field(min_length=2, max_length=160)
    overview: str = Field(min_length=20, max_length=800)
    learning_objectives: list[str] = Field(min_length=2, max_length=6)
    explanation: str = Field(min_length=40, max_length=3000)
    key_concepts: list[str] = Field(min_length=2, max_length=8)
    examples: list[str] = Field(min_length=1, max_length=5)
    practical_example: str = Field(min_length=20, max_length=1600)
    common_mistakes: list[str] = Field(min_length=1, max_length=5)
    quick_recap: list[str] = Field(min_length=2, max_length=6)
    analogy: str | None = Field(default=None, max_length=900)
    code_example: str | None = Field(default=None, max_length=1800)
    important_notes: list[str] = Field(default_factory=list, max_length=6)


class LearningContentResponse(BaseModel):
    learner_id: int
    content: LearningContent
    source: Literal["openrouter", "curated_fallback"]
    topic_status: Literal["in_progress", "completed", "pending", "remediation"]


class AssessmentQuestion(BaseModel):
    question_id: str = Field(min_length=2, max_length=80)
    question: str = Field(min_length=10, max_length=700)
    options: list[str] = Field(min_length=3, max_length=5)
    concept: str = Field(min_length=2, max_length=100)
    difficulty: Literal["beginner", "intermediate", "advanced"]
    correct_option: int = Field(ge=0)
    explanation: str = Field(min_length=5, max_length=500)

    @model_validator(mode="after")
    def validate_correct_option(self) -> "AssessmentQuestion":
        if self.correct_option >= len(self.options):
            raise ValueError("correct_option must reference an available option")
        return self


class AssessmentQuestionSet(BaseModel):
    questions: list[AssessmentQuestion] = Field(min_length=3, max_length=8)

    @model_validator(mode="after")
    def validate_question_set(self) -> "AssessmentQuestionSet":
        question_ids = [question.question_id for question in self.questions]
        if len(question_ids) != len(set(question_ids)):
            raise ValueError("Assessment question IDs must be unique")
        return self


class AssessmentQuestionPublic(BaseModel):
    question_id: str
    question: str
    options: list[str]
    concept: str
    difficulty: Literal["beginner", "intermediate", "advanced"]


class AssessmentGenerateResponse(BaseModel):
    assessment_id: int
    learner_id: int
    topic_id: str
    topic_title: str
    status: Literal["pending", "submitted"]
    questions: list[AssessmentQuestionPublic]
    source: Literal["openrouter", "curated_fallback"]


class AssessmentAnswer(BaseModel):
    question_id: str = Field(min_length=2, max_length=80)
    selected_option: int = Field(ge=0)


class AssessmentSubmitRequest(BaseModel):
    answers: list[AssessmentAnswer] = Field(min_length=1, max_length=8)


class ConceptResult(BaseModel):
    concept: str
    correct_count: int
    total_questions: int
    score: float
    percentage: int
    level: Literal["weak", "developing", "strong"]


class RecommendationResponse(BaseModel):
    action_type: Literal["remediate", "practice", "continue", "reassess"]
    target_topic_id: str | None
    target_topic_title: str | None
    summary: str
    next_action: str
    remediation: str | None


class AssessmentResultResponse(BaseModel):
    assessment_id: int
    learner_id: int
    topic_id: str
    topic_title: str
    score: int
    percentage: float
    correct_count: int
    total_questions: int
    concept_results: list[ConceptResult]
    weak_concepts: list[str]
    strong_concepts: list[str]
    recommendation: RecommendationResponse


class LatestAssessmentSummary(BaseModel):
    topic_id: str
    topic_title: str
    percentage: float


class LearnerSummaryResponse(BaseModel):
    learner_id: int
    name: str
    goal: str
    current_topic_id: str | None
    current_topic_title: str | None
    completed_topics: int
    total_topics: int
    progress_percentage: int
    overall_skill_percentage: int
    strong_concepts: list[SkillScoreResponse]
    developing_concepts: list[SkillScoreResponse]
    weak_concepts: list[SkillScoreResponse]
    latest_assessment: LatestAssessmentSummary | None
    recommendation: RecommendationResponse | None
