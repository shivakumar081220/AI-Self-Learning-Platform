# AI Latency and Cache Report

## Measurement method

Every `request_structured_json` call now logs a UTC `started_at`, total provider `duration_ms` across the original attempt and any permitted retry, HTTP status, operation status, source, model name, and Pydantic validation status. Durable artifact cache hits log their local lookup duration and `source=cache`; fallback paths log `source=fallback`. No prompt, response body, API key, authorization header, or learner identifier is logged.

Endpoint total time includes database work and, where applicable, synchronous provider time. Provider `duration_ms` is available in backend application logs; it is distinct from client-perceived endpoint time. The prior live run recorded HTTP 429 for lesson content, topic questions, interpretation, and remediation, but did not record per-request duration. Therefore no baseline milliseconds or post-change latency improvement is claimed here.

## Operation profile

| Operation | When it runs | Provider calls on an ordinary cache miss | Provider timeout | Token cap | Persistent reuse |
|---|---|---:|---:|---:|---|
| Curriculum | Profile enrollment | 1 | 30s default | 2,400 | Existing matching course and generated topics |
| Diagnostic | Learner begins diagnostic | 1 | 30s default | 3,200 | `AIArtifactCache` plus existing pending assessment |
| Lesson | Learner opens current topic | 1 | 30s default | 2,600 | `AIArtifactCache`, versioned from learner/topic state |
| Topic assessment | Learner completes topic | 1 | 30s default | 1,400 | `AIArtifactCache` plus existing pending assessment |
| Diagnostic interpretation | After deterministic diagnostic score | 1 | 30s default | 1,200 | Saved with its completed assessment |
| Topic remediation | After deterministic weak result | 1 | 30s default | 1,200 | Saved with its completed assessment |
| Tutor | Explicit learner question | 1 | 30s default | 1,400 | No persistent response cache |

An output-validation failure may consume one correction attempt. A 429 or 5xx may consume one delayed retry, honoring `Retry-After` up to five seconds (one-second default). Those are bounded exceptions, not normal calls; there are never more than two HTTP attempts in one provider operation.

## Latency and source results

| Flow | Previous observation | Post-change measurement |
|---|---|---|
| Curriculum | OpenRouter succeeded in an earlier UI run. Per-request duration was not captured. | Fresh run: two HTTP 429 responses (original + one retry), deterministic curriculum fallback, endpoint 200. |
| Diagnostic | OpenRouter succeeded in an earlier UI run. Per-request duration was not captured. | Fresh run: two HTTP 429 responses, curated fallback, endpoint 200 with eight questions; repeating the request reused the pending assessment. |
| Diagnostic submission | Deterministic 50% score; interpretation fell back after HTTP 429. | Fresh run: deterministic 50% (4/8); interpretation had two HTTP 429 responses and used deterministic fallback. |
| Lesson | Earlier request received HTTP 429 and used curated fallback. | Fresh run: two HTTP 429 responses and curated fallback; repeating the unchanged lesson GET returned persisted fallback without another provider request. |
| Topic assessment | Earlier request received HTTP 429 and used deterministic fallback. | Fresh run: two HTTP 429 responses, curated fallback, endpoint 200 with three questions; public response omitted answer keys. |
| Topic assessment submission | Deterministic 33.3%; remediation fell back after HTTP 429. | Fresh run: deterministic 1/3 (33.3%); two HTTP 429 responses for remediation, then deterministic remediation was returned and persisted with the assessment. |

## Automated cache/retry checks

Mocked tests verify that a repeated lesson request uses one persisted cache entry and makes no second provider call; equivalent pending diagnostic/topic assessments are reused; invalid output is rejected; and a mocked 429 respects `Retry-After` and makes exactly one retry. These tests do not claim provider latency or live rate-limit recovery.

## Interpretation

The fresh browser run used a configured `openrouter/free` model, but every live operation was rate-limited. It therefore verifies fallback usability, not successful AI generation or latency improvement. Provider warnings and endpoint status were observed; a per-operation `duration_ms` value was not available in the captured Uvicorn output. The structured timing instrumentation remains in place, but measured provider/endpoint durations and a latency comparison require a successful run with timing records enabled and captured.

The optimization removes the redundant curriculum POST from the diagnostic page, shifts course generation to the enrollment action, generates diagnostic/lesson/assessment/remediation only when needed, narrows prompts to current learner/topic context, and persists reusable artifacts. Do not infer provider recovery or reduced mean latency from this rate-limited run.
