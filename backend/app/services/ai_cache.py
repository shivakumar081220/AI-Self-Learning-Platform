import hashlib
import json
import logging
import time
from collections.abc import Callable
from datetime import datetime, timedelta
from typing import TypeVar

from pydantic import BaseModel, ValidationError
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..config import settings
from ..models import AIArtifactCache


logger = logging.getLogger(__name__)
ResponseModel = TypeVar("ResponseModel", bound=BaseModel)
_FALLBACK_CACHE_SECONDS = 60
_PENDING_STALE_SECONDS = 90


def _emit_cache_timing(
    operation: str,
    started_at: str,
    started_clock: float,
    source: str,
    validation_status: str,
) -> None:
    telemetry_source = (
        "openrouter" if source == "openrouter" else "cache" if source == "cache" else "fallback"
    )
    logger.info(
        "ai_operation=%s started_at=%s duration_ms=%d status=success source=%s model=%s "
        "validation_status=%s",
        operation,
        started_at,
        round((time.monotonic() - started_clock) * 1000),
        telemetry_source,
        settings.openrouter_model,
        validation_status,
    )


def get_or_generate_artifact(
    database: Session,
    *,
    learner_id: int,
    operation: str,
    key_context: dict,
    response_model: type[ResponseModel],
    generate: Callable[[], tuple[ResponseModel, str]],
    fallback: Callable[[], ResponseModel],
    persist_fallback: bool = False,
) -> tuple[ResponseModel, str]:
    key_material = json.dumps(key_context, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    cache_key = hashlib.sha256(key_material.encode("utf-8")).hexdigest()
    started_at = datetime.utcnow().isoformat(timespec="milliseconds") + "Z"
    started_clock = time.monotonic()

    while True:
        now = datetime.utcnow()
        artifact = database.scalar(
            select(AIArtifactCache).where(
                AIArtifactCache.learner_id == learner_id,
                AIArtifactCache.operation == operation,
                AIArtifactCache.cache_key == cache_key,
            )
        )
        if artifact and artifact.status in {"completed", "fallback"}:
            if (
                artifact.status == "completed"
                or artifact.expires_at is None
                or artifact.expires_at > now
            ):
                try:
                    cached = response_model.model_validate(artifact.result_json)
                except ValidationError:
                    logger.warning(
                        "AI artifact cache entry failed validation; operation=%s status=invalid_cache",
                        operation,
                    )
                    database.execute(
                        update(AIArtifactCache)
                        .where(AIArtifactCache.id == artifact.id)
                        .values(status="failed", result_json=None, source=None, expires_at=None)
                    )
                    database.commit()
                    continue
                source = "cache" if artifact.status == "completed" else "curated_fallback"
                _emit_cache_timing(operation, started_at, started_clock, source, "passed")
                return cached, source

        if artifact and artifact.status == "pending":
            if (now - artifact.updated_at).total_seconds() < _PENDING_STALE_SECONDS:
                if (time.monotonic() - started_clock) >= settings.openrouter_timeout_seconds:
                    generated_fallback = fallback()
                    _emit_cache_timing(
                        operation, started_at, started_clock, "curated_fallback", "passed"
                    )
                    return generated_fallback, "curated_fallback"
                time.sleep(0.1)
                database.expire_all()
                continue

        if artifact is None:
            artifact = AIArtifactCache(
                learner_id=learner_id,
                operation=operation,
                cache_key=cache_key,
                status="pending",
            )
            database.add(artifact)
            try:
                database.commit()
            except IntegrityError:
                database.rollback()
                continue
        else:
            claimed = database.execute(
                update(AIArtifactCache)
                .where(AIArtifactCache.id == artifact.id)
                .values(
                    status="pending",
                    source=None,
                    result_json=None,
                    expires_at=None,
                    updated_at=now,
                )
            )
            database.commit()
            if claimed.rowcount != 1:
                continue

        try:
            result, source = generate()
            validated_result = response_model.model_validate(result)
            is_ai_result = source == "openrouter"
            artifact.status = "completed" if is_ai_result else "fallback"
            artifact.source = source
            artifact.result_json = validated_result.model_dump(mode="json")
            artifact.expires_at = (
                None
                if is_ai_result or persist_fallback
                else datetime.utcnow() + timedelta(seconds=_FALLBACK_CACHE_SECONDS)
            )
            artifact.updated_at = datetime.utcnow()
            database.commit()
            _emit_cache_timing(
                operation,
                started_at,
                started_clock,
                source,
                "passed",
            )
            return validated_result, source
        except Exception:
            database.rollback()
            database.execute(
                update(AIArtifactCache)
                .where(
                    AIArtifactCache.learner_id == learner_id,
                    AIArtifactCache.operation == operation,
                    AIArtifactCache.cache_key == cache_key,
                )
                .values(status="failed", source=None, result_json=None, expires_at=None)
            )
            database.commit()
            raise
