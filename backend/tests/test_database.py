from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.database import Base
from app.models import (
    Learner,
    LearningGoal,
    Topic,
    TopicPrerequisite,
    TopicProgress,
)
from app.seed_topics import PREREQUISITES, TOPIC_CATALOG, seed_topics


def test_seed_creates_curated_topics_and_prerequisites(tmp_path):
    database_url = f"sqlite:///{tmp_path / 'phase2-test.db'}"
    engine = create_engine(database_url)
    Base.metadata.create_all(bind=engine)

    with Session(engine) as database:
        seed_topics(database)
        seed_topics(database)

        topics = database.scalars(select(Topic)).all()
        relationships = database.scalars(select(TopicPrerequisite)).all()

        assert len(topics) == len(TOPIC_CATALOG)
        assert len(relationships) == sum(len(items) for items in PREREQUISITES.values())
        assert {topic.id for topic in topics} == {item["id"] for item in TOPIC_CATALOG}


def test_learner_activity_models_persist_relationships(tmp_path):
    database_url = f"sqlite:///{tmp_path / 'learner-test.db'}"
    engine = create_engine(database_url)
    Base.metadata.create_all(bind=engine)

    with Session(engine) as database:
        learner = Learner(
            name="Asha",
            experience_level="beginner",
            goal_text="Build a RAG application",
        )
        learner.goals.append(
            LearningGoal(title="Build a RAG application", track="generative_ai")
        )
        database.add(learner)
        seed_topics(database)
        learner.topic_progress.append(
            TopicProgress(topic_id="ai-foundations", status="active")
        )
        database.commit()

        loaded_learner = database.get(Learner, learner.id)
        assert loaded_learner is not None
        assert loaded_learner.goals[0].title == "Build a RAG application"
        assert loaded_learner.topic_progress[0].topic_id == "ai-foundations"
