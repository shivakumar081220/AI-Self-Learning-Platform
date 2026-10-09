from sqlalchemy import create_engine

from app import database
from app.config import settings


def test_legacy_tutor_attachments_gain_content_type_without_losing_rows(
    tmp_path, monkeypatch
):
    engine = create_engine(f"sqlite:///{tmp_path / 'legacy-tutor.db'}")
    try:
        with engine.begin() as connection:
            connection.exec_driver_sql(
                "CREATE TABLE tutor_attachments ("
                "id INTEGER PRIMARY KEY, message_id INTEGER NOT NULL, "
                "storage_key VARCHAR(80) NOT NULL UNIQUE, size_bytes INTEGER NOT NULL, "
                "created_at DATETIME NOT NULL)"
            )
            connection.exec_driver_sql(
                "INSERT INTO tutor_attachments "
                "(id, message_id, storage_key, size_bytes, created_at) VALUES "
                "(1, 10, 'legacy-photo.jpg', 123, '2026-01-01'), "
                "(2, 11, 'legacy-graphic.webp', 456, '2026-01-02'), "
                "(3, 12, 'legacy-image.png', 789, '2026-01-03')"
            )

        monkeypatch.setattr(database, "engine", engine)
        monkeypatch.setattr(settings, "database_url", "sqlite:///legacy-tutor.db")

        database.ensure_legacy_columns()
        database.ensure_legacy_columns()

        with engine.connect() as connection:
            rows = connection.exec_driver_sql(
                "SELECT id, storage_key, size_bytes, content_type "
                "FROM tutor_attachments ORDER BY id"
            ).fetchall()

        assert rows == [
            (1, "legacy-photo.jpg", 123, "image/jpeg"),
            (2, "legacy-graphic.webp", 456, "image/webp"),
            (3, "legacy-image.png", 789, "image/png"),
        ]
    finally:
        engine.dispose()
