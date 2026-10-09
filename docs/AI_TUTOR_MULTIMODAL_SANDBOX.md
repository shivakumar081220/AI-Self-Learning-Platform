# Multimodal AI Tutor and Coding Sandbox

## Overview

The feature extends the authenticated tutor already attached to lesson pages. Chat, voice transcripts, lesson-section questions, image questions, and the Python workspace share the selected tutor conversation. Tutor activity does not score assessments or change mastery, weaknesses, or course progress.

### Runtime flow

```text
React tutor view
  ├─ Chat / speech transcript ──> existing tutor message endpoint
  ├─ Image question ──> authenticated multipart endpoint
  │                      ├─ MIME/signature/size checks
  │                      ├─ verify configured model advertises image input
  │                      ├─ OpenRouter structured vision request
  │                      └─ save private image file + TutorAttachment metadata
  └─ Coding workspace
       ├─ AI action ──> OpenRouter structured coding response (review only)
       └─ Run Code ──> Piston /api/v2/execute ──> TutorCodeExecution record
```

All routes are authenticated and first check that the learner belongs to the caller. Conversation and topic/course context is checked before a tutor action or execution. Attachment downloads and execution-history reads repeat ownership validation.

## Configuration

Set values in the backend environment or local `.env`; never add credentials to Vite variables or frontend code.

| Variable | Required for | Meaning |
|---|---|---|
| `OPENROUTER_API_KEY` | Live text, vision, or coding AI | Backend-only OpenRouter credential |
| `OPENROUTER_BASE_URL` | OpenRouter features | Normally `https://openrouter.ai/api/v1` |
| `OPENROUTER_MODEL` | Text tutor and coding AI | Existing text-capable model selection |
| `OPENROUTER_VISION_MODEL` | Image questions | Explicit model identifier that accepts image input |
| `OPENROUTER_TIMEOUT_SECONDS` | OpenRouter requests | Existing provider timeout setting |
| `TUTOR_CODE_SANDBOX_URL` | Tutor workspace execution | Piston-compatible `/api/v2/execute` endpoint; for local setup use `http://127.0.0.1:2000/api/v2/execute` |
| `TUTOR_CODE_SANDBOX_API_KEY` | Protected tutor sandbox proxy | Optional bearer credential for a trusted reverse proxy in front of Piston; Piston itself does not provide API authentication |
| `TUTOR_CODE_SANDBOX_PYTHON_VERSION` | Tutor workspace execution | Installed Piston Python runtime version; defaults to `3.10.0` |
| `CODE_SANDBOX_TIMEOUT_SECONDS` | Tutor workspace execution | Client request timeout; clamped to 0.1–15 seconds |
| `CODE_SANDBOX_URL` | Code-bearing assessments | Existing task-API endpoint used by assessment evaluation; it is not a Piston URL |
| `CODE_SANDBOX_API_KEY` | Authenticated sandbox deployments | Optional bearer credential sent only by the backend to the configured sandbox |
| `TUTOR_UPLOAD_DIR` | Image persistence | Private directory for generated image filenames; defaults to `backend/data/tutor_uploads` |

Set `OPENROUTER_VISION_MODEL` only after confirming the model supports image input. Before the first image request for a model, the backend queries the OpenRouter `/models` catalog and requires `architecture.input_modalities` to contain `image`; successful and unsupported metadata is cached for five minutes. If metadata is unavailable, the model is not listed, or image input is not advertised, the API rejects the image request. It does not assume the configured text model is multimodal.

The optional OpenRouter metadata check is not a billable generation call. Actual image/tutor/coding requests are provider calls and may incur usage. Keys are not logged or returned.

### Local Piston setup for the tutor workspace

The tutor adapter sends Piston's native request shape to `TUTOR_CODE_SANDBOX_URL`. It does not execute submitted code in FastAPI. Piston is separate from the existing task API configured for code-bearing assessments; do not point `CODE_SANDBOX_URL` at Piston because assessment scoring expects a different batch contract.

This repository includes a local development Compose service in `sandbox/docker-compose.yml`. Piston requires a privileged container for its Isolate runner. The service is bound to loopback, disables learner-job networking, applies process/file/output/time/CPU/memory/concurrency limits, and does not mount the application directory, database, `.env`, or Docker socket. **The privileged-container requirement is a significant host-level security risk. Run this only on a trusted, dedicated development machine or isolated Linux host, not on a shared or production host.** Docker Desktop must use its Linux container engine; Windows containers are not supported.

From the repository root in PowerShell:

```powershell
docker compose -f sandbox\docker-compose.yml up -d
Invoke-RestMethod http://127.0.0.1:2000/api/v2/packages |
  Where-Object { $_.language -eq "python" -and $_.version -eq "3.10.0" } |
  Select-Object language, version, installed
Invoke-RestMethod -Method Post `
  -Uri http://127.0.0.1:2000/api/v2/packages `
  -ContentType "application/json" `
  -Body '{"language":"python","version":"3.10.0"}'
```

The first request checks that the configured Python version exists in Piston's package index. Install it with the second request, then verify it is installed with `Invoke-RestMethod http://127.0.0.1:2000/api/v2/runtimes`. If that version is unavailable, select a Python version actually listed by the package endpoint, install it, and set `TUTOR_CODE_SANDBOX_PYTHON_VERSION` to that exact version.

Set the backend environment (normally the root `.env`) and restart FastAPI:

```text
TUTOR_CODE_SANDBOX_URL=http://127.0.0.1:2000/api/v2/execute
TUTOR_CODE_SANDBOX_API_KEY=
TUTOR_CODE_SANDBOX_PYTHON_VERSION=3.10.0
CODE_SANDBOX_TIMEOUT_SECONDS=10
```

Piston execution requests contain `language`, `version`, `files`, `stdin`, and a bounded `run_timeout`. The adapter maps Piston `run.stdout`, `run.stderr`, and `run.code` to the tutor execution record. Piston does not report a compatible execution duration, so `duration_ms` remains null; `provider_duration_ms` is only the HTTP round trip. Non-zero exit codes and signals are `failed`, never successful. A local smoke test can use `print(42)` in the tutor workspace after starting Piston and restarting FastAPI.

The Compose file has not been live-run or security-audited in this environment because Docker/WSL2 are unavailable. Mocked tests validate the adapter contract, not actual Piston isolation. The UI disables Stop because the Piston request protocol used here has no cancellation endpoint. The application additionally limits four concurrent tutor executions.

## API contracts

All routes require a bearer-authenticated user and enforce learner/conversation ownership.

### Image message

`POST /api/learners/{learner_id}/tutor/conversations/{conversation_id}/images`

Multipart form fields:

| Field | Type | Limit |
|---|---|---|
| `content` | Text | 2,000 characters; may be blank to use a contextual default question |
| `files` | Repeated file | JPEG, PNG, GIF, or WebP; up to 3 files, 5 MiB each and 10 MiB total |
| `section_context_json` | Optional JSON text | 5,500 characters, validated as the current tutor section context |

The request body is capped at 11 MiB and requires a bounded `Content-Length`. MIME type and file signature must agree. SVG and other active document formats are not accepted. The backend creates random storage names; clients cannot select filesystem paths. The image content is sent to the configured vision model as image input and is not saved in SQL. If the provider request fails, no message or attachment metadata is committed, allowing the learner to retry or continue in text-only chat.

The response uses the existing `TutorMessageSendResponse` shape. `user_message.attachments` includes only attachment ID, MIME type, and byte size. The original file is retrieved separately:

`GET /api/learners/{learner_id}/tutor/attachments/{attachment_id}`

This returns the owned image with `Cache-Control: private, no-store` and `X-Content-Type-Options: nosniff`. Files are stored outside the frontend's public/static directory.

### AI coding tools

`POST /api/learners/{learner_id}/tutor/conversations/{conversation_id}/coding-assistant`

```json
{
  "action": "ask | generate | explain | debug | improve | tests | exercise",
  "language": "python",
  "prompt": "requirements or follow-up question",
  "code": "current editor contents",
  "execution_status": "not_run | completed | failed | timeout | unavailable",
  "execution_output": "latest actual sandbox output",
  "execution_stderr": "latest actual sandbox error"
}
```

The schema limits code to 12 KB, prompts to 2,000 characters, and execution context fields to 8,000 characters. `debug` requires a real prior execution status, not `not_run`. The structured response has `summary`, optional `code`, `explanation`, and `suggested_tests`. It is an AI suggestion only. It is not added to the editor or executed until the learner explicitly applies/edits it and selects Run Code.

### Python execution and history

`POST /api/learners/{learner_id}/tutor/conversations/{conversation_id}/executions`

```json
{
  "language": "python",
  "source_code": "print(42)",
  "stdin": ""
}
```

Code and standard input are capped at 12 KB and 4 KB. Unsupported languages and invalid sizes are rejected. Missing configuration, rate limiting, timeouts, transport errors, malformed results, and runtime failures are not represented as successful output. The response distinguishes `completed`, `failed`, `timeout`, and `unavailable`; `exit_status` and code-execution duration remain null when the provider does not report them. `provider_duration_ms` measures the request round trip, not execution time.

`GET /api/learners/{learner_id}/tutor/conversations/{conversation_id}/executions` returns the latest 20 executions for that owner. `TutorCodeExecution` stores learner/conversation IDs, Python language, status, bounded output/stderr, optional provider metadata, and timestamp. Submitted source code is not persisted. Records are never retrievable through another learner's conversation.

## Security and persistence controls

- No learner code is passed to `exec`, `eval`, a local interpreter, shell, or subprocess in FastAPI. Tutor workspace execution is sent to `TUTOR_CODE_SANDBOX_URL`; assessment execution continues to use its distinct task API at `CODE_SANDBOX_URL`.
- Code/input/request/response limits and an application-level four-run concurrency gate bound the adapter. The sandbox must enforce its own strict CPU, memory, filesystem, process, network, and execution-time limits.
- Image request body size, image count, individual/total image sizes, MIME types, and common file signatures are checked. Images are private generated-name files; the database holds only metadata and message association.
- Provider prompts contain bounded learner/course/topic/lesson context, a recent conversation window, and bounded user/code/output fields. User-provided text, code, and image contents are treated as untrusted data in system instructions.
- API keys, image contents, submitted code, and provider response bodies are not written to logs. Responses use generic errors for upstream failures.
- SQLAlchemy startup `create_all` adds the new tutor attachment and code-execution tables without dropping or resetting existing application tables. Back up the database and private upload directory together for production recovery.
- Normal tests mock provider and sandbox calls. Passing those tests proves request construction and parsing, not external provider availability or sandbox isolation.

## Optional tests and live verification

From `backend`:

```powershell
.\.venv\Scripts\python.exe -m pytest -q
$env:RUN_LIVE_TUTOR_SMOKE='1'
.\.venv\Scripts\python.exe -m pytest -q tests\test_live_tutor_smoke.py
```

The optional smoke tests are skipped unless explicitly enabled. Vision smoke requires both `OPENROUTER_API_KEY` and `OPENROUTER_VISION_MODEL`; tutor sandbox smoke requires `TUTOR_CODE_SANDBOX_URL` and an installed matching Piston runtime. A real successful sandbox smoke confirms only that the endpoint returned the harmless print output, not that every isolation property was independently audited.

## Current limitations

- The local environment examined for this implementation has no `OPENROUTER_VISION_MODEL` or running Piston service, so real image-generation and sandbox execution cannot yet be demonstrated.
- Only Python is exposed because no additional sandbox-supported languages were verifiable.
- Stop/cancel is not available in the current remote task protocol.
- Sandbox-reported stderr, process exit status, and execution duration are optional; legacy providers that omit these fields are labeled as not reported by the UI.
- OCR/handwriting quality depends on the configured vision model and image legibility; no guarantee is made for unreadable or ambiguous content.
