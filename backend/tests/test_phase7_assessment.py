import json
from collections.abc import Generator
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.config import settings
from app.database import Base, get_db
from app.main import app
from app.models import Assessment, LearningPath, Recommendation, SkillScore, Topic, TopicProgress, Weakness
from app.seed_topics import seed_topics
from app.services import ai_provider, assessment_service
from app.services.assessment_service import QUESTION_BANK


class FakeAssessmentProvider:
    response_content = ""

    def __init__(self, **kwargs):
        self.chat = SimpleNamespace(
            completions=SimpleNamespace(create=self.create_completion)
        )

    def create_completion(self, **kwargs):
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content=self.response_content))]
        )


@pytest.fixture
def client(tmp_path) -> Generator[TestClient, None, None]:
    engine = create_engine(f"sqlite:///{tmp_path / 'phase7-api.db'}")
    Base.metadata.create_all(bind=engine)
    with Session(engine) as database:
        seed_topics(database)

    def override_get_db() -> Generator[Session, None, None]:
        with Session(engine) as database:
            yield database

    app.dependency_overrides[get_db] = override_get_db
    app.state.phase7_test_engine = engine
    yield TestClient(app)
    app.dependency_overrides.clear()
    del app.state.phase7_test_engine


def prepare_learned_topic(client: TestClient) -> tuple[dict, dict, str]:
    learner = client.post(
        "/api/learners",
        json={
            "name": "Assessment User",
            "experience_level": "beginner",
            "goal_key": "llm_apps",
        },
    ).json()
    path = client.post(f"/api/learners/{learner['id']}/learning-path/generate").json()
    topic_id = path["current_topic_id"]
    completed = client.post(f"/api/learners/{learner['id']}/topics/{topic_id}/complete")
    assert completed.status_code == 200
    return learner, path, topic_id


def generate_assessment(client: TestClient, learner_id: int, topic_id: str) -> dict:
    response = client.post(
        f"/api/learners/{learner_id}/topics/{topic_id}/assessment/generate"
    )
    assert response.status_code == 200
    return response.json()


def answers_for(assessment: dict, selected_option: int) -> list[dict]:
    return [
        {"question_id": question["question_id"], "selected_option": selected_option}
        for question in assessment["questions"]
    ]


def test_assessment_requires_learned_topic_and_hides_answer_keys(client: TestClient):
    learner = client.post(
        "/api/learners",
        json={"name": "Not Ready", "experience_level": "beginner", "goal_key": "rag"},
    ).json()
    path = client.post(f"/api/learners/{learner['id']}/learning-path/generate").json()
    blocked = client.post(
        f"/api/learners/{learner['id']}/topics/{path['current_topic_id']}/assessment/generate"
    )
    assert blocked.status_code == 400

    learner, _, topic_id = prepare_learned_topic(client)
    learner_id = learner["id"]
    generated = generate_assessment(client, learner_id, topic_id)
    assert generated["source"] == "curated_fallback"
    assert all("correct_option" not in question for question in generated["questions"])
    assert all("explanation" not in question for question in generated["questions"])


def test_generated_topic_with_one_concept_gets_three_fallback_questions():
    topic = Topic(
        id="generated-one-concept",
        title="Agent Planning",
        description="Plan a bounded sequence of tool calls for an AI agent.",
        difficulty="intermediate",
        concept_tags=["agent_planning"],
    )

    question_set = assessment_service._fallback_questions(topic)

    assert len(question_set.questions) == 3
    assert len({question.question_id for question in question_set.questions}) == 3
    assert {question.concept for question in question_set.questions} == {"agent_planning"}


def test_assessment_endpoint_falls_back_for_generated_one_concept_topic(
    client: TestClient, monkeypatch
):
    learner = client.post(
        "/api/learners",
        json={"name": "Generated Topic", "experience_level": "beginner", "goal_key": "ai_agents"},
    ).json()
    topic_id = "generated-one-concept"
    with Session(app.state.phase7_test_engine) as database:
        topic = Topic(
            id=topic_id,
            title="Agent Planning",
            description="Plan a bounded sequence of tool calls for an AI agent.",
            difficulty="beginner",
            concept_tags=["agent_planning"],
            content_source="AI-generated learner curriculum",
        )
        database.add(topic)
        database.add(
            LearningPath(
                learner_id=learner["id"],
                goal=learner["goal_text"],
                path_json=[{"topic_id": topic_id, "title": topic.title}],
                overall_rationale="Generated one-concept topic test",
                current_index=0,
            )
        )
        database.add(TopicProgress(learner_id=learner["id"], topic_id=topic_id, status="completed"))
        database.commit()

    def reject_request(**kwargs):
        raise RuntimeError("AuthenticationError")

    class RejectedProvider:
        def __init__(self, **kwargs):
            self.chat = SimpleNamespace(completions=SimpleNamespace(create=reject_request))

    monkeypatch.setattr(settings, "openrouter_api_key", "invalid-test-key")
    monkeypatch.setattr(ai_provider, "OpenAI", RejectedProvider)

    generated = client.post(
        f"/api/learners/{learner['id']}/topics/{topic_id}/assessment/generate"
    )

    assert generated.status_code == 200, generated.text
    assert generated.json()["source"] == "curated_fallback"
    assert len(generated.json()["questions"]) == 3


def test_missing_key_and_invalid_ai_output_use_curated_questions(client: TestClient, monkeypatch):
    learner, _, topic_id = prepare_learned_topic(client)
    monkeypatch.setattr(settings, "openrouter_api_key", "")
    missing = generate_assessment(client, learner["id"], topic_id)
    assert missing["source"] == "curated_fallback"

    monkeypatch.setattr(settings, "openrouter_api_key", "test-key")
    FakeAssessmentProvider.response_content = json.dumps({"questions": []})
    monkeypatch.setattr(ai_provider, "OpenAI", FakeAssessmentProvider)
    invalid = generate_assessment(client, learner["id"], topic_id)
    assert invalid["source"] == "curated_fallback"


def test_mocked_openrouter_assessment_is_validated(client: TestClient, monkeypatch):
    learner, _, topic_id = prepare_learned_topic(client)
    FakeAssessmentProvider.response_content = json.dumps({"questions": QUESTION_BANK[topic_id]})
    monkeypatch.setattr(settings, "openrouter_api_key", "test-key")
    monkeypatch.setattr(ai_provider, "OpenAI", FakeAssessmentProvider)

    generated = generate_assessment(client, learner["id"], topic_id)

    assert generated["source"] == "openrouter"
    assert len(generated["questions"]) == 3


def test_weak_result_persists_skills_weakness_recommendation_and_remediation(client: TestClient):
    learner, _, topic_id = prepare_learned_topic(client)
    generated = generate_assessment(client, learner["id"], topic_id)
    result = client.post(
        f"/api/learners/{learner['id']}/assessments/{generated['assessment_id']}/submit",
        json={"answers": answers_for(generated, 1)},
    )

    assert result.status_code == 200
    body = result.json()
    assert body["percentage"] == 0
    assert body["weak_concepts"]
    assert body["recommendation"]["action_type"] == "remediate"
    assert topic_id == body["recommendation"]["target_topic_id"]
    assert "simpler" in body["recommendation"]["next_action"]
    with Session(app.state.phase7_test_engine) as database:
        weakness = database.scalar(select(Weakness).where(Weakness.learner_id == learner["id"]))
        progress = database.scalar(
            select(TopicProgress).where(
                TopicProgress.learner_id == learner["id"], TopicProgress.topic_id == topic_id
            )
        )
        recommendation = database.scalar(
            select(Recommendation).where(Recommendation.learner_id == learner["id"])
        )
        assert weakness.status == "open"
        assert progress.status == "remediation"
        assert recommendation.action_type == "remediate"


def test_summary_and_persisted_result_ignore_recommendations_outside_active_course(client: TestClient):
    learner, _, topic_id = prepare_learned_topic(client)
    generated = generate_assessment(client, learner["id"], topic_id)
    submitted = client.post(
        f"/api/learners/{learner['id']}/assessments/{generated['assessment_id']}/submit",
        json={"answers": answers_for(generated, 1)},
    )
    assert submitted.status_code == 200
    current_recommendation = submitted.json()["recommendation"]

    with Session(app.state.phase7_test_engine) as database:
        unrelated_topic = Topic(
            id="another-course-topic",
            title="Topic from another course",
            description="An unrelated course topic.",
            difficulty="beginner",
            concept_tags=[],
            goal_relevance={},
            content_source="test",
        )
        database.add(unrelated_topic)
        database.flush()
        database.add(
            Recommendation(
                learner_id=learner["id"],
                action_type="continue",
                topic_id=unrelated_topic.id,
                reason="This recommendation belongs to another course.",
            )
        )
        database.commit()

    summary = client.get(f"/api/learners/{learner['id']}/summary").json()
    persisted = client.get(
        f"/api/learners/{learner['id']}/assessments/{generated['assessment_id']}"
    ).json()

    assert summary["recommendation"]["target_topic_id"] == current_recommendation["target_topic_id"]
    assert persisted["recommendation"]["target_topic_id"] == current_recommendation["target_topic_id"]


def test_retry_after_weak_result_creates_different_questions_for_same_topic(
    client: TestClient, monkeypatch
):
    learner, _, topic_id = prepare_learned_topic(client)
    learner_id = learner["id"]
    monkeypatch.setattr(settings, "openrouter_api_key", "")
    first = generate_assessment(client, learner_id, topic_id)
    submitted = client.post(
        f"/api/learners/{learner_id}/assessments/{first['assessment_id']}/submit",
        json={"answers": answers_for(first, 1)},
    )
    assert submitted.status_code == 200
    assert submitted.json()["recommendation"]["action_type"] == "remediate"

    retry = client.post(
        f"/api/learners/{learner_id}/topics/{topic_id}/assessment/generate"
    )

    assert retry.status_code == 200, retry.text
    second = retry.json()
    assert second["topic_id"] == topic_id
    assert {item["question"] for item in second["questions"]}.isdisjoint(
        {item["question"] for item in first["questions"]}
    )


def test_strong_result_advances_and_updates_path(client: TestClient):
    learner, _, topic_id = prepare_learned_topic(client)
    generated = generate_assessment(client, learner["id"], topic_id)
    result = client.post(
        f"/api/learners/{learner['id']}/assessments/{generated['assessment_id']}/submit",
        json={"answers": answers_for(generated, 0)},
    )

    assert result.status_code == 200
    body = result.json()
    assert body["percentage"] == 100
    assert body["strong_concepts"]
    assert body["recommendation"]["action_type"] == "continue"
    assert body["recommendation"]["target_topic_id"] != topic_id
    with Session(app.state.phase7_test_engine) as database:
        progress = database.scalar(
            select(TopicProgress).where(
                TopicProgress.learner_id == learner["id"], TopicProgress.topic_id == topic_id
            )
        )
        path = database.scalar(
            select(LearningPath).where(LearningPath.learner_id == learner["id"])
        )
        assert progress.status == "completed"
        assert path.path_json[path.current_index]["topic_id"] != topic_id


def test_invalid_answers_duplicate_submission_and_persisted_result(client: TestClient):
    learner, _, topic_id = prepare_learned_topic(client)
    generated = generate_assessment(client, learner["id"], topic_id)
    invalid = client.post(
        f"/api/learners/{learner['id']}/assessments/{generated['assessment_id']}/submit",
        json={"answers": [{"question_id": "not-a-question", "selected_option": 0}]},
    )
    assert invalid.status_code == 422

    result = client.post(
        f"/api/learners/{learner['id']}/assessments/{generated['assessment_id']}/submit",
        json={"answers": answers_for(generated, 0)},
    )
    assert result.status_code == 200
    duplicate = client.post(
        f"/api/learners/{learner['id']}/assessments/{generated['assessment_id']}/submit",
        json={"answers": answers_for(generated, 0)},
    )
    assert duplicate.status_code == 409
    reloaded = client.get(
        f"/api/learners/{learner['id']}/assessments/{generated['assessment_id']}"
    )
    assert reloaded.status_code == 200
    assert reloaded.json()["percentage"] == result.json()["percentage"]
    assert reloaded.json()["question_review"] == result.json()["question_review"]
    assert all("correct_option" in question for question in reloaded.json()["question_review"])


def test_skill_update_uses_historical_weighting(client: TestClient):
    learner, _, topic_id = prepare_learned_topic(client)
    generated = generate_assessment(client, learner["id"], topic_id)
    result = client.post(
        f"/api/learners/{learner['id']}/assessments/{generated['assessment_id']}/submit",
        json={"answers": answers_for(generated, 0)},
    ).json()
    first_score = result["concept_results"][0]["score"]

    with Session(app.state.phase7_test_engine) as database:
        skill = database.scalar(
            select(SkillScore).where(
                SkillScore.learner_id == learner["id"],
                SkillScore.concept == result["concept_results"][0]["concept"],
            )
        )
        assert skill.score == first_score
