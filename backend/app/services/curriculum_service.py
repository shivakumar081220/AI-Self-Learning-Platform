import logging
from uuid import uuid4

from pydantic import ValidationError
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..config import settings
from ..models import Assessment, GeneratedCourse, Learner, SkillScore, Topic, TopicPrerequisite, TopicProgress, Weakness
from ..schemas import CurriculumModule, CurriculumTopic, GeneratedCurriculum
from ..topic_titles import display_topic_title
from ..track_catalog import TRACK_BY_ID, TRACK_CONCEPTS
from .ai_provider import AIProviderError, log_ai_fallback, request_structured_json


logger = logging.getLogger(__name__)

_FALLBACK_MODULE_TITLES = {
    "python_for_ai": [
        "Python Syntax and Core Types",
        "Control Flow and Reusable Functions",
        "Collections and Data Cleaning",
        "Numerical Computing and Features",
        "Reproducible AI Data Pipelines",
    ],
    "machine_learning": [
        "Data and Feature Foundations",
        "Supervised Learning",
        "Training and Optimization",
        "Validation and Generalization",
        "Evaluation and Error Analysis",
    ],
    "deep_learning": [
        "Tensor and Network Foundations",
        "Forward Computation",
        "Learning with Gradients",
        "Generalization and Regularization",
        "Training and Model Evaluation",
    ],
    "nlp": [
        "Text Preparation",
        "Text Representations",
        "NLP Task Modeling",
        "Language Representations",
        "NLP Evaluation",
    ],
    "generative_ai": [
        "Prompt and Context Foundations",
        "Reliable Structured Generation",
        "Generation Controls",
        "Grounded Applications",
        "Quality and Safety Evaluation",
    ],
    "llms": [
        "Tokens and Context",
        "Transformer Architecture",
        "Model Inference",
        "Structured LLM Applications",
        "Production Evaluation",
    ],
    "rag": [
        "Document Preparation",
        "Embedding and Retrieval",
        "Ranking and Search",
        "Grounded Answer Generation",
        "RAG Evaluation",
    ],
    "ai_agents": [
        "Validated Tool Interfaces",
        "Planning and Decomposition",
        "Stateful Orchestration",
        "Permissions and Guardrails",
        "Agent Reliability",
    ],
}

_CONCEPT_TITLES = {
    "variables_and_types": "Variables and Data Types",
    "control_flow": "Conditions and Loops",
    "data_structures": "Python Data Structures",
    "data_cleaning": "Data Cleaning",
    "numerical_computing": "Numerical Computing",
    "feature_preparation": "Feature Preparation",
    "reproducible_scripts": "Reproducible Scripts",
    "dataset_pipelines": "Dataset Pipelines",
    "training_data": "Training Data",
    "feature_engineering": "Feature Engineering",
    "supervised_learning": "Supervised Learning",
    "loss_functions": "Loss Functions",
    "model_optimization": "Model Optimization",
    "validation_sets": "Validation Sets",
    "evaluation_metrics": "Evaluation Metrics",
    "error_analysis": "Error Analysis",
    "neural_network_layers": "Neural Network Layers",
    "forward_pass": "Forward Pass",
    "activation_functions": "Activation Functions",
    "backpropagation": "Backpropagation",
    "gradient_descent": "Gradient Descent",
    "training_loops": "Training Loops",
    "model_evaluation": "Model Evaluation",
    "text_normalization": "Text Normalization",
    "tokenization": "Tokenization",
    "bag_of_words": "Bag-of-Words",
    "tf_idf": "TF-IDF",
    "text_classification": "Text Classification",
    "sequence_labeling": "Sequence Labeling",
    "word_embeddings": "Word Embeddings",
    "language_models": "Language Models",
    "precision_recall": "Precision and Recall",
    "nlp_evaluation": "NLP Evaluation",
    "prompt_design": "Prompt Design",
    "structured_outputs": "Structured Outputs",
    "generation_parameters": "Generation Parameters",
    "sampling": "Sampling",
    "grounding": "Grounding",
    "guardrails": "Guardrails",
    "quality_metrics": "Quality Metrics",
    "safety_evaluation": "Safety Evaluation",
    "context_windows": "Context Windows",
    "transformers": "Transformer Architecture",
    "attention": "Attention",
    "inference": "Inference",
    "decoding": "Decoding",
    "tool_calling": "Tool Calling",
    "latency": "Latency",
    "document_chunking": "Document Chunking",
    "metadata": "Document Metadata",
    "vector_search": "Vector Search",
    "retrieval_ranking": "Retrieval Ranking",
    "hybrid_search": "Hybrid Search",
    "grounded_generation": "Grounded Generation",
    "citations": "Citations",
    "retrieval_metrics": "Retrieval Metrics",
    "answer_faithfulness": "Answer Faithfulness",
    "tool_schemas": "Tool Schemas",
    "argument_validation": "Argument Validation",
    "task_decomposition": "Task Decomposition",
    "planning": "Agent Planning",
    "state_management": "State Management",
    "orchestration": "Orchestration",
    "permissions": "Permissions",
    "trajectory_evaluation": "Trajectory Evaluation",
    "agent_reliability": "Agent Reliability",
}

_CONCEPT_EXPLANATIONS = {
    "variables_and_types": "Variables give descriptive names to values; Python's int, float, str, and bool types represent counts, measurements, labels, and state.",
    "python_syntax": "Python uses indentation to define blocks, and expressions combine values and operators into results.",
    "functions": "Functions package a named transformation so data preparation and model evaluation can be reused consistently.",
    "control_flow": "Conditions and loops select which transformations run and repeat them across records or batches.",
    "data_structures": "Lists preserve ordered records, dictionaries map field names to values, and sets support unique membership checks.",
    "data_cleaning": "Data cleaning identifies missing, malformed, duplicate, or inconsistent values before they distort downstream analysis.",
    "numerical_computing": "Numerical computing represents data as arrays so consistent arithmetic can be applied efficiently across observations.",
    "feature_preparation": "Feature preparation converts source columns into model-ready numeric or categorical inputs without leaking target information.",
    "reproducible_scripts": "Reproducible scripts make data transformations repeatable by keeping inputs, parameters, and processing steps explicit.",
    "dataset_pipelines": "A dataset pipeline applies ordered, testable transformations and preserves a clear boundary between training and evaluation data.",
    "training_data": "Training examples pair input features with the target information a supervised model learns to predict.",
    "feature_engineering": "Feature engineering transforms raw columns into useful signals while avoiding leakage from validation or test outcomes.",
    "supervised_learning": "Supervised learning fits a function from labeled examples and measures whether it generalizes to unseen examples.",
    "loss_functions": "A loss function quantifies prediction error so an optimizer can compare parameter updates during training.",
    "model_optimization": "Optimization adjusts model parameters to reduce training loss while monitoring generalization rather than training score alone.",
    "validation_sets": "A validation set estimates performance during model selection without using the final test set for repeated tuning.",
    "overfitting": "Overfitting occurs when a model fits training-specific detail that fails to generalize to new observations.",
    "evaluation_metrics": "Evaluation metrics translate predictions into task-relevant measurements; the right metric depends on error costs and class balance.",
    "error_analysis": "Error analysis inspects incorrect predictions by slice or pattern to identify data, feature, or modeling improvements.",
    "tensors": "Tensors are multidimensional arrays whose shapes and devices determine how neural-network operations can be composed.",
    "neural_network_layers": "A neural-network layer transforms an input representation using learned weights and a selected operation.",
    "forward_pass": "A forward pass applies network layers in order to map inputs to predictions.",
    "activation_functions": "Activation functions add nonlinear transformations, allowing stacked layers to represent more than a single linear mapping.",
    "backpropagation": "Backpropagation applies the chain rule to calculate how each parameter contributed to a model's loss.",
    "gradient_descent": "Gradient descent updates parameters in the direction that locally reduces loss, scaled by a learning rate.",
    "regularization": "Regularization constrains model complexity so training-specific patterns are less likely to dominate predictions.",
    "generalization": "Generalization is a model's ability to perform on new data drawn from the intended task distribution.",
    "training_loops": "A training loop repeatedly performs forward computation, loss measurement, gradient calculation, and parameter updates.",
    "model_evaluation": "Model evaluation compares predictions with held-out labels using metrics aligned with the task.",
    "text_normalization": "Text normalization applies consistent, task-appropriate transformations while preserving distinctions that may carry meaning.",
    "tokenization": "Tokenization divides text into units that a model or downstream feature extractor can process.",
    "bag_of_words": "A bag-of-words representation counts vocabulary items while discarding word order.",
    "tf_idf": "TF-IDF upweights terms frequent in one document but uncommon across the collection.",
    "text_classification": "Text classification maps a text input to one or more labels using a learned decision rule.",
    "sequence_labeling": "Sequence labeling assigns a prediction to each token while preserving the original token sequence.",
    "word_embeddings": "Word embeddings map tokens to dense vectors whose learned geometry can represent useful contextual or semantic patterns.",
    "language_models": "Language models estimate token sequences and can support prediction, completion, or downstream text tasks.",
    "precision_recall": "Precision measures how many predicted positives are correct; recall measures how many actual positives are found.",
    "nlp_evaluation": "NLP evaluation combines task-specific metrics with representative examples and human review for linguistic quality.",
    "prompt_design": "Prompt design states the task, context, constraints, and expected output so generation can be evaluated.",
    "constraints": "Explicit constraints limit the response's scope, format, and unsupported claims.",
    "structured_outputs": "Structured outputs constrain model responses to a schema that application code can validate before use.",
    "generation_parameters": "Generation parameters control aspects of sampling and output length but do not guarantee factual correctness.",
    "sampling": "Sampling selects the next token from a model's probability distribution; settings change variation, not the evidence behind an answer.",
    "grounding": "Grounding supplies trusted evidence to a generated answer and checks that claims are supported by that evidence.",
    "guardrails": "Guardrails combine deterministic validation, bounded permissions, and clear recovery when generated output is unsafe or invalid.",
    "quality_metrics": "Quality metrics turn user and task requirements into measurable checks for relevance, correctness, and reliability.",
    "safety_evaluation": "Safety evaluation tests foreseeable misuse, sensitive outputs, and failures against explicit acceptance criteria.",
    "tokens": "Tokens are the units processed by a language model; tokenization determines input length and context use.",
    "context_windows": "A context window bounds the tokens available for a single model operation and requires deliberate context selection.",
    "attention": "Attention combines information from relevant sequence positions using query-key compatibility and weighted values.",
    "self_attention": "Self-attention relates tokens within one sequence so each representation can incorporate surrounding context.",
    "positional_encoding": "Positional information tells a transformer how token order differs when the same tokens appear in a different sequence.",
    "inference": "Inference runs a trained model on supplied inputs to produce predictions or generated tokens.",
    "decoding": "Decoding turns token probabilities into an output sequence using a defined selection strategy.",
    "tool_calling": "Tool calling connects model-proposed structured actions to application-controlled validation and execution.",
    "document_chunking": "Document chunking divides source material into retrievable units while balancing context, precision, and overlap.",
    "metadata": "Document metadata records attributes such as source, date, and access scope that support filtering and traceability.",
    "embeddings": "Embeddings map text into vectors so a retrieval system can rank semantically related content.",
    "vector_search": "Vector search ranks candidate vectors by a similarity measure, then returns source records for grounding.",
    "retrieval_ranking": "Retrieval ranking orders candidate passages using query relevance and additional quality signals.",
    "hybrid_search": "Hybrid search combines lexical matching with semantic retrieval to cover exact terms and related meanings.",
    "grounded_generation": "Grounded generation gives a model retrieved evidence and asks it to answer within that evidence boundary.",
    "citations": "Citations map answer claims back to source passages so readers can verify where evidence came from.",
    "retrieval_metrics": "Retrieval metrics measure whether relevant source material appears in the top-ranked results.",
    "answer_faithfulness": "Answer faithfulness checks whether generated claims are supported by retrieved context.",
    "tool_schemas": "Tool schemas define allowed action names and typed arguments that an application can validate.",
    "argument_validation": "Argument validation checks types, bounds, and permissions before any requested tool is executed.",
    "task_decomposition": "Task decomposition breaks a bounded goal into smaller steps with observable inputs and completion criteria.",
    "planning": "Planning selects an ordered set of actions while respecting available tools, constraints, and task state.",
    "state_management": "State management records the observations and decisions needed to continue or recover a multi-step workflow.",
    "orchestration": "Orchestration controls transitions between model reasoning, validated tools, results, and completion checks.",
    "permissions": "Permissions restrict each tool to the minimum actions and data required for its purpose.",
    "trajectory_evaluation": "Trajectory evaluation inspects the sequence of agent actions and observations, not only its final answer.",
    "agent_reliability": "Agent reliability measures task completion, valid tool use, recoverability, and adherence to boundaries.",
}


def _fallback_curriculum(
    learner: Learner, database: Session | None = None
) -> GeneratedCurriculum:
    goal = learner.goal_text
    track = TRACK_BY_ID.get(learner.track, TRACK_BY_ID["generative_ai"])
    skills = {
        item.concept: item.score
        for item in database.scalars(
            select(SkillScore).where(SkillScore.learner_id == learner.id)
        ).all()
    } if database else {}
    modules: list[CurriculumModule] = []
    previous_topic: str | None = None
    previous_module: str | None = None
    outline = list(zip(_FALLBACK_MODULE_TITLES[track.id], TRACK_CONCEPTS[track.id]))
    skipped_mastered_modules = 0
    if learner.experience_level != "beginner":
        for _, concepts in outline[:2]:
            if not all(skills.get(concept, 0.0) >= 0.85 for concept in concepts):
                break
            skipped_mastered_modules += 1
    skipped_mastered_modules = min(skipped_mastered_modules, len(outline) - 3)
    outline = outline[skipped_mastered_modules:]
    for index, (module_title, concept_pair) in enumerate(
        outline, start=skipped_mastered_modules
    ):
        topics: list[CurriculumTopic] = []
        for concept in concept_pair:
            topic_title = _CONCEPT_TITLES.get(
                concept, concept.replace("_", " ").title()
            )
            explanation = _CONCEPT_EXPLANATIONS.get(
                concept,
                f"{topic_title} is a core part of {track.name}. It connects the learner's data or task to a measurable result.",
            )
            topic = CurriculumTopic(
                title=topic_title,
                description=(
                    f"{explanation} Apply it to {goal} within the {track.name} track."
                ),
                learning_objectives=[
                    f"Explain {topic_title.lower()} in a {track.name} task",
                    f"Apply {topic_title.lower()} to the selected goal and check the result",
                ],
                difficulty=learner.experience_level,
                concepts=[concept],
                prerequisites=[previous_topic] if previous_topic else [],
                estimated_minutes=20 + index * 5,
            )
            topics.append(topic)
            previous_topic = topic.title
        module_skills = list(concept_pair)
        weak = [concept for concept in module_skills if skills.get(concept, 1.0) < 0.75]
        new_skills = [
            concept for concept in module_skills if skills.get(concept, 0.0) < 0.75
        ]
        modules.append(
            CurriculumModule(
                title=module_title,
                description=(
                    f"Build and apply {', '.join(_CONCEPT_TITLES.get(item, item.replace('_', ' ')).lower() for item in module_skills)} "
                    f"for {goal}. The module is tailored to a {learner.experience_level} {track.name} learner."
                ),
                learning_objectives=[
                    f"Explain and apply {', '.join(_CONCEPT_TITLES.get(item, item.replace('_', ' ')).lower() for item in module_skills)}",
                    f"Use these skills in a practical {track.name} task related to {goal}",
                ],
                difficulty=learner.experience_level,
                prerequisites=[previous_module] if previous_module else [],
                estimated_minutes=sum(topic.estimated_minutes for topic in topics) + 20,
                practical_exercises=[
                    f"Use {topics[0].title} and {topics[1].title} to complete a small {track.name} task for {goal}."
                ],
                assessment_objectives=[
                    f"Check a learner's ability to explain and apply {topic.title.lower()}"
                    for topic in topics
                ],
                skills_to_revise=weak,
                skills_to_learn=new_skills or [
                    f"Transfer {topic.title.lower()} to a new {track.name} use case"
                ],
                topics=topics,
            )
        )
        previous_module = module_title
    return GeneratedCurriculum(
        course_title=f"{track.name}: {goal}",
        description=(
            f"A {learner.experience_level}-level {track.name} course for {goal}, organized into "
            "ordered modules with focused topics, practical exercises, and assessment objectives."
            + (
                " Demonstrated foundational skills are omitted so the course can start at the next unmet module."
                if skipped_mastered_modules
                else ""
            )
        ),
        track_id=track.id,
        goal=goal,
        level=learner.experience_level,
        estimated_duration=f"{sum(module.estimated_minutes for module in modules)} minutes",
        learning_objectives=[
            track.learning_objective,
            f"Apply {track.name} concepts to {goal}",
            f"Evaluate a {track.name} workflow using task-appropriate quality checks",
        ],
        modules=modules,
    )


def _openrouter_curriculum(learner: Learner, database: Session) -> GeneratedCurriculum:
    skills = database.scalars(
        select(SkillScore).where(SkillScore.learner_id == learner.id)
    ).all()
    weaknesses = database.scalars(
        select(Weakness).where(
            Weakness.learner_id == learner.id,
            Weakness.status == "open",
        )
    ).all()
    assessments = database.scalars(
        select(Assessment)
        .where(
            Assessment.learner_id == learner.id,
            Assessment.completed_at.is_not(None),
        )
        .order_by(Assessment.completed_at.desc())
        .limit(5)
    ).all()
    completed_topics = [
        topic.title
        for progress in database.scalars(
            select(TopicProgress).where(
                TopicProgress.learner_id == learner.id,
                TopicProgress.status == "completed",
            )
        ).all()
        if (topic := database.get(Topic, progress.topic_id)) is not None
    ]
    existing_course = database.scalar(
        select(GeneratedCourse).where(GeneratedCourse.learner_id == learner.id)
    )
    global_topics = database.scalars(
        select(Topic).where(Topic.owner_user_id.is_(None), Topic.is_active.is_(True))
    ).all()
    relevant_global_topics = [
        topic
        for topic in global_topics
        if topic.goal_relevance.get(learner.track, 0) > 0
    ]
    if not relevant_global_topics:
        relevant_global_topics = global_topics
    owned_topics = database.scalars(
        select(Topic).where(
            Topic.owner_user_id == learner.user_id,
            Topic.track_id == learner.track,
            Topic.is_active.is_(True),
        )
    ).all()
    topic_catalog = [
        *relevant_global_topics,
        *owned_topics,
    ]
    weak_concepts = list(dict.fromkeys(
        [item.concept for item in weaknesses]
        + [item.concept for item in skills if item.score < 0.75]
    ))
    strong_concepts = [item.concept for item in skills if item.score >= 0.75]
    diagnostic_evidence = []
    for assessment in assessments:
        if assessment.assessment_type != "diagnostic":
            continue
        insights = (assessment.feedback_json or {}).get("concept_insights", [])
        diagnostic_evidence.append(
            {
                "score": round((assessment.score or 0.0) * 100, 1),
                "concept_results": [
                    {
                        "concept": item.get("concept"),
                        "percentage": item.get("percentage"),
                        "level": item.get("level"),
                    }
                    for item in insights
                    if isinstance(item, dict)
                    and item.get("concept")
                    and item.get("level") in {"weak", "developing", "strong"}
                ],
            }
        )
    topic_ids = [topic.id for topic in topic_catalog]
    prerequisite_edges = database.scalars(
        select(TopicPrerequisite).where(TopicPrerequisite.topic_id.in_(topic_ids))
    ).all()
    prerequisites_by_topic: dict[str, list[str]] = {}
    for edge in prerequisite_edges:
        prerequisites_by_topic.setdefault(edge.topic_id, []).append(edge.prerequisite_id)
    context = {
        "learner": {
            "goal": learner.goal_text,
            "experience_level": learner.experience_level,
            "track": learner.track,
            "track_name": TRACK_BY_ID.get(learner.track, TRACK_BY_ID["generative_ai"]).name,
            "track_prerequisites": TRACK_BY_ID.get(learner.track, TRACK_BY_ID["generative_ai"]).prerequisite_tracks,
            "completed_topics": completed_topics,
            "previous_track": existing_course.track_id if existing_course else None,
            "track_history": existing_course.track_history_json if existing_course else [],
            "target_outcome": learner.target_outcome,
            "preferred_learning_style": learner.preferred_learning_style,
            "skill_gaps": [
                {
                    "concept": item.concept,
                    "score": item.score,
                    "evidence_count": item.evidence_count,
                }
                for item in sorted(skills, key=lambda item: item.score)[:8]
            ],
            "weak_concepts": weak_concepts,
            "strong_concepts": strong_concepts,
            "diagnostic_evidence": diagnostic_evidence,
            "recent_assessments": [
                {
                    "assessment_type": item.assessment_type,
                    "topic_id": item.topic_id,
                    "score": item.score,
                    "percentage": item.percentage,
                    "completed_at": item.completed_at.isoformat() if item.completed_at else None,
                }
                for item in assessments
            ],
        },
        "track_concept_catalog": sorted({
            concept
            for pair in TRACK_CONCEPTS[learner.track]
            for concept in pair
        } | {
            concept
            for topic in topic_catalog
            for concept in topic.concept_tags
        }),
        "topic_catalog": [
            {
                "title": topic.title,
                "concepts": topic.concept_tags,
                "prerequisites": prerequisites_by_topic.get(topic.id, []),
            }
            for topic in topic_catalog
        ],
        "requirements": (
            "Generate a complete course with 3 to 8 ordered modules. Each module must include its title, "
            "description, objectives, prerequisites by exact module title, estimated duration, practical "
            "exercises, assessment objectives, skills_to_revise, skills_to_learn, and 1 to 8 nested lesson "
            "topics. Each topic must include objectives, exact prerequisites by topic title, difficulty, "
            "duration, and concepts from track_concept_catalog. Use diagnostic evidence, strong and weak "
            "concepts, completed topics, and recent assessments to adapt the sequence. Cover weak prerequisites "
            "before dependent topics. Keep the curriculum specific to the selected track and do not return IDs."
        ),
    }
    curriculum = request_structured_json(
        operation="curriculum_generation",
        system_prompt=(
            "Generate a complete personalized course for exactly the selected track_id and track_name. "
            "Use the learner goal, outcome, experience, diagnostic evidence, weak and strong skills, completed "
            "topics, and previous assessment results. Return ordered modules with nested lesson topics. Every "
            "module must contain a title, description, objectives, exact module prerequisites, estimated "
            "duration, practical exercises, assessment objectives, skills_to_revise, skills_to_learn, and "
            "its topics. Every topic must contain its own objectives, concepts, exact topic prerequisites, "
            "difficulty, and duration. Use only concepts in track_concept_catalog. Place weak prerequisites "
            "before dependent topics, and avoid reteaching demonstrated mastery unless needed as a prerequisite. "
            "Return only the exact schema fields with their declared JSON types; include all required properties, "
            "do not add unsupported properties, and do not create database IDs."
        ),
        user_payload=context,
        response_model=GeneratedCurriculum,
        temperature=0.4,
        max_tokens=6500,
    )
    if (
        curriculum.goal != learner.goal_text
        or curriculum.level != learner.experience_level
        or curriculum.track_id != learner.track
    ):
        raise ValueError("Curriculum does not match learner context")
    allowed_concepts = set(context["track_concept_catalog"])
    if any(
        concept not in allowed_concepts
        for topic in curriculum.topics
        for concept in topic.concepts
    ):
        raise ValueError("Curriculum contains concepts outside the selected track catalog")
    if any(
        not set(module.skills_to_revise + module.skills_to_learn).issubset(allowed_concepts)
        for module in curriculum.modules
    ):
        raise ValueError("Module skill targets must use supplied track concept identifiers")
    return curriculum


def generate_curriculum(
    learner: Learner, database: Session | None = None
) -> tuple[GeneratedCurriculum, str]:
    if settings.openrouter_api_key:
        try:
            if database is None:
                raise ValueError("A database session is required for personalized curriculum generation")
            return _openrouter_curriculum(learner, database), "openrouter"
        except (AIProviderError, ValidationError, ValueError) as error:
            logger.warning(
                "AI operation used deterministic fallback; operation=curriculum_generation reason=%s",
                type(error).__name__,
            )
    log_ai_fallback(
        "curriculum_generation",
        "provider_not_configured" if not settings.openrouter_api_key else "generation_failed",
    )
    return _fallback_curriculum(learner, database), "deterministic_fallback"


def persist_curriculum(database: Session, learner: Learner, user_id: int) -> tuple[GeneratedCourse, str]:
    existing = database.scalar(
        select(GeneratedCourse).where(
            GeneratedCourse.learner_id == learner.id,
            GeneratedCourse.track_id == learner.track,
            GeneratedCourse.goal == learner.goal_text,
            GeneratedCourse.level == learner.experience_level,
            GeneratedCourse.target_outcome == learner.target_outcome,
        )
    )
    if existing:
        return existing, "persisted"
    curriculum, source = generate_curriculum(learner, database)
    course = GeneratedCourse(
        user_id=user_id,
        learner_id=learner.id,
        title=curriculum.course_title,
        description=curriculum.description,
        goal=curriculum.goal,
        target_outcome=learner.target_outcome,
        level=curriculum.level,
        estimated_duration=curriculum.estimated_duration,
        learning_objectives_json=curriculum.learning_objectives,
        modules_json=[],
        track_id=curriculum.track_id,
        generation_source=source,
    )
    database.add(course)
    database.flush()
    generation_index = (
        database.scalar(select(func.count(Topic.id)).where(Topic.course_id == course.id)) or 0
    ) + 1
    topic_ids: dict[str, str] = {}
    module_ids = {module.title: uuid4().hex for module in curriculum.modules}
    for topic in curriculum.topics:
        topic_id = f"generated-{uuid4().hex}"
        topic_ids[topic.title] = topic_id
        database.add(
            Topic(
                id=topic_id,
                # Topic titles are globally unique; this internal suffix is removed from responses.
                title=f"{display_topic_title(topic.title)} · {course.id}-{generation_index}",
                description=topic.description,
                difficulty=topic.difficulty,
                concept_tags=topic.concepts,
                learning_objectives_json=topic.learning_objectives,
                estimated_minutes=topic.estimated_minutes,
                goal_relevance={"generated": 1.0},
                content_source=f"{source} curriculum topic",
                track_id=curriculum.track_id,
                is_active=True,
                owner_user_id=user_id,
                course_id=course.id,
            )
        )
    course.modules_json = [
        {
            "module_id": module_ids[module.title],
            "order": module_index + 1,
            "title": module.title,
            "description": module.description,
            "learning_objectives": module.learning_objectives,
            "difficulty": module.difficulty,
            "estimated_minutes": module.estimated_minutes,
            "practical_exercises": module.practical_exercises,
            "assessment_objectives": module.assessment_objectives,
            "skills_to_revise": module.skills_to_revise,
            "skills_to_learn": module.skills_to_learn,
            "prerequisites": [
                module_ids[prerequisite]
                for prerequisite in module.prerequisites
            ],
            "topic_ids": [topic_ids[topic.title] for topic in module.topics],
        }
        for module_index, module in enumerate(curriculum.modules)
    ]
    database.flush()
    previously_completed = database.scalars(
        select(TopicProgress)
        .join(Topic, Topic.id == TopicProgress.topic_id)
        .where(
            TopicProgress.learner_id == learner.id,
            TopicProgress.status == "completed",
            Topic.course_id != course.id,
        )
    ).all()
    completed_concepts = {
        concept
        for progress in previously_completed
        for concept in (progress.topic.concept_tags or [])
    }
    completed_by_concept = {
        concept: progress
        for progress in previously_completed
        for concept in (progress.topic.concept_tags or [])
    }
    for topic in database.scalars(
        select(Topic).where(Topic.course_id == course.id)
    ).all():
        concepts = set(topic.concept_tags or [])
        if not concepts or not concepts.issubset(completed_concepts):
            continue
        matching_history = [
            completed_by_concept[concept]
            for concept in concepts
            if concept in completed_by_concept
        ]
        database.add(
            TopicProgress(
                learner_id=learner.id,
                topic_id=topic.id,
                status="completed",
                lesson_completed=True,
                mastery_score=min(
                    (item.mastery_score for item in matching_history),
                    default=0.8,
                ),
                attempt_count=0,
                last_activity_at=max(
                    (
                        item.last_activity_at
                        for item in matching_history
                        if item.last_activity_at is not None
                    ),
                    default=None,
                ),
            )
        )
    for module in curriculum.modules:
        for topic in module.topics:
            for prerequisite_title in topic.prerequisites:
                database.add(
                    TopicPrerequisite(
                        topic_id=topic_ids[topic.title],
                        prerequisite_id=topic_ids[prerequisite_title],
                    )
                )
    database.commit()
    database.refresh(course)
    return course, source