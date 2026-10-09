# AI Latency and Cache Report

## Measurement and privacy

Structured provider events record operation, UTC start time, provider duration, source, model, HTTP status, operation status, and validation status. Cache/fallback events identify their source. Logs omit prompts, response bodies, credentials, authorization headers, and learner identifiers.

Provider duration is not total endpoint duration: an API request also includes database and application work. The available historical run did not capture numeric per-request duration, so this document makes no latency-improvement claim.

## Generation and reuse

| Operation | Trigger | Reuse behavior |
|---|---|---|
| Curriculum | Course enrollment or explicit generation | Existing matching persisted course |
| Diagnostic | Learner starts diagnostic | Cached question artifact and matching pending attempt |
| Lesson | Learner opens a topic | Persistent, versioned lesson artifact |
| Topic assessment | Learner selects assessment types | Cached generated set and matching pending attempt |
| Subjective evaluation | Assessment submission | Evaluation is persisted with the completed attempt |
| Tutor | Each learner turn | Conversation is persisted; response itself is not cached |
| Code evaluation | Code-bearing assessment submission | Batched external sandbox call, not an OpenRouter request |

Provider requests have a configured timeout (30 seconds by default) and no more than one bounded retry per operation. A retry can occur for eligible transient failures or invalid structured output. Endpoint/client timeouts are separate from provider timeouts.

## Observed provider results

The documented live browser run used the configured `openrouter/free` model. OpenRouter returned HTTP 429 for the tested curriculum, diagnostic, interpretation, lesson, topic-assessment, and remediation operations, including the bounded retry. The application returned fallback results where supported. A repeated unchanged lesson request reused saved fallback content.

This run demonstrates fallback behavior and cache reuse, not successful live AI generation or reduced latency. The run did not capture per-request duration values. Multi-type assessment integration tests mock OpenRouter and the sandbox; they provide no live latency measurement.

## Test evidence

Automated tests cover artifact reuse, pending-assessment reuse, invalid-output fallback, and bounded retry behavior. The regular test suite does not call OpenRouter. A live provider test is opt-in and may incur provider usage. Real sandbox performance also requires an independently deployed sandbox and is not measured here.

## Interpretation

Persisting generated artifacts avoids repeat work for unchanged context. A changed learner or course context may intentionally produce a new cache key. The available evidence is not sufficient to claim a provider speedup, lower average latency, or successful provider availability.
