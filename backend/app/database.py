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


def get_db() -> Generator[Session, None, None]:
    database = SessionLocal()
    try:
        yield database
    finally:
        database.close()
