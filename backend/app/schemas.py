from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


ExperienceLevel = Literal["beginner", "intermediate", "advanced"]
TutorTeachingStyle = Literal[
    "simplified",
    "analogy",
    "technical",
    "code_based",
    "step_by_step",
]


class RegisterRequest(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    email: str = Field(min_length=5, max_length=255)
    password: str = Field(min_length=8, max_length=128)

    @field_validator("email")
    @classmethod
    def validate_email(cls, value: str) -> str:
        value = value.strip().lower()
        if "@" not in value or "." not in value.rsplit("@", 1)[-1]:
            raise ValueError("Enter a valid email address")
        return value


class LoginRequest(BaseModel):
    email: str
    password: str


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: str
    is_active: bool


class AuthResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse


class GoalOption(BaseModel):
    key: str
    label: str
    description: str


class AITrackOption(BaseModel):
    id: str
    name: str
    description: str
    learning_objective: str
    difficulty: ExperienceLevel
    example_goals: list[str]
    prerequisite_tracks: list[str]


class LearnerCreate(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    experience_level: ExperienceLevel
    track_id: str | None = None
    goal_key: str | None = None
    custom_goal: str | None = Field(default=None, max_length=240)
    preferred_learning_style: str | None = Field(default=None, max_length=80)
    target_outcome: str | None = Field(default=None, max_length=240)

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
    target_outcome: str | None = None
    track: str
    created_at: datetime


class CurriculumTopic(BaseModel):
    title: str = Field(min_length=3, max_length=160)
    description: str = Field(min_length=20, max_length=800)
    learning_objectives: list[str] = Field(min_length=2, max_length=6)
    difficulty: ExperienceLevel
    concepts: list[str] = Field(min_length=1, max_length=8)
    prerequisites: list[str] = Field(default_factory=list, max_length=8)
    estimated_minutes: int = Field(ge=10, le=240)


class CurriculumModule(BaseModel):
    title: str = Field(min_length=3, max_length=160)
    description: str = Field(min_length=20, max_length=800)
    learning_objectives: list[str] = Field(min_length=2, max_length=6)
    difficulty: ExperienceLevel
    prerequisites: list[str] = Field(default_factory=list, max_length=8)
    estimated_minutes: int = Field(ge=10, le=600)
    practical_exercises: list[str] = Field(min_length=1, max_length=5)
    assessment_objectives: list[str] = Field(min_length=1, max_length=6)
    skills_to_revise: list[str] = Field(default_factory=list, max_length=8)
    skills_to_learn: list[str] = Field(min_length=1, max_length=8)
    topics: list[CurriculumTopic] = Field(min_length=1, max_length=8)


class GeneratedCurriculum(BaseModel):
    model_config = ConfigDict(extra="forbid")

    course_title: str = Field(min_length=5, max_length=200)
    description: str = Field(min_length=20, max_length=800)
    track_id: str = Field(min_length=2, max_length=50)
    goal: str = Field(min_length=3, max_length=240)
    level: ExperienceLevel
    estimated_duration: str = Field(min_length=3, max_length=80)
    learning_objectives: list[str] = Field(min_length=3, max_length=8)
    modules: list[CurriculumModule] = Field(default_factory=list, min_length=0, max_length=12)
    topics: list[CurriculumTopic] = Field(default_factory=list, max_length=48)

    @model_validator(mode="after")
    def validate_curriculum_structure(self) -> "GeneratedCurriculum":
        if not self.modules and self.topics:
            module_by_title = {topic.title: topic for topic in self.topics}
            module_positions = {topic.title: index for index, topic in enumerate(self.topics)}
            self.modules = [
                CurriculumModule(
                    title=topic.title,
                    description=topic.description,
                    learning_objectives=topic.learning_objectives[:6],
                    difficulty=topic.difficulty,
                    prerequisites=topic.prerequisites,
                    estimated_minutes=topic.estimated_minutes,
                    practical_exercises=[
                        f"Apply {topic.concepts[0].replace('_', ' ')} to the learner's selected goal."
                    ],
                    assessment_objectives=topic.learning_objectives[:3],
                    skills_to_learn=topic.concepts[:8],
                    topics=[topic],
                )
                for topic in self.topics
            ]
            if any(
                prerequisite not in module_by_title
                or module_positions[prerequisite] >= module_positions[topic.title]
                for topic in self.topics
                for prerequisite in topic.prerequisites
            ):
                raise ValueError("Curriculum prerequisites must precede dependent topics")
        elif self.modules:
            self.topics = [
                topic
                for module in self.modules
                for topic in module.topics
            ]
        if len(self.modules) < 3:
            raise ValueError("A complete curriculum must contain at least three modules")
        module_titles = [module.title for module in self.modules]
        if len(module_titles) != len(set(module_titles)):
            raise ValueError("Curriculum module titles must be unique")
        module_positions = {title: index for index, title in enumerate(module_titles)}
        if any(
            prerequisite not in module_positions
            or module_positions[prerequisite] >= module_positions[module.title]
            for module in self.modules
            for prerequisite in module.prerequisites
        ):
            raise ValueError("Module prerequisites must precede dependent modules")
        topic_titles = [topic.title for module in self.modules for topic in module.topics]
        if len(topic_titles) != len(set(topic_titles)):
            raise ValueError("Curriculum topic titles must be unique")
        topic_positions = {title: index for index, title in enumerate(topic_titles)}
        if any(
            prerequisite not in topic_positions
            or topic_positions[prerequisite] >= topic_positions[topic.title]
            for topic in self.topics
            for prerequisite in topic.prerequisites
        ):
            raise ValueError("Curriculum prerequisites must reference generated topics")
        if len({concept for topic in self.topics for concept in topic.concepts}) < 3:
            raise ValueError("Curriculum must define at least three distinct concepts")
        return self


class CurriculumResponse(BaseModel):
    course_id: int
    track_id: str
    track_name: str
    course_title: str
    description: str
    goal: str
    level: ExperienceLevel
    estimated_duration: str
    learning_objectives: list[str] = Field(default_factory=list)
    modules: list[dict] = Field(default_factory=list)
    topics: list[dict]
    track_history: list[dict] = Field(default_factory=list)
    courses: list[dict] = Field(default_factory=list)
    source: Literal["openrouter", "deterministic_fallback", "persisted"]
    generation_source: Literal["openrouter", "deterministic_fallback", "unknown"]


class DiagnosticQuestion(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=2, max_length=80)
    question: str = Field(min_length=10, max_length=600)
    options: list[str] = Field(min_length=3, max_length=5)
    correct_option: int = Field(ge=0)
    concept: str = Field(min_length=2, max_length=100)
    difficulty: ExperienceLevel
    explanation: str = Field(min_length=5, max_length=500)

    @model_validator(mode="after")
    def validate_correct_option(self) -> "DiagnosticQuestion":
        if self.correct_option >= len(self.options):
            raise ValueError("correct_option must reference an available option")
        return self


class DiagnosticQuestionSet(BaseModel):
    model_config = ConfigDict(extra="forbid")

    questions: list[DiagnosticQuestion] = Field(min_length=8, max_length=8)

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
    concept: str
    difficulty: ExperienceLevel


class DiagnosticGenerateResponse(BaseModel):
    assessment_id: int
    questions: list[DiagnosticQuestionPublic]
    generated_by: Literal["openrouter", "cache", "curated_fallback"]


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


class DiagnosticConceptInsight(BaseModel):
    concept: str
    level: Literal["weak", "developing", "strong"]
    percentage: int
    correct_questions: int
    total_questions: int
    evidence_statement: str
    current_strength: str
    knowledge_gap: str
    improvement_plan: list[str] = Field(default_factory=list, max_length=5)
    supporting_topics: list[str] = Field(default_factory=list, max_length=5)


class SkillInterpretationResponse(BaseModel):
    summary: str
    focus_concepts: list[str]
    knowledge_level: str = "developing"
    knowledge_assessment: str = ""
    source: Literal["openrouter", "deterministic_fallback"]


class CodingExample(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=3, max_length=140)
    code: str = Field(min_length=8, max_length=5000)
    explanation: str = Field(min_length=10, max_length=1200)
    expected_output: str | None = Field(default=None, max_length=1200)
    why_it_matters: str = Field(min_length=10, max_length=700)
    common_mistake: str = Field(min_length=10, max_length=500)


class LessonSubsection(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=2, max_length=140)
    explanation: str = Field(min_length=20, max_length=1800)
    key_points: list[str] = Field(default_factory=list, max_length=6)
    examples: list[str] = Field(default_factory=list, max_length=4)
    practical_application: str | None = Field(default=None, max_length=1200)
    tutor_prompts: list[str] = Field(default_factory=list, max_length=6)


class LessonSection(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=2, max_length=140)
    summary: str = Field(min_length=20, max_length=1200)
    subsections: list[LessonSubsection] = Field(default_factory=list, max_length=8)


class LessonCodeExample(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=3, max_length=140)
    language: str = Field(default="python", min_length=2, max_length=30)
    code: str = Field(min_length=8, max_length=5000)
    explanation: str = Field(min_length=10, max_length=1200)
    expected_output: str | None = Field(default=None, max_length=1200)


class LessonMistake(BaseModel):
    model_config = ConfigDict(extra="forbid")

    mistake: str = Field(min_length=5, max_length=400)
    explanation: str = Field(min_length=10, max_length=900)
    correction: str = Field(min_length=10, max_length=900)


class LessonSelfCheck(BaseModel):
    model_config = ConfigDict(extra="forbid")

    question: str = Field(min_length=5, max_length=500)
    hint: str = Field(min_length=3, max_length=300)


class QuestionReviewItem(BaseModel):
    question_id: str
    question: str
    options: list[str]
    selected_option: int | None
    correct_option: int
    is_correct: bool
    concept: str
    explanation: str


class DiagnosticSubmitResponse(SkillAnalysisResponse):
    assessment_id: int
    answered_questions: int
    question_review: list[QuestionReviewItem] = Field(default_factory=list)
    concept_insights: list[DiagnosticConceptInsight] = Field(default_factory=list)
    ai_interpretation: SkillInterpretationResponse | None = None


class TutorRequest(BaseModel):
    question: str = Field(min_length=4, max_length=500)
    topic_id: str | None = Field(default=None, max_length=80)


class TutorResponse(BaseModel):
    learner_id: int
    topic_id: str | None
    topic_title: str
    answer: str
    simple_explanation: str
    example: str
    coding_example: CodingExample | None = None
    key_points: list[str]
    weak_concepts: list[str]
    related_topic: str | None
    suggested_next_action: str
    follow_up: str
    course_title: str | None
    course_connection: str
    module_title: str | None
    source: Literal["openrouter", "deterministic_fallback"]


class TutorContextResponse(BaseModel):
    learner_id: int
    goal: str
    experience_level: str
    track: str
    course: dict[str, Any] | None
    current_topic: dict[str, Any]
    completed_topics: list[dict[str, Any]]
    in_progress_topics: list[dict[str, Any]]
    weak_concepts: list[dict[str, Any]]
    strong_concepts: list[dict[str, Any]]
    recent_assessments: list[dict[str, Any]]
    learning_path: dict[str, Any]


class TutorConversationCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    topic_id: str = Field(min_length=1, max_length=80)
    title: str | None = Field(default=None, max_length=160)


class TutorSectionContext(BaseModel):
    model_config = ConfigDict(extra="forbid")

    section_title: str = Field(min_length=2, max_length=140)
    subsection_title: str | None = Field(default=None, max_length=140)
    content: str = Field(min_length=1, max_length=5000)


class TutorMessageCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    content: str = Field(min_length=1, max_length=2000)
    section_context: TutorSectionContext | None = None
    teaching_style: TutorTeachingStyle | None = None


class TutorAttachmentResponse(BaseModel):
    id: int
    content_type: Literal["image/jpeg", "image/png", "image/gif", "image/webp"]
    size_bytes: int


class TutorResponsePayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    answer: str = Field(min_length=20, max_length=3000)
    answer_type: Literal[
        "concept",
        "explanation",
        "example",
        "comparison",
        "why",
        "how",
        "code",
        "debugging",
        "practical_application",
        "formula",
        "scenario",
        "exam_preparation",
        "summary",
    ] = "explanation"
    direct_answer: str | None = Field(default=None, max_length=1200)
    key_points: list[str] = Field(default_factory=list, max_length=8)
    step_by_step: list[str] = Field(default_factory=list, max_length=8)
    example: str | None = Field(default=None, max_length=1200)
    practical_application: str | None = Field(default=None, max_length=1200)
    common_mistake: str | None = Field(default=None, max_length=800)
    takeaway: str | None = Field(default=None, max_length=500)
    follow_up_question: str | None = Field(default=None, max_length=300)
    teaching_approach: str = Field(min_length=3, max_length=80)
    difficulty: Literal["beginner", "intermediate", "advanced"]
    related_concepts: list[str] = Field(max_length=8)
    weak_area_addressed: str | None = Field(default=None, max_length=100)
    suggested_follow_up: str = Field(min_length=3, max_length=300)


class TutorMessageResponse(BaseModel):
    id: int
    role: Literal["user", "assistant"]
    content: str
    response: TutorResponsePayload | None = None
    attachments: list[TutorAttachmentResponse] = Field(default_factory=list)
    created_at: datetime


class TutorConversationSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    learner_id: int
    topic_id: str
    title: str
    created_at: datetime
    updated_at: datetime


class TutorConversationResponse(TutorConversationSummary):
    messages: list[TutorMessageResponse]


class TutorMessageSendResponse(BaseModel):
    conversation_id: int
    user_message: TutorMessageResponse
    assistant_message: TutorMessageResponse
    response: TutorResponsePayload
    source: Literal["openrouter", "deterministic_fallback"]


class TutorCodingRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    action: Literal["ask", "generate", "explain", "debug", "improve", "tests", "exercise"]
    language: Literal["python"] = "python"
    prompt: str = Field(default="", max_length=2000)
    code: str = Field(default="", max_length=12000)
    execution_output: str = Field(default="", max_length=8000)
    execution_stderr: str = Field(default="", max_length=8000)
    execution_status: Literal["not_run", "completed", "failed", "timeout", "unavailable"] = "not_run"


class TutorCodingResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    summary: str = Field(min_length=1, max_length=2000)
    code: str = Field(default="", max_length=12000)
    explanation: str = Field(default="", max_length=5000)
    suggested_tests: list[str] = Field(default_factory=list, max_length=12)


class TutorCodeExecutionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    language: Literal["python"] = "python"
    source_code: str = Field(min_length=1, max_length=12000)
    stdin: str = Field(default="", max_length=4000)


class TutorCodeExecutionResponse(BaseModel):
    execution_id: int
    language: Literal["python"]
    status: Literal["completed", "failed", "timeout", "unavailable"]
    output: str
    stderr: str
    exit_status: int | None
    duration_ms: int | None
    provider_duration_ms: int | None
    created_at: datetime
    provider_metadata_available: bool


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
    course_id: int | None = None
    goal: str
    current_index: int
    current_topic_id: str | None
    current_topic_title: str | None
    overall_rationale: str
    topics: list[LearningPathTopic]
    pending_assessments: list[dict[str, Any]] = Field(default_factory=list)


class CurrentTopicResponse(BaseModel):
    learner_id: int
    topic_id: str
    title: str
    course_id: int | None = None
    track_id: str | None = None
    course_title: str | None = None
    module_id: str | None = None
    module_title: str | None = None
    module_order: int | None = None
    module_description: str | None = None
    module_learning_objectives: list[str] = Field(default_factory=list)
    difficulty: str
    position: int
    total_topics: int
    status: Literal["in_progress", "completed", "pending", "remediation"]
    prerequisites: list[str]


class LearningContent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    topic_id: str = Field(min_length=2, max_length=80)
    topic_title: str = Field(min_length=2, max_length=160)
    overview: str = Field(min_length=20, max_length=800)
    learning_objectives: list[str] = Field(min_length=2, max_length=6)
    explanation: str = Field(min_length=40, max_length=3000)
    key_concepts: list[str] = Field(min_length=2, max_length=8)
    examples: list[str] = Field(min_length=1, max_length=5)
    real_world_example: str | None = Field(default=None, max_length=1600)
    practical_example: str = Field(min_length=20, max_length=1600)
    common_mistakes: list[str] = Field(min_length=1, max_length=5)
    quick_recap: list[str] = Field(min_length=2, max_length=6)
    analogy: str | None = Field(default=None, max_length=900)
    code_example: str | None = Field(default=None, max_length=1800)
    coding_example: CodingExample | None = None
    prerequisites: list[str] = Field(default_factory=list, max_length=8)
    practice_suggestion: str | None = Field(default=None, max_length=1000)
    important_notes: list[str] = Field(default_factory=list, max_length=6)
    title: str | None = Field(default=None, min_length=2, max_length=160)
    introduction: str | None = Field(default=None, min_length=20, max_length=1200)
    why_it_matters: str | None = Field(default=None, min_length=20, max_length=1600)
    sections: list[LessonSection] = Field(default_factory=list, max_length=8)
    code_examples: list[LessonCodeExample] = Field(default_factory=list, max_length=5)
    common_mistake_details: list[LessonMistake] = Field(default_factory=list, max_length=6)
    key_takeaways: list[str] = Field(default_factory=list, max_length=8)
    self_check: list[LessonSelfCheck] = Field(default_factory=list, max_length=6)
    important_points: list[str] = Field(default_factory=list, max_length=8)
    recommended_focus: list[str] = Field(default_factory=list, max_length=8)
    assessment_recommendation: str | None = Field(default=None, max_length=500)


class LearningContentResponse(BaseModel):
    learner_id: int
    content: LearningContent
    source: Literal["openrouter", "cache", "curated_fallback"]
    topic_status: Literal["in_progress", "completed", "pending", "remediation"]


AssessmentQuestionType = Literal[
    "mcq", "conceptual", "scenario", "code_output", "coding", "debugging", "comparison"
]


class GenerateAssessmentRequest(BaseModel):
    selected_types: list[AssessmentQuestionType] = Field(min_length=1, max_length=7)
    question_count: int = Field(default=7, ge=1, le=30)

    @model_validator(mode="after")
    def validate_selected_types(self) -> "GenerateAssessmentRequest":
        if len(self.selected_types) != len(set(self.selected_types)):
            raise ValueError("Assessment types must be unique")
        return self


class ConceptMasteryEvaluation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    concept: str = Field(min_length=2, max_length=100)
    mastery: float = Field(ge=0.0, le=1.0)


class OpenResponseEvaluation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    question_id: str = Field(min_length=2, max_length=80)
    score: float = Field(ge=0.0, le=10.0)
    strengths: list[str] = Field(max_length=5)
    missing_concepts: list[str] = Field(max_length=10)
    feedback: str = Field(min_length=10, max_length=1000)
    concept_mastery: list[ConceptMasteryEvaluation] = Field(max_length=10)


class OpenResponseEvaluationSet(BaseModel):
    model_config = ConfigDict(extra="forbid")

    evaluations: list[OpenResponseEvaluation] = Field(min_length=1, max_length=30)

    @model_validator(mode="after")
    def validate_evaluation_ids(self) -> "OpenResponseEvaluationSet":
        ids = [item.question_id for item in self.evaluations]
        if len(ids) != len(set(ids)):
            raise ValueError("Evaluation question IDs must be unique")
        return self


class AssessmentQuestion(BaseModel):
    model_config = ConfigDict(extra="forbid")

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
    model_config = ConfigDict(extra="forbid")

    questions: list[AssessmentQuestion] = Field(min_length=3, max_length=8)

    @model_validator(mode="after")
    def validate_question_set(self) -> "AssessmentQuestionSet":
        question_ids = [question.question_id for question in self.questions]
        if len(question_ids) != len(set(question_ids)):
            raise ValueError("Assessment question IDs must be unique")
        return self


class AssessmentTypesQuestion(BaseModel):
    model_config = ConfigDict(extra="forbid")

    question_id: str = Field(min_length=2, max_length=80)
    question_type: AssessmentQuestionType
    question: str = Field(min_length=10, max_length=1200)
    concept: str = Field(min_length=2, max_length=100)
    difficulty: Literal["beginner", "intermediate", "advanced"]
    points: int = Field(ge=1, le=10)
    options: list[str] | None = Field(default=None, min_length=4, max_length=4)
    correct_option: int | None = Field(default=None, ge=0)
    explanation: str | None = Field(default=None, min_length=5, max_length=800)
    code: str | None = Field(default=None, max_length=5000)
    starter_code: str | None = Field(default=None, max_length=5000)
    language: str | None = Field(default=None, max_length=30)
    rubric: list[str] = Field(default_factory=list, max_length=8)
    expected_concepts: list[str] = Field(default_factory=list, max_length=10)
    expected_output: str | None = Field(default=None, max_length=2000)
    function_name: str | None = Field(default=None, max_length=100)
    test_cases: list[dict[str, Any]] = Field(default_factory=list, max_length=20)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_type_fields(self) -> "AssessmentTypesQuestion":
        if self.question_type == "mcq":
            if not self.options or len(self.options) != 4 or self.correct_option is None:
                raise ValueError("MCQ questions require exactly four options and a correct option")
            if self.correct_option >= len(self.options):
                raise ValueError("correct_option must reference an available option")
        elif self.options or self.correct_option is not None:
            raise ValueError("Only MCQ questions may include answer options")
        if self.question_type in {"conceptual", "scenario", "comparison"}:
            if not self.rubric or not self.expected_concepts:
                raise ValueError("Open-response questions require rubric and expected concepts")
        if self.question_type == "code_output":
            if not self.code or self.expected_output is None:
                raise ValueError("Code-output questions require code and expected output")
        if self.question_type in {"coding", "debugging"}:
            if not self.language or not self.test_cases or not self.function_name:
                raise ValueError("Code tasks require language, function name and test cases")
            if self.question_type == "debugging" and (
                not self.rubric or not self.expected_concepts
            ):
                raise ValueError("Debugging questions require a rubric and expected concepts")
        return self


class AssessmentTypesQuestionSet(BaseModel):
    model_config = ConfigDict(extra="forbid")

    questions: list[AssessmentTypesQuestion] = Field(min_length=1, max_length=30)

    @model_validator(mode="after")
    def validate_question_set(self) -> "AssessmentTypesQuestionSet":
        ids = [question.question_id for question in self.questions]
        if len(ids) != len(set(ids)):
            raise ValueError("Assessment question IDs must be unique")
        return self


class AssessmentQuestionPublic(BaseModel):
    question_id: str
    question: str
    question_type: AssessmentQuestionType = "mcq"
    points: int = 1
    options: list[str] = Field(default_factory=list)
    concept: str
    difficulty: Literal["beginner", "intermediate", "advanced"]
    code: str | None = None
    starter_code: str | None = None
    language: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class AssessmentGenerateResponse(BaseModel):
    assessment_id: int
    learner_id: int
    course_id: int | None = None
    topic_id: str
    topic_title: str
    status: Literal["pending", "submitted"]
    questions: list[AssessmentQuestionPublic]
    source: Literal["openrouter", "cache", "curated_fallback"]
    selected_types: list[AssessmentQuestionType] = Field(default_factory=lambda: ["mcq"])
    question_count: int = 0
    saved_answers: dict[str, Any] = Field(default_factory=dict)


class AssessmentAnswer(BaseModel):
    question_id: str = Field(min_length=2, max_length=80)
    selected_option: int | None = Field(default=None, ge=0)
    learner_answer: str | dict[str, Any] | None = None

    @model_validator(mode="after")
    def require_answer(self) -> "AssessmentAnswer":
        if self.selected_option is None and self.learner_answer is None:
            raise ValueError("Provide a selected option or a learner answer")
        if self.selected_option is not None and self.learner_answer is not None:
            raise ValueError("Provide only one answer format per question")
        return self


class AssessmentSubmitRequest(BaseModel):
    answers: list[AssessmentAnswer] = Field(min_length=1, max_length=30)


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
    practice_suggestion: str | None = None
    remediation_source: Literal["openrouter", "deterministic_fallback", "persisted"] | None = None
    alternative_explanation: str | None = None
    example: str | None = None
    remediation_next_action: str | None = None


class AssessmentResultResponse(BaseModel):
    assessment_id: int
    learner_id: int
    course_id: int | None = None
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
    question_review: list[QuestionReviewItem] = Field(default_factory=list)
    total_points: int = 0
    earned_points: float = 0.0
    selected_types: list[AssessmentQuestionType] = Field(default_factory=lambda: ["mcq"])
    type_results: dict[str, dict[str, float]] = Field(default_factory=dict)
    ai_interpretation: dict[str, Any] | None = None
    question_results: list[dict[str, Any]] = Field(default_factory=list)


class LatestAssessmentSummary(BaseModel):
    topic_id: str | None
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


class DashboardTopicResponse(BaseModel):
    topic_id: str
    title: str
    course_id: int | None
    course_title: str | None
    status: Literal["completed", "current", "in_progress", "remediation", "pending"]
    completed_at: datetime | None = None
    lesson_completed: bool = False


class DashboardAssessmentItem(BaseModel):
    assessment_id: int
    topic_id: str | None
    course_id: int | None = None
    topic_title: str
    assessment_type: str
    percentage: float
    completed_at: datetime


class DashboardAssessmentPerformance(BaseModel):
    average_percentage: float | None
    latest_percentage: float | None
    completed_count: int
    recent_scores: list[DashboardAssessmentItem]


class DashboardActivityItem(BaseModel):
    activity_type: Literal[
        "topic_completed",
        "lesson_completed",
        "progress_updated",
        "assessment_completed",
        "tutor_message",
    ]
    title: str
    description: str
    occurred_at: datetime
    topic_id: str | None = None
    course_id: int | None = None
    assessment_id: int | None = None


class DashboardSummaryResponse(LearnerSummaryResponse):
    course_id: int | None
    course_title: str | None
    completed_topic_items: list[DashboardTopicResponse]
    current_topic: DashboardTopicResponse | None
    assessment_performance: DashboardAssessmentPerformance
    recent_activity: list[DashboardActivityItem]
    path_completed: bool
