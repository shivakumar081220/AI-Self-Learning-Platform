from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from .config import settings


connect_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}
engine = create_engine(settings.database_url, connect_args=connect_args)
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)


class Base(DeclarativeBase):
    pass


def ensure_legacy_columns() -> None:
    """Add nullable Phase 9 columns to an existing prototype SQLite database."""
    if not settings.database_url.startswith("sqlite"):
        return
    with engine.begin() as connection:
        tables = {
            row[0]
            for row in connection.exec_driver_sql(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
        if "learners" in tables:
            columns = {row[1] for row in connection.exec_driver_sql("PRAGMA table_info(learners)").fetchall()}
            if "user_id" not in columns:
                connection.exec_driver_sql("ALTER TABLE learners ADD COLUMN user_id INTEGER")
            if "preferred_learning_style" not in columns:
                connection.exec_driver_sql("ALTER TABLE learners ADD COLUMN preferred_learning_style VARCHAR(80)")
            if "target_outcome" not in columns:
                connection.exec_driver_sql("ALTER TABLE learners ADD COLUMN target_outcome TEXT")
        if "topics" in tables:
            columns = {row[1] for row in connection.exec_driver_sql("PRAGMA table_info(topics)").fetchall()}
            if "owner_user_id" not in columns:
                connection.exec_driver_sql("ALTER TABLE topics ADD COLUMN owner_user_id INTEGER")
            if "course_id" not in columns:
                connection.exec_driver_sql("ALTER TABLE topics ADD COLUMN course_id INTEGER")
            if "track_id" not in columns:
                connection.exec_driver_sql(
                    "ALTER TABLE topics ADD COLUMN track_id VARCHAR(50) NOT NULL DEFAULT 'generative_ai'"
                )
            if "is_active" not in columns:
                connection.exec_driver_sql(
                    "ALTER TABLE topics ADD COLUMN is_active BOOLEAN NOT NULL DEFAULT 1"
                )
            if "learning_objectives_json" not in columns:
                connection.exec_driver_sql(
                    "ALTER TABLE topics ADD COLUMN learning_objectives_json JSON NOT NULL DEFAULT '[]'"
                )
            if "estimated_minutes" not in columns:
                connection.exec_driver_sql("ALTER TABLE topics ADD COLUMN estimated_minutes INTEGER")
        if "generated_courses" in tables:
            columns = {
                row[1]
                for row in connection.exec_driver_sql("PRAGMA table_info(generated_courses)").fetchall()
            }
            if "generation_source" not in columns:
                connection.exec_driver_sql(
                    "ALTER TABLE generated_courses ADD COLUMN generation_source VARCHAR(30) NOT NULL DEFAULT 'unknown'"
                )
            if "track_id" not in columns:
                connection.exec_driver_sql(
                    "ALTER TABLE generated_courses ADD COLUMN track_id VARCHAR(50) NOT NULL DEFAULT 'generative_ai'"
                )
            if "track_history_json" not in columns:
                connection.exec_driver_sql(
                    "ALTER TABLE generated_courses ADD COLUMN track_history_json JSON NOT NULL DEFAULT '[]'"
                )
            if "target_outcome" not in columns:
                connection.exec_driver_sql(
                    "ALTER TABLE generated_courses ADD COLUMN target_outcome TEXT"
                )
            if "learning_objectives_json" not in columns:
                connection.exec_driver_sql(
                    "ALTER TABLE generated_courses ADD COLUMN learning_objectives_json JSON NOT NULL DEFAULT '[]'"
                )
            for index in connection.exec_driver_sql(
                "PRAGMA index_list('generated_courses')"
            ).fetchall():
                if not index[2]:
                    continue
                index_name = index[1].replace('"', '""')
                index_columns = [
                    row[2]
                    for row in connection.exec_driver_sql(
                        f'PRAGMA index_info("{index_name}")'
                    ).fetchall()
                ]
                if index_columns == ["learner_id"]:
                    connection.exec_driver_sql(f'DROP INDEX "{index_name}"')
            connection.exec_driver_sql(
                "CREATE INDEX IF NOT EXISTS ix_generated_courses_learner_id "
                "ON generated_courses (learner_id)"
            )
        if "learning_paths" in tables:
            columns = {
                row[1]
                for row in connection.exec_driver_sql("PRAGMA table_info(learning_paths)").fetchall()
            }
            if "course_id" not in columns:
                connection.exec_driver_sql(
                    "ALTER TABLE learning_paths ADD COLUMN course_id INTEGER"
                )
        if "assessments" in tables:
            columns = {
                row[1]
                for row in connection.exec_driver_sql("PRAGMA table_info(assessments)").fetchall()
            }
            if "feedback_json" not in columns:
                connection.exec_driver_sql("ALTER TABLE assessments ADD COLUMN feedback_json JSON")


def get_db() -> Generator[Session, None, None]:
    database = SessionLocal()
    try:
        yield database
    finally:
        database.close()
