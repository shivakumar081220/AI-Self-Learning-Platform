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
    AIArtifactCache,
    Assessment,
    AssessmentQuestionRecord,
    AssessmentResponseRecord,
    GeneratedCourse,
    Learner,
    Recommendation,
    SkillScore,
    Topic,
    TopicProgress,
    TutorConversation,
    TutorMessage,
    User,
    Weakness,
)
from app.schemas import TutorResponsePayload
from app.seed_topics import seed_topics
from app.security import verify_password
from app.routers import learners as learners_router
from app.services import curriculum_service


def test_authenticated_persistence_journey_survives_engine_reconstruction(
    tmp_path, monkeypatch
):
    database_url = f"sqlite:///{tmp_path / 'persistence-journey.db'}"
    connect_args = {"check_same_thread": False}
    engine_ref = {
        "engine": create_engine(database_url, connect_args=connect_args)
    }
    Base.metadata.create_all(bind=engine_ref["engine"])
    with Session(engine_ref["engine"]) as database:
        seed_topics(database)

    monkeypatch.setattr(settings, "jwt_secret_key", "persistence-test-secret")
    monkeypatch.setattr(settings, "openrouter_api_key", "")

    def override_get_db() -> Generator[Session, None, None]:
        with Session(engine_ref["engine"]) as database:
            yield database

    app.dependency_overrides[get_db] = override_get_db
    client = TestClient(app)
    try:
        registered = client.post(
            "/api/auth/register",
            json={
                "name": "Persistence Learner",
                "email": "persistence@example.test",
                "password": "persist-test-password",
            },
        )
        assert registered.status_code == 201, registered.text
        user_id = registered.json()["user"]["id"]
        headers = {
            "Authorization": f"Bearer {registered.json()['access_token']}"
        }
        duplicate = client.post(
            "/api/auth/register",
            json={
                "name": "Duplicate",
                "email": "PERSISTENCE@example.test",
                "password": "persist-test-password",
            },
        )
        assert duplicate.status_code == 409
        with Session(engine_ref["engine"]) as database:
            user = database.get(User, user_id)
            assert user is not None
            assert user.password_hash != "persist-test-password"
            assert verify_password("persist-test-password", user.password_hash)

        profile = client.post(
            "/api/learners",
            headers=headers,
            json={
                "name": "Persistence Learner",
                "experience_level": "beginner",
                "goal_key": "rag",
                "track_id": "rag",
                "target_outcome": "Build a grounded question-answering app",
            },
        )
        assert profile.status_code == 201, profile.text
        learner_id = profile.json()["id"]
        updated = client.put(
            "/api/learners/me",
            headers=headers,
            json={
                "name": "Persistence Learner Updated",
                "experience_level": "intermediate",
                "goal_key": "rag",
                "track_id": "rag",
                "target_outcome": "Ship a reliable RAG app",
            },
        )
        assert updated.status_code == 200, updated.text
        assert client.post(
            "/api/auth/login",
            json={
                "email": "persistence@example.test",
                "password": "persist-test-password",
            },
        ).status_code == 200
        assert client.get("/api/learners/me", headers=headers).json()[
            "experience_level"
        ] == "intermediate"

        diagnostic = client.post(
            f"/api/learners/{learner_id}/diagnostic", headers=headers
        )
        assert diagnostic.status_code == 200, diagnostic.text
        diagnostic_body = diagnostic.json()
        assert all(
            "correct_option" not in question
            for question in diagnostic_body["questions"]
        )
        with Session(engine_ref["engine"]) as database:
            diagnostic_record = database.get(
                Assessment, diagnostic_body["assessment_id"]
            )
            assert diagnostic_record is not None
            diagnostic_answers = [
                {
                    "question_id": question["id"],
                    "selected_option": (
                        question["correct_option"] + 1
                    ) % len(question["options"]),
                }
                for question in diagnostic_record.questions_json
            ]
        diagnostic_result = client.post(
            f"/api/learners/{learner_id}/diagnostic/"
            f"{diagnostic_body['assessment_id']}/submit",
            headers=headers,
            json={"answers": diagnostic_answers},
        )
        assert diagnostic_result.status_code == 200, diagnostic_result.text
        assert diagnostic_result.json()["overall_percentage"] == 0
        with Session(engine_ref["engine"]) as database:
            saved_diagnostic = database.get(
                Assessment, diagnostic_body["assessment_id"]
            )
            assert saved_diagnostic is not None
            assert saved_diagnostic.completed_at is not None
            assert len(saved_diagnostic.answers_json) == len(diagnostic_answers)
            assert database.scalar(
                select(SkillScore).where(
                    SkillScore.learner_id == learner_id,
                    SkillScore.score == 0,
                )
            ) is not None

        generation_calls = []
        actual_generate_curriculum = curriculum_service.generate_curriculum

        def counted_generate_curriculum(*args, **kwargs):
            generation_calls.append(1)
            return actual_generate_curriculum(*args, **kwargs)

        monkeypatch.setattr(
            curriculum_service, "generate_curriculum", counted_generate_curriculum
        )
        curriculum = client.post("/api/curriculum/generate", headers=headers)
        assert curriculum.status_code == 200, curriculum.text
        assert len(generation_calls) == 1
        course_id = curriculum.json()["course_id"]
        original_module_ids = [
            module["module_id"] for module in curriculum.json()["modules"]
        ]
        current_course = client.get("/api/curriculum/current", headers=headers)
        assert current_course.status_code == 200
        assert current_course.json()["course_id"] == course_id
        assert [
            module["module_id"] for module in current_course.json()["modules"]
        ] == original_module_ids
        repeated_generation = client.post(
            "/api/curriculum/generate", headers=headers
        )
        assert repeated_generation.status_code == 200
        assert repeated_generation.json()["course_id"] == course_id
        assert len(generation_calls) == 1
        with Session(engine_ref["engine"]) as database:
            course = database.get(GeneratedCourse, course_id)
            assert course is not None and course.learner_id == learner_id
            assert len(course.modules_json) >= 2
            course_topic_ids = {
                topic.id
                for topic in database.scalars(
                    select(Topic).where(Topic.course_id == course_id)
                ).all()
            }
            assert course_topic_ids
            assert {
                topic_id
                for module in course.modules_json
                for topic_id in module["topic_ids"]
            } == course_topic_ids

        path = client.get(
            f"/api/learners/{learner_id}/learning-path",
            headers=headers,
            params={"course_id": course_id},
        )
        assert path.status_code == 200, path.text
        topic_id = path.json()["current_topic_id"]
        lesson = client.get(
            f"/api/learners/{learner_id}/topics/{topic_id}/content",
            headers=headers,
        )
        assert lesson.status_code == 200, lesson.text
        saved_lesson = lesson.json()["content"]
        assert saved_lesson["topic_id"] == topic_id
        lesson_again = client.get(
            f"/api/learners/{learner_id}/topics/{topic_id}/content",
            headers=headers,
        )
        assert lesson_again.status_code == 200
        assert lesson_again.json()["content"] == saved_lesson
        with Session(engine_ref["engine"]) as database:
            artifacts_before = database.scalar(
                select(AIArtifactCache).where(
                    AIArtifactCache.learner_id == learner_id,
                    AIArtifactCache.operation == "learning_content",
                )
            )
            assert artifacts_before is not None
            assert artifacts_before.result_json["topic_id"] == topic_id
            assert artifacts_before.status == "fallback"

        completion = client.post(
            f"/api/learners/{learner_id}/topics/{topic_id}/complete",
            headers=headers,
        )
        assert completion.status_code == 200, completion.text
        assessment = client.post(
            f"/api/learners/{learner_id}/topics/{topic_id}/assessment/generate",
            headers=headers,
        )
        assert assessment.status_code == 200, assessment.text
        assessment_body = assessment.json()
        with Session(engine_ref["engine"]) as database:
            assessment_record = database.get(
                Assessment, assessment_body["assessment_id"]
            )
            assert assessment_record is not None
            submitted_answers = [
                {
                    "question_id": question["question_id"],
                    "selected_option": (
                        question["correct_option"] + 1
                    ) % len(question["options"]),
                }
                for question in assessment_record.questions_json
            ]
        assert all(
            "correct_option" not in question
            for question in assessment_body["questions"]
        )
        result = client.post(
            f"/api/learners/{learner_id}/assessments/"
            f"{assessment_body['assessment_id']}/submit",
            headers=headers,
            json={"answers": submitted_answers},
        )
        assert result.status_code == 200, result.text
        assert result.json()["percentage"] == 0
        assert result.json()["weak_concepts"]
        with Session(engine_ref["engine"]) as database:
            saved_assessment = database.get(
                Assessment, assessment_body["assessment_id"]
            )
            assert saved_assessment is not None
            assert saved_assessment.completed_at is not None
            assert saved_assessment.answers_json
            assert database.scalar(
                select(Weakness).where(Weakness.learner_id == learner_id)
            ) is not None
            assert database.scalar(
                select(Recommendation).where(
                    Recommendation.learner_id == learner_id
                )
            ) is not None
            assert database.scalar(
                select(TopicProgress).where(
                    TopicProgress.learner_id == learner_id,
                    TopicProgress.topic_id == topic_id,
                )
            ) is not None

        topic_assessment_ids = [assessment_body["assessment_id"]]
        for _ in range(2):
            retake = client.post(
                f"/api/learners/{learner_id}/topics/{topic_id}/assessment/generate",
                headers=headers,
            )
            assert retake.status_code == 200, retake.text
            assert retake.json()["assessment_id"] not in topic_assessment_ids
            topic_assessment_ids.append(retake.json()["assessment_id"])
            with Session(engine_ref["engine"]) as database:
                retake_record = database.get(
                    Assessment, retake.json()["assessment_id"]
                )
                assert retake_record is not None
                correct_answers = [
                    {
                        "question_id": question["question_id"],
                        "selected_option": question["correct_option"],
                    }
                    for question in retake_record.questions_json
                ]
            retake_result = client.post(
                f"/api/learners/{learner_id}/assessments/"
                f"{retake.json()['assessment_id']}/submit",
                headers=headers,
                json={"answers": correct_answers},
            )
            assert retake_result.status_code == 200, retake_result.text
            assert retake_result.json()["percentage"] == 100
        with Session(engine_ref["engine"]) as database:
            assert database.scalar(
                select(Weakness).where(
                    Weakness.learner_id == learner_id,
                    Weakness.topic_id == topic_id,
                    Weakness.status == "resolved",
                )
            ) is not None
            assert len(
                database.scalars(
                    select(Assessment).where(
                        Assessment.learner_id == learner_id,
                        Assessment.topic_id == topic_id,
                    )
                ).all()
            ) == 3

        def tutor_reply(context, question, history, section_context, teaching_style):
            del context, history, section_context, teaching_style
            answer = f"Here is a lesson-based explanation of your question: {question}"
            return (
                TutorResponsePayload(
                    answer=answer,
                    direct_answer=answer,
                    teaching_approach="saved lesson explanation",
                    difficulty="intermediate",
                    related_concepts=[],
                    suggested_follow_up="Would you like a worked example?",
                ),
                "deterministic_fallback",
            )

        monkeypatch.setattr(
            learners_router, "generate_tutor_response", tutor_reply
        )
        conversation = client.post(
            f"/api/learners/{learner_id}/tutor/conversations",
            headers=headers,
            json={"topic_id": topic_id},
        )
        assert conversation.status_code == 201, conversation.text
        conversation_id = conversation.json()["id"]
        for prompt in ("Explain retrieval grounding", "Can you give an example?"):
            sent = client.post(
                f"/api/learners/{learner_id}/tutor/conversations/"
                f"{conversation_id}/messages",
                headers=headers,
                json={"content": prompt},
            )
            assert sent.status_code == 200, sent.text

        dashboard = client.get(
            f"/api/learners/{learner_id}/dashboard",
            headers=headers,
            params={"course_id": course_id},
        )
        assert dashboard.status_code == 200, dashboard.text
        assert dashboard.json()["assessment_performance"]["completed_count"] == 4
        assert dashboard.json()["recommendation"] is not None

        current_topic_before_reopen = client.get(
            f"/api/learners/{learner_id}/learning-path",
            headers=headers,
            params={"course_id": course_id},
        ).json()["current_topic_id"]
        engine_ref["engine"].dispose()
        engine_ref["engine"] = create_engine(
            database_url, connect_args=connect_args
        )
        logged_in = client.post(
            "/api/auth/login",
            json={
                "email": "persistence@example.test",
                "password": "persist-test-password",
            },
        )
        assert logged_in.status_code == 200, logged_in.text
        headers = {
            "Authorization": f"Bearer {logged_in.json()['access_token']}"
        }
        assert client.get("/api/learners/me", headers=headers).json()["id"] == learner_id
        restored_course = client.get("/api/curriculum/current", headers=headers)
        assert restored_course.json()["course_id"] == course_id
        assert [
            module["module_id"] for module in restored_course.json()["modules"]
        ] == original_module_ids
        restored_path = client.get(
            f"/api/learners/{learner_id}/learning-path",
            headers=headers,
            params={"course_id": course_id},
        )
        assert restored_path.status_code == 200
        assert (
            restored_path.json()["current_topic_id"] == current_topic_before_reopen
        )
        assert client.get(
            f"/api/learners/{learner_id}/topics/{topic_id}/content",
            headers=headers,
        ).json()["content"] == saved_lesson
        assert client.get(
            f"/api/learners/{learner_id}/assessments/"
            f"{assessment_body['assessment_id']}",
            headers=headers,
        ).json()["percentage"] == 0
        restored_conversation = client.get(
            f"/api/learners/{learner_id}/tutor/conversations/{conversation_id}",
            headers=headers,
        )
        assert restored_conversation.status_code == 200
        assert [message["role"] for message in restored_conversation.json()["messages"]] == [
            "user",
            "assistant",
            "user",
            "assistant",
        ]
        resumed = client.post(
            f"/api/learners/{learner_id}/tutor/conversations/"
            f"{conversation_id}/messages",
            headers=headers,
            json={"content": "Continue with one more practical example"},
        )
        assert resumed.status_code == 200, resumed.text
        restored_dashboard = client.get(
            f"/api/learners/{learner_id}/dashboard",
            headers=headers,
            params={"course_id": course_id},
        )
        assert restored_dashboard.status_code == 200
        assert restored_dashboard.json()["recommendation"] is not None

        other_user = client.post(
            "/api/auth/register",
            json={
                "name": "Other Learner",
                "email": "other-persistence@example.test",
                "password": "other-test-password",
            },
        )
        other_headers = {
            "Authorization": f"Bearer {other_user.json()['access_token']}"
        }
        foreign_learner = client.post(
            "/api/learners",
            headers=other_headers,
            json={
                "name": "Other Learner",
                "experience_level": "beginner",
                "goal_key": "rag",
                "track_id": "python_for_ai",
            },
        )
        assert foreign_learner.status_code == 201
        assert client.get(
            f"/api/learners/{learner_id}/dashboard", headers=other_headers
        ).status_code == 403
        assert client.get(
            f"/api/learners/{learner_id}/tutor/conversations/{conversation_id}",
            headers=other_headers,
        ).status_code == 403

        with Session(engine_ref["engine"]) as database:
            assert database.get(Learner, learner_id) is not None
            assert database.get(GeneratedCourse, course_id) is not None
            assert database.scalar(
                select(AssessmentQuestionRecord).where(
                    AssessmentQuestionRecord.assessment_id
                    == assessment_body["assessment_id"]
                )
            ) is None
            assert database.scalar(
                select(AssessmentResponseRecord)
            ) is None
            assert database.scalar(
                select(TutorConversation).where(
                    TutorConversation.id == conversation_id
                )
            ) is not None
            assert len(
                database.scalars(
                    select(TutorMessage).where(
                        TutorMessage.conversation_id == conversation_id
                    )
                ).all()
            ) == 6
            assert datetime.utcnow() >= saved_assessment.completed_at
    finally:
        app.dependency_overrides.clear()
        engine_ref["engine"].dispose()


def test_curriculum_save_failure_rolls_back_course_and_generated_topics(
    tmp_path, monkeypatch
):
    engine = create_engine(f"sqlite:///{tmp_path / 'curriculum-rollback.db'}")
    Base.metadata.create_all(bind=engine)
    monkeypatch.setattr(settings, "openrouter_api_key", "")
    with Session(engine) as database:
        user = User(email="rollback@example.test", password_hash="test-hash")
        learner = Learner(
            name="Rollback Learner",
            experience_level="beginner",
            goal_text="Learn retrieval-augmented generation",
            track="rag",
        )
        user.learner = learner
        database.add(user)
        database.commit()
        user_id = user.id
        learner_id = learner.id

    with Session(engine) as database:
        learner = database.get(Learner, learner_id)
        assert learner is not None
        original_commit = database.commit

        def fail_after_course_rows_are_staged():
            staged_course = database.scalar(
                select(GeneratedCourse.id).where(
                    GeneratedCourse.learner_id == learner_id
                )
            )
            if staged_course is not None:
                raise RuntimeError("simulated curriculum commit failure")
            original_commit()

        monkeypatch.setattr(database, "commit", fail_after_course_rows_are_staged)
        with pytest.raises(RuntimeError, match="simulated curriculum commit failure"):
            curriculum_service.persist_curriculum(database, learner, user_id)
        database.rollback()

    with Session(engine) as database:
        assert database.scalar(
            select(GeneratedCourse.id).where(
                GeneratedCourse.learner_id == learner_id
            )
        ) is None
        assert database.scalar(
            select(Topic.id).where(Topic.course_id.is_not(None))
        ) is None
    engine.dispose()
