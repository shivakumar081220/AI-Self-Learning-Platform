import json
import logging
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from ..config import settings

logger = logging.getLogger(__name__)
MAX_SOURCE_BYTES = 12_000
MAX_STDIN_BYTES = 4_000
MAX_OUTPUT_BYTES = 32_000
MAX_RESPONSE_BYTES = 128_000
MAX_TIMEOUT_SECONDS = 15.0
_EXECUTIONS = ThreadPoolExecutor(max_workers=4, thread_name_prefix="code-sandbox")
_EXECUTION_LIMIT = threading.BoundedSemaphore(4)


class SandboxUnavailable(RuntimeError):
    pass


class SandboxTimeout(RuntimeError):
    pass


class SandboxExecutionError(RuntimeError):
    pass


class PistonRunResult(BaseModel):
    model_config = ConfigDict(extra="ignore")

    stdout: str = Field(default="", max_length=MAX_OUTPUT_BYTES)
    stderr: str = Field(default="", max_length=MAX_OUTPUT_BYTES)
    code: int | None = None
    signal: str | None = None


class PistonResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    run: PistonRunResult


def _post_sandbox(payload: bytes, timeout: float) -> bytes:
    if not settings.tutor_code_sandbox_url:
        raise SandboxUnavailable(
            "Code execution requires TUTOR_CODE_SANDBOX_URL to be configured."
        )
    headers = {"Content-Type": "application/json", "Accept": "application/json"}
    if settings.tutor_code_sandbox_api_key:
        headers["Authorization"] = f"Bearer {settings.tutor_code_sandbox_api_key}"
    request = Request(
        settings.tutor_code_sandbox_url,
        data=payload,
        headers=headers,
        method="POST",
    )
    try:
        with urlopen(request, timeout=timeout) as response:
            if not 200 <= response.status < 300:
                raise SandboxExecutionError("The sandbox returned an unsuccessful status.")
            body = response.read(MAX_RESPONSE_BYTES + 1)
            if len(body) > MAX_RESPONSE_BYTES:
                raise SandboxExecutionError("The sandbox response exceeded the allowed size.")
            return body
    except HTTPError as error:
        logger.warning("Code sandbox returned HTTP status=%s", error.code)
        if error.code == 429:
            raise SandboxUnavailable("The sandbox is rate limited; retry shortly.") from None
        raise SandboxUnavailable("The sandbox service rejected the execution request.") from None
    except TimeoutError:
        raise SandboxTimeout("The sandbox execution timed out.") from None
    except URLError:
        raise SandboxUnavailable("The sandbox service could not be reached.") from None


def run_python(source_code: str, stdin: str) -> dict:
    if not settings.tutor_code_sandbox_url:
        raise SandboxUnavailable(
            "Code execution requires TUTOR_CODE_SANDBOX_URL to be configured."
        )
    if len(source_code.encode("utf-8")) > MAX_SOURCE_BYTES:
        raise ValueError("Code must be no larger than 12 KB.")
    if len(stdin.encode("utf-8")) > MAX_STDIN_BYTES:
        raise ValueError("Standard input must be no larger than 4 KB.")
    timeout = min(max(settings.code_sandbox_timeout_seconds, 0.1), MAX_TIMEOUT_SECONDS)
    task = {
        "language": "python",
        "version": settings.tutor_code_sandbox_python_version,
        "files": [{"name": "main.py", "content": source_code}],
        "stdin": stdin,
        "run_timeout": round(timeout * 1000),
    }
    payload = json.dumps(task, ensure_ascii=True).encode("utf-8")
    if not _EXECUTION_LIMIT.acquire(blocking=False):
        raise SandboxUnavailable("The code runner is busy. Wait for another run to finish.")
    started = time.monotonic()
    future = _EXECUTIONS.submit(_post_sandbox, payload, timeout)
    future.add_done_callback(lambda _: _EXECUTION_LIMIT.release())
    try:
        body = future.result(timeout=timeout + 1)
    except TimeoutError:
        future.cancel()
        raise SandboxTimeout("The sandbox execution timed out.") from None
    elapsed_ms = round((time.monotonic() - started) * 1000)
    try:
        result = PistonResponse.model_validate_json(body).run
    except (ValidationError, ValueError):
        logger.warning("Code sandbox returned a malformed response.")
        raise SandboxExecutionError("The sandbox returned an invalid execution result.") from None
    status = "completed" if result.code == 0 and result.signal is None else "failed"
    return {
        "status": status,
        "output": result.stdout[:MAX_OUTPUT_BYTES],
        "stderr": result.stderr[:MAX_OUTPUT_BYTES],
        "exit_status": result.code,
        "duration_ms": None,
        "provider_duration_ms": elapsed_ms,
    }