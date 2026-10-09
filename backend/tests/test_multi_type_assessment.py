from collections.abc import Generator
from datetime import datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.config import settings
from app.database import Base, get_db
from app.main import app
from app.models import (
    Assessment,
    AssessmentQuestionRecord,
    AssessmentResponseRecord,
    Learner,
    SkillScore,
    Topic,
    TopicProgress,
    Weakness,
)
from app.schemas import (
    AssessmentTypesQuestionSet,
    ConceptMasteryEvaluation,
    OpenResponseEvaluation,
)
from app.seed_topics import seed_topics
from app.services import multi_type_assessment_service as multi
from app.services.learning_ai_service import LearningInterpretation, RemediationAid


ASSESSMENT_TYPES = [
    "mcq",
    "conceptual",
    "scenario",
    "code_output",
    "coding",
    "debugging",
    "comparison",
]


@pytest.fixture
def client(tmp_path) -> Generator[TestClient, None, None]:
    engine = create_engine(f"sqlite:///{tmp_path / 'multi-type-assessment.db'}")
    Base.metadata.create_all(bind=engine)
    with Session(engine) as database:
        seed_topics(database)

    def override_get_db() -> Generator[Session, None, None]:
        with Session(engine) as database:
            yield database

    app.dependency_overrides[get_db] = override_get_db
    app.state.multi_type_test_engine = engine
    yield TestClient(app)
    app.dependency_overrides.clear()
    del app.state.multi_type_test_engine
    engine.dispose()


def prepare_topic(client: TestClient, name: str = "Multi Type Learner") -> tuple[int, str]:
    learner = client.post(
        "/api/learners",
        json={
            "name": name,
            "experience_level": "beginner",
            "goal_key": "llm_apps",
        },
    ).json()
    path = client.post(
        f"/api/learners/{learner['id']}/learning-path/generate"
    ).json()
    topic_id = path["current_topic_id"]
    completed = client.post(
        f"/api/learners/{learner['id']}/topics/{topic_id}/complete"
    )
    assert completed.status_code == 200
    return learner["id"], topic_id


def mock_generation(monkeypatch, counter: list[int] | None = None) -> None:
    def generate(**kwargs):
        if counter is not None:
            counter.append(1)
        payload = kwargs["user_payload"]
        selected = payload["selected_types"]
        count = payload["requested_question_count"]
        with Session(app.state.multi_type_test_engine) as database:
            topic = database.get(Topic, payload["topic"]["id"])
            assert topic is not None
            seen = {
                multi._question_fingerprint(question)
                for question in payload.get("previous_questions_to_avoid", [])
            }
            questions = []
            for index in range(count):
                question_type = selected[index % len(selected)]
                candidate_index = index
                question = multi._fallback_question(
                    topic, question_type, candidate_index
                )
                while multi._question_fingerprint(question.question) in seen:
                    candidate_index += 1
                    question = multi._fallback_question(
                        topic, question_type, candidate_index
                    )
                seen.add(multi._question_fingerprint(question.question))
                questions.append(question)
        return kwargs["response_model"].model_validate(
            {"questions": [question.model_dump() for question in questions]}
        )

    monkeypatch.setattr(multi, "request_structured_json", generate)
    monkeypatch.setattr(settings, "openrouter_api_key", "test-key")


def test_one_structured_request_generates_all_seven_types_and_hides_keys(
    client: TestClient, monkeypatch
):
    learner_id, topic_id = prepare_topic(client)
    calls: list[int] = []
    mock_generation(monkeypatch, calls)

    response = client.post(
        f"/api/learners/{learner_id}/topics/{topic_id}/assessment/generate",
        json={"selected_types": ASSESSMENT_TYPES, "question_count": 7},
    )

    assert response.status_code == 200, response.text
    result = response.json()
    assert result["source"] == "openrouter"
    assert len(calls) == 1
    assert {question["question_type"] for question in result["questions"]} == set(
        ASSESSMENT_TYPES
    )
    for question in result["questions"]:
        assert "correct_option" not in question
        assert "explanation" not in question
        assert "rubric" not in question
        assert "expected_concepts" not in question
        assert "expected_output" not in question
        assert "test_cases" not in question

    with Session(app.state.multi_type_test_engine) as database:
        assessment = database.get(Assessment, result["assessment_id"])
        assert assessment is not None
        assert set(assessment.selected_types) == set(ASSESSMENT_TYPES)
        assert len(assessment.questions) == 7
        assert all(item.evaluation_data_json for item in assessment.questions)


def test_assessment_uses_persisted_generative_ai_course_topic(
    client: TestClient, monkeypatch
):
    monkeypatch.setattr(settings, "jwt_secret_key", "multi-type-assessment-test-secret")
    monkeypatch.setattr(settings, "openrouter_api_key", "")
    registered = client.post(
        "/api/auth/register",
        json={
            "name": "Fresh Generative AI Learner",
            "email": "fresh-generative-ai@example.com",
            "password": "multi-type-test-password",
        },
    )
    assert registered.status_code == 201
    headers = {
        "Authorization": f"Bearer {registered.json()['access_token']}"
    }
    learner_response = client.post(
        "/api/learners",
        headers=headers,
        json={
            "name": "Fresh Generative AI Learner",
            "experience_level": "beginner",
            "track_id": "generative_ai",
            "goal_key": "llm_apps",
        },
    )
    assert learner_response.status_code == 201, learner_response.text
    learner_id = learner_response.json()["id"]
    curriculum = client.post("/api/curriculum/generate", headers=headers)
    assert curriculum.status_code == 200, curriculum.text
    path = client.post(
        f"/api/learners/{learner_id}/learning-path/generate",
        headers=headers,
    )
    assert path.status_code == 200, path.text
    topic_id = path.json()["current_topic_id"]
    completed = client.post(
        f"/api/learners/{learner_id}/topics/{topic_id}/complete",
        headers=headers,
    )
    assert completed.status_code == 200, completed.text
    assert completed.json()["topic_id"] == topic_id
    current_path = client.get(
        f"/api/learners/{learner_id}/learning-path",
        headers=headers,
    )
    assert current_path.json()["current_topic_id"] == topic_id
    calls: list[int] = []
    mock_generation(monkeypatch, calls)
    generated = client.post(
        f"/api/learners/{learner_id}/topics/{topic_id}/assessment/generate",
        headers=headers,
        json={
            "selected_types": ["mcq", "scenario", "coding", "debugging"],
            "question_count": 4,
        },
    )
    assert generated.status_code == 200, generated.text
    body = generated.json()
    assert body["course_id"] == curriculum.json()["course_id"]
    assert body["topic_id"] == topic_id
    assert len(calls) == 1
    assert len(body["questions"]) == 4
    assert {question["question_type"] for question in body["questions"]} == {
        "mcq",
        "scenario",
        "coding",
        "debugging",
    }
    with Session(app.state.multi_type_test_engine) as database:
        assessment = database.get(Assessment, body["assessment_id"])
        topic = database.get(Topic, topic_id)
        assert assessment is not None and topic is not None
        assert topic.course_id == curriculum.json()["course_id"]
        assert assessment.selected_types == ["mcq", "scenario", "coding", "debugging"]

    def evaluate_responses(questions, _answers, _learner, _topic):
        return {
            question.question_id: OpenResponseEvaluation(
                question_id=question.question_id,
                score=0,
                strengths=[],
                missing_concepts=question.expected_concepts,
                feedback="Add a clearer technical explanation and justification.",
                concept_mastery=[
                    ConceptMasteryEvaluation(concept=concept, mastery=0.0)
                    for concept in question.expected_concepts
                ],
            )
            for question in questions
            if question.question_type in multi.SUBJECTIVE_TYPES | {"debugging"}
        }, "openrouter"

    def evaluate_sandbox(tasks):
        return (
            {
                task["question_id"]: multi.SandboxTaskResult(
                    question_id=task["question_id"],
                    passed=0,
                    total=len(task["test_cases"]),
                    feedback="Sandbox tests completed.",
                )
                for task in tasks
            },
            "sandbox",
        )

    monkeypatch.setattr(multi, "evaluate_open_responses", evaluate_responses)
    monkeypatch.setattr(multi, "evaluate_code_in_sandbox", evaluate_sandbox)
    monkeypatch.setattr(
        multi,
        "interpret_skill_results",
        lambda _learner, _overall, weak, _developing, _strong: (
            LearningInterpretation(
                summary="The evidence identifies practical areas to strengthen next.",
                focus_concepts=weak[:3],
            ),
            "openrouter",
        ),
    )
    monkeypatch.setattr(
        multi,
        "generate_remediation_aid",
        lambda _learner, topic, weak, _percentage, _deterministic: (
            RemediationAid(
                weak_concepts=weak[:1] or list(topic.concept_tags[:1]),
                explanation="Review the topic idea with one worked practical example.",
                alternative_explanation="Break the workflow into small decisions and verify each.",
                example="Check whether the chosen approach meets the stated requirements.",
                practice_suggestion="Complete one guided implementation before retrying.",
                next_action="Practice the weak area and reassess this topic.",
            ),
            "openrouter",
        ),
    )
    answers = []
    for question in body["questions"]:
        if question["question_type"] == "mcq":
            answer = {"selected_option": 0}
        elif question["question_type"] == "scenario":
            answer = {"learner_answer": "Use relevant evidence, explain the trade-off, and validate results."}
        elif question["question_type"] == "coding":
            answer = {"learner_answer": {"code": "def solve(value):\n    return value\n"}}
        else:
            answer = {
                "learner_answer": {
                    "code": "def solve(value):\n    return value\n",
                    "bug": "The return expression uses the wrong value.",
                    "explanation": "The implementation should return the requested transformed value.",
                }
            }
        answers.append({"question_id": question["question_id"], **answer})

    submitted = client.post(
        f"/api/learners/{learner_id}/assessments/{body['assessment_id']}/submit",
        headers=headers,
        json={"answers": answers},
    )
    assert submitted.status_code == 200, submitted.text
    result = submitted.json()
    assert result["course_id"] == curriculum.json()["course_id"]
    assert result["type_results"]["mcq"]["percentage"] == 100
    assert result["type_results"]["scenario"]["percentage"] == 0
    assert result["percentage"] < 80
    assert result["weak_concepts"]
    assert result["ai_interpretation"]["source"] == "openrouter"
    path_after = client.get(
        f"/api/learners/{learner_id}/learning-path?course_id={curriculum.json()['course_id']}",
        headers=headers,
    )
    assert path_after.status_code == 200
    assert path_after.json()["current_topic_id"] == topic_id
    dashboard = client.get(
        f"/api/learners/{learner_id}/summary",
        headers=headers,
    )
    assert dashboard.status_code == 200, dashboard.text
    assert dashboard.json()["latest_assessment"]["percentage"] == result["percentage"]
    assert dashboard.json()["weak_concepts"]
    persisted = client.get(
        f"/api/learners/{learner_id}/assessments/{body['assessment_id']}",
        headers=headers,
    )
    assert persisted.status_code == 200
    assert persisted.json()["question_results"] == result["question_results"]
    assert len(calls) == 1


def test_multi_type_resume_save_submit_and_persisted_result(
    client: TestClient, monkeypatch
):
    learner_id, topic_id = prepare_topic(client)
    calls: list[int] = []
    mock_generation(monkeypatch, calls)
    selected = ["mcq", "scenario", "coding", "debugging"]
    generated = client.post(
        f"/api/learners/{learner_id}/topics/{topic_id}/assessment/generate",
        json={"selected_types": selected, "question_count": 4},
    ).json()
    assert len(calls) == 1
    assert len(generated["questions"]) == 4

    repeated = client.post(
        f"/api/learners/{learner_id}/topics/{topic_id}/assessment/generate",
        json={"selected_types": selected, "question_count": 4},
    )
    assert repeated.status_code == 200
    assert repeated.json()["assessment_id"] == generated["assessment_id"]
    assert len(calls) == 1

    questions = generated["questions"]
    by_type = {question["question_type"]: question for question in questions}
    saved = client.put(
        f"/api/learners/{learner_id}/assessments/{generated['assessment_id']}/responses",
        json={
            "answers": [
                {
                    "question_id": by_type["scenario"]["question_id"],
                    "learner_answer": "Use retrieved evidence and validate its relevance.",
                }
            ]
        },
    )
    assert saved.status_code == 200, saved.text
    resumed = client.get(
        f"/api/learners/{learner_id}/assessments/{generated['assessment_id']}"
    )
    assert resumed.status_code == 200
    assert resumed.json()["saved_answers"][by_type["scenario"]["question_id"]]
    assert len(calls) == 1

    def evaluate_responses(questions, _answers, _learner, _topic):
        return {
            question.question_id: OpenResponseEvaluation(
                question_id=question.question_id,
                score=0,
                strengths=[],
                missing_concepts=question.expected_concepts,
                feedback="The response needs a more explicit explanation.",
                concept_mastery=[
                    ConceptMasteryEvaluation(concept=concept, mastery=0.0)
                    for concept in question.expected_concepts
                ],
            )
            for question in questions
            if question.question_type in multi.SUBJECTIVE_TYPES | {"debugging"}
        }, "openrouter"

    sandbox_tasks: list[dict] = []

    def evaluate_sandbox(tasks):
        sandbox_tasks.extend(tasks)
        return (
            {
                task["question_id"]: multi.SandboxTaskResult(
                    question_id=task["question_id"],
                    passed=len(task["test_cases"]) - 1,
                    total=len(task["test_cases"]),
                    feedback="Sandbox tests completed.",
                )
                for task in tasks
            },
            "sandbox",
        )

    monkeypatch.setattr(multi, "evaluate_open_responses", evaluate_responses)
    monkeypatch.setattr(multi, "evaluate_code_in_sandbox", evaluate_sandbox)
    monkeypatch.setattr(
        multi,
        "interpret_skill_results",
        lambda _learner, _overall, weak, _developing, _strong: (
            LearningInterpretation(
                summary="The evidence shows areas to strengthen before advancing.",
                focus_concepts=weak[:3],
            ),
            "openrouter",
        ),
    )
    remediation_calls: list[list[str]] = []

    def generate_remediation(_learner, topic, weak, _percentage, _deterministic):
        remediation_calls.append(weak)
        return (
            RemediationAid(
                weak_concepts=weak[:1] or list(topic.concept_tags[:1]),
                explanation="Review the concept with a focused example and check each step.",
                alternative_explanation="Try thinking about the task as a sequence of validated decisions.",
                example="Compare the output against the task requirements.",
                practice_suggestion="Complete one short applied exercise.",
                next_action="Reassess this topic after practice.",
            ),
            "openrouter",
        )

    monkeypatch.setattr(multi, "generate_remediation_aid", generate_remediation)
    answers = []
    for question in questions:
        kind = question["question_type"]
        if kind == "mcq":
            answer = {"selected_option": 0}
        elif kind == "scenario":
            answer = {"learner_answer": "Use evidence, explain the trade-off, and validate the result."}
        elif kind == "coding":
            answer = {"learner_answer": {"code": "def limit_topic_items(items, limit):\n    return items[:limit]\n"}}
        else:
            answer = {
                "learner_answer": {
                    "code": "def limit_topic_items(items, limit):\n    return items[:limit]\n",
                    "bug": "The slice starts at limit, so earlier items are discarded.",
                    "explanation": "The slice must begin at zero to return the first limit items.",
                }
            }
        answers.append({"question_id": question["question_id"], **answer})

    submitted = client.post(
        f"/api/learners/{learner_id}/assessments/{generated['assessment_id']}/submit",
        json={"answers": answers},
    )
    assert submitted.status_code == 200, submitted.text
    result = submitted.json()
    assert result["type_results"]["mcq"]["percentage"] == 100
    assert result["type_results"]["scenario"]["percentage"] == 0
    assert result["percentage"] < 80
    assert result["weak_concepts"]
    assert result["ai_interpretation"]["source"] == "openrouter"
    assert remediation_calls
    assert {task["language"] for task in sandbox_tasks} == {"python"}
    assert len(result["question_results"]) == 4

    with Session(app.state.multi_type_test_engine) as database:
        assessment = database.get(Assessment, generated["assessment_id"])
        assert assessment is not None
        assert assessment.status == "completed"
        assert assessment.earned_points == result["earned_points"]
        assert database.scalar(
            select(SkillScore).where(SkillScore.learner_id == learner_id)
        )
        assert database.scalar(
            select(Weakness).where(
                Weakness.learner_id == learner_id,
                Weakness.status == "open",
            )
        )
        assert len(
            database.scalars(
                select(AssessmentResponseRecord).join(AssessmentQuestionRecord).where(
                    AssessmentQuestionRecord.assessment_id == assessment.id
                )
            ).all()
        ) == 4

    persisted = client.get(
        f"/api/learners/{learner_id}/assessments/{generated['assessment_id']}"
    )
    assert persisted.status_code == 200
    assert persisted.json()["percentage"] == result["percentage"]
    assert persisted.json()["question_results"] == result["question_results"]
    assert len(calls) == 1

    regenerated = client.post(
        f"/api/learners/{learner_id}/topics/{topic_id}/assessment/generate",
        json={"selected_types": selected, "question_count": 4},
    )
    assert regenerated.status_code == 200, regenerated.text
    assert regenerated.json()["assessment_id"] != generated["assessment_id"]
    assert regenerated.json()["source"] == "openrouter"
    assert len(calls) == 2


def test_identical_generation_context_uses_artifact_cache(client: TestClient, monkeypatch):
    learner_id, topic_id = prepare_topic(client)
    calls: list[int] = []
    mock_generation(monkeypatch, calls)
    with Session(app.state.multi_type_test_engine) as database:
        learner = database.get(Learner, learner_id)
        topic = database.get(Topic, topic_id)
        assert learner is not None and topic is not None
        first, first_source = multi.generate_assessment(
            database, topic, learner, ["mcq", "scenario"], 2
        )
        second, second_source = multi.generate_assessment(
            database, topic, learner, ["mcq", "scenario"], 2
        )
    assert first_source == "openrouter"
    assert second_source == "cache"
    assert first == second
    assert len(calls) == 1


def test_weak_concept_triggers_remediation_even_when_type_score_is_high(
    client: TestClient, monkeypatch
):
    learner_id, topic_id = prepare_topic(client)
    monkeypatch.setattr(settings, "openrouter_api_key", "")
    generated = client.post(
        f"/api/learners/{learner_id}/topics/{topic_id}/assessment/generate",
        json={"selected_types": ["conceptual"], "question_count": 1},
    )
    assert generated.status_code == 200, generated.text
    question = generated.json()["questions"][0]

    def evaluate_responses(questions, _answers, _learner, _topic):
        return (
            {
                item.question_id: OpenResponseEvaluation(
                    question_id=item.question_id,
                    score=item.points,
                    strengths=["Explains the concept clearly"],
                    missing_concepts=[],
                    feedback="The explanation is clear, but its concept application needs review.",
                    concept_mastery=[
                        ConceptMasteryEvaluation(concept=concept, mastery=0.0)
                        for concept in item.expected_concepts
                    ],
                )
                for item in questions
            },
            "openrouter",
        )

    monkeypatch.setattr(multi, "evaluate_open_responses", evaluate_responses)
    monkeypatch.setattr(
        multi,
        "interpret_skill_results",
        lambda _learner, _overall, weak, _developing, _strong: (
            LearningInterpretation(
                summary="Review the concept application before moving ahead.",
                focus_concepts=weak[:3],
            ),
            "openrouter",
        ),
    )
    monkeypatch.setattr(
        multi,
        "generate_remediation_aid",
        lambda _learner, _topic, weak, _percentage, _deterministic: (
            RemediationAid(
                weak_concepts=weak,
                explanation="Practice applying this concept to a concrete example.",
                alternative_explanation="Break the application into smaller steps.",
                example="Check each step against the topic requirements.",
                practice_suggestion="Complete one focused practice question.",
                next_action="Reassess after reviewing the concept.",
            ),
            "openrouter",
        ),
    )

    submitted = client.post(
        f"/api/learners/{learner_id}/assessments/{generated.json()['assessment_id']}/submit",
        json={
            "answers": [
                {
                    "question_id": question["question_id"],
                    "learner_answer": "A clear explanation tied to the topic.",
                }
            ]
        },
    )

    assert submitted.status_code == 200, submitted.text
    result = submitted.json()
    assert result["type_results"]["conceptual"]["percentage"] == 100
    assert result["weak_concepts"]
    assert result["recommendation"]["action_type"] == "remediate"
    with Session(app.state.multi_type_test_engine) as database:
        progress = database.scalar(
            select(TopicProgress).where(
                TopicProgress.learner_id == learner_id,
                TopicProgress.topic_id == topic_id,
            )
        )
        assert progress is not None
        assert progress.status == "remediation"


def test_type_specific_generation_and_deterministic_code_output(client: TestClient, monkeypatch):
    learner_id, topic_id = prepare_topic(client)
    mock_generation(monkeypatch)
    generated = client.post(
        f"/api/learners/{learner_id}/topics/{topic_id}/assessment/generate",
        json={"selected_types": ["code_output"], "question_count": 1},
    )
    assert generated.status_code == 200, generated.text

    question = generated.json()["questions"][0]
    assert question["question_type"] == "code_output"
    with Session(app.state.multi_type_test_engine) as database:
        assessment = database.get(Assessment, generated.json()["assessment_id"])
        assert assessment is not None
        expected = assessment.questions_json[0]["expected_output"]

    monkeypatch.setattr(settings, "code_sandbox_url", "http://sandbox.test/run")
    monkeypatch.setattr(
        multi,
        "evaluate_code_in_sandbox",
        lambda tasks: (
            {
                tasks[0]["question_id"]: multi.SandboxTaskResult(
                    question_id=tasks[0]["question_id"],
                    passed=1,
                    total=1,
                    feedback="Python execution completed.",
                    actual_output=expected,
                )
            },
            "sandbox",
        ),
    )
    submitted = client.post(
        f"/api/learners/{learner_id}/assessments/{generated.json()['assessment_id']}/submit",
        json={
            "answers": [
                {
                    "question_id": question["question_id"],
                    "learner_answer": expected,
                }
            ]
        },
    )
    assert submitted.status_code == 200, submitted.text
    assert submitted.json()["percentage"] == 100
    assert submitted.json()["question_results"][0]["evaluation_source"] == "sandbox"


def test_ai_open_response_evaluation_is_batched_and_schema_validated(
    client: TestClient, monkeypatch
):
    learner_id, topic_id = prepare_topic(client)
    mock_generation(monkeypatch)
    generated = client.post(
        f"/api/learners/{learner_id}/topics/{topic_id}/assessment/generate",
        json={
            "selected_types": ["conceptual", "scenario", "comparison"],
            "question_count": 3,
        },
    ).json()
    with Session(app.state.multi_type_test_engine) as database:
        learner = database.get(Learner, learner_id)
        topic = database.get(Topic, topic_id)
        assessment = database.get(Assessment, generated["assessment_id"])
        assert learner is not None and topic is not None and assessment is not None
        question_set = AssessmentTypesQuestionSet.model_validate(
            {"questions": assessment.questions_json}
        )

    calls: list[dict] = []

    def evaluate(**kwargs):
        calls.append(kwargs["user_payload"])
        evaluations = [
            {
                "question_id": response["question_id"],
                "score": 1,
                "strengths": ["Identifies the key idea"],
                "missing_concepts": [],
                "feedback": "The explanation addresses the core idea clearly.",
                "concept_mastery": [
                    {"concept": concept, "mastery": 1.0}
                    for concept in response["expected_concepts"]
                ],
            }
            for response in kwargs["user_payload"]["responses"]
        ]
        return kwargs["response_model"].model_validate({"evaluations": evaluations})

    monkeypatch.setattr(multi, "request_structured_json", evaluate)
    answers = {
        question.question_id: "A relevant explanation with a technical reason."
        for question in question_set.questions
    }
    result, source = multi.evaluate_open_responses(
        question_set.questions, answers, learner, topic
    )
    assert source == "openrouter"
    assert len(calls) == 1
    assert set(result) == {question.question_id for question in question_set.questions}
    assert all(item.score == 1 for item in result.values())


def test_code_submission_fails_explicitly_without_external_sandbox(
    client: TestClient, monkeypatch
):
    learner_id, topic_id = prepare_topic(client)
    monkeypatch.setattr(settings, "openrouter_api_key", "")
    monkeypatch.setattr(settings, "code_sandbox_url", "")
    generated = client.post(
        f"/api/learners/{learner_id}/topics/{topic_id}/assessment/generate",
        json={"selected_types": ["coding"], "question_count": 1},
    ).json()
    question = generated["questions"][0]
    response = client.post(
        f"/api/learners/{learner_id}/assessments/{generated['assessment_id']}/submit",
        json={
            "answers": [
                {
                    "question_id": question["question_id"],
                    "learner_answer": {"code": "def limit_topic_items(items, limit):\n    return items[:limit]\n"},
                }
            ]
        },
    )
    assert response.status_code == 503
    assert "CODE_SANDBOX_URL" in response.json()["detail"]
    with Session(app.state.multi_type_test_engine) as database:
        assessment = database.get(Assessment, generated["assessment_id"])
        assert assessment is not None
        assert assessment.completed_at is None


def test_invalid_generated_set_uses_valid_fallback_and_cache_reuse(client: TestClient, monkeypatch):
    learner_id, topic_id = prepare_topic(client)
    calls: list[int] = []

    def malformed_generation(**_kwargs):
        calls.append(1)
        return AssessmentTypesQuestionSet(questions=[])

    monkeypatch.setattr(multi, "request_structured_json", malformed_generation)
    monkeypatch.setattr(settings, "openrouter_api_key", "test-key")
    payload = {"selected_types": ["mcq", "scenario"], "question_count": 2}
    response = client.post(
        f"/api/learners/{learner_id}/topics/{topic_id}/assessment/generate",
        json=payload,
    )
    assert response.status_code == 200, response.text
    assert response.json()["source"] == "curated_fallback"
    assert len(response.json()["questions"]) == 2
    assert len(calls) == 1

    # A second pending request resumes the persisted artifact without another provider call.
    resumed = client.post(
        f"/api/learners/{learner_id}/topics/{topic_id}/assessment/generate",
        json=payload,
    )
    assert resumed.status_code == 200
    assert resumed.json()["assessment_id"] == response.json()["assessment_id"]
    assert len(calls) == 1


def test_retake_avoids_previous_questions_and_sends_recent_history_to_ai(
    client: TestClient, monkeypatch
):
    learner_id, topic_id = prepare_topic(client, "Retake Learner")
    monkeypatch.setattr(settings, "openrouter_api_key", "")
    payload = {"selected_types": ["mcq"], "question_count": 2}

    def generate_and_complete() -> dict:
        generated = client.post(
            f"/api/learners/{learner_id}/topics/{topic_id}/assessment/generate",
            json=payload,
        )
        assert generated.status_code == 200, generated.text
        body = generated.json()
        with Session(app.state.multi_type_test_engine) as database:
            assessment = database.get(Assessment, body["assessment_id"])
            assert assessment is not None
            assessment.status = "completed"
            assessment.completed_at = datetime.utcnow()
            assessment.score = 0.5
            assessment.percentage = 50
            database.commit()
        return body

    first = generate_and_complete()
    second = generate_and_complete()
    first_questions = {item["question"] for item in first["questions"]}
    second_questions = {item["question"] for item in second["questions"]}
    assert first_questions.isdisjoint(second_questions)

    observed_payloads: list[dict] = []

    def generate_with_history(**kwargs):
        user_payload = kwargs["user_payload"]
        observed_payloads.append(user_payload)
        prior = user_payload["previous_questions_to_avoid"]
        with Session(app.state.multi_type_test_engine) as database:
            topic = database.get(Topic, topic_id)
            assert topic is not None
            candidate = next(
                multi._fallback_question(topic, "mcq", index)
                for index in range(20, 80)
                if multi._question_fingerprint(
                    multi._fallback_question(topic, "mcq", index).question
                )
                not in {
                    multi._question_fingerprint(question)
                    for question in prior
                }
            )
        return kwargs["response_model"].model_validate(
            {"questions": [candidate.model_dump()]}
        )

    monkeypatch.setattr(settings, "openrouter_api_key", "test-key")
    monkeypatch.setattr(multi, "request_structured_json", generate_with_history)
    ai_retake = client.post(
        f"/api/learners/{learner_id}/topics/{topic_id}/assessment/generate",
        json={"selected_types": ["mcq"], "question_count": 1},
    )

    assert ai_retake.status_code == 200, ai_retake.text
    assert ai_retake.json()["source"] == "openrouter"
    assert len(observed_payloads) == 1
    history = observed_payloads[0]["previous_questions_to_avoid"]
    assert len(history) == 4
    assert first_questions.union(second_questions).issubset(set(history))
    assert ai_retake.json()["questions"][0]["question"] not in set(history)


def test_assessment_ownership_is_enforced(client: TestClient, monkeypatch):
    learner_a, topic_a = prepare_topic(client, "Learner A")
    learner_b, _ = prepare_topic(client, "Learner B")
    monkeypatch.setattr(settings, "openrouter_api_key", "")
    assessment = client.post(
        f"/api/learners/{learner_a}/topics/{topic_a}/assessment/generate",
        json={"selected_types": ["mcq"], "question_count": 1},
    )
    assert assessment.status_code == 200

    unauthorized = client.get(
        f"/api/learners/{learner_b}/assessments/{assessment.json()['assessment_id']}"
    )
    assert unauthorized.status_code == 404


def test_latest_weak_assessment_is_reported_despite_prior_strong_skill(
    client: TestClient, monkeypatch
):
    learner_id, topic_id = prepare_topic(client, "Learner With Prior Evidence")
    with Session(app.state.multi_type_test_engine) as database:
        topic = database.get(Topic, topic_id)
        assert topic is not None
        concept = topic.concept_tags[0]
        database.add(
            SkillScore(
                learner_id=learner_id,
                concept=concept,
                score=1.0,
                evidence_count=1,
                confidence=0.8,
                source="diagnostic",
            )
        )
        database.commit()

    mock_generation(monkeypatch)
    monkeypatch.setattr(settings, "openrouter_api_key", "")
    generated = client.post(
        f"/api/learners/{learner_id}/topics/{topic_id}/assessment/generate",
        json={"selected_types": ["mcq"], "question_count": 1},
    )
    assert generated.status_code == 200, generated.text
    answers = [
        {"question_id": question["question_id"], "selected_option": 1}
        for question in generated.json()["questions"]
    ]
    submitted = client.post(
        f"/api/learners/{learner_id}/assessments/{generated.json()['assessment_id']}/submit",
        json={"answers": answers},
    )

    assert submitted.status_code == 200, submitted.text
    result = submitted.json()
    assert result["weak_concepts"] == [concept]
    assert concept.replace("_", " ") in result["recommendation"]["summary"]
    assert result["recommendation"]["action_type"] == "remediate"
