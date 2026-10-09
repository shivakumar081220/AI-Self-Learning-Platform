# AI Design

## What uses AI

The backend uses OpenRouter for structured generation where configured:

- Personalized course curricula and diagnostic questions
- Topic assessment questions and selected subjective-answer evaluations
- Topic-specific lesson content
- Tutor responses and assessment interpretation/remediation guidance
- Tutor image analysis through a separately configured vision model
- Coding assistance for generation, explanation, debugging, improvement, tests, and exercises

AI is optional. Provider failures, invalid output, or missing configuration use curated or deterministic fallbacks where available. A feature without a safe fallback returns an explicit error rather than fabricated success.

## Provider configuration

Configure these values in the backend environment or local `.env` file:

```text
OPENROUTER_API_KEY=your_key
OPENROUTER_BASE_URL=https://openrouter.ai/api/v1
OPENROUTER_MODEL=openrouter/free
OPENROUTER_VISION_MODEL=
```

Never commit the key. It is not sent to the browser or included in application logs. Image input is disabled unless `OPENROUTER_VISION_MODEL` is configured; before an image is sent, the provider model catalog is checked for the selected model's `architecture.input_modalities` containing `image`. Capability metadata is cached briefly. Missing, unsupported, or unverifiable capability returns an actionable error rather than a text-only answer presented as image analysis.

## Context, validation, and caching

Each operation receives only the relevant persisted learner and course context, such as experience level, goal, selected track, current topic, completed work, skill evidence, and recent assessment results. Operation-specific Pydantic schemas validate structured responses before they are used. Validators also check identifiers, topic/type membership, required content, and answer privacy where applicable.

Tutor lesson context is trimmed to bounded summaries and examples. Recent conversation history, learner text, code, and sandbox output have independent input limits. Image files are signature-checked and size-limited before a data URL is sent to the explicitly configured vision model; raw image bytes are not stored in SQL.

Reusable generated curricula, lessons, and assessments are persisted and loaded again when the relevant context matches. Tutor responses are tied to live conversation turns and are not response-cached.

## Deterministic responsibilities

The model does not control authentication, ownership, answer privacy, score calculation for objectively graded items, skill persistence, weakness status, topic completion, prerequisite enforcement, or database writes. These remain application decisions.

The adaptive engine uses saved assessment and skill evidence. Generated content may inform the learner-facing explanation or interpretation, but it cannot grant access, mark work complete, or override prerequisite order.

AI coding suggestions are returned for the learner to review and edit; they are never executed automatically. Code only runs when the learner explicitly chooses Run Code and only through the external sandbox. The backend stores bounded execution status/output, not learner source code. Tutor turns and code chat do not change assessment scores, skill mastery, or completion progress.

Topic skill scores use the latest result directly on the first observation and `0.6 * previous_score + 0.4 * latest_score` thereafter. The current bands are weak below 50%, developing from 50% to below 80%, and strong at 80% or above.

## Reliability and limits

Provider requests use bounded retries. Invalid or unavailable output is rejected and handled by the operation's curated/deterministic fallback. Provider logs record operational metadata, not prompt bodies, response bodies, credentials, or learner identifiers.

Vision requests deliberately do not use deterministic fallback: if the configured vision model cannot analyze the image or its response is invalid, the request fails clearly so the UI cannot imply that an image was understood. Text-only tutor fallback remains available for ordinary text questions. Coding assistance requires OpenRouter; it returns an explicit error rather than fabricated code when the provider is unavailable.

Schema validation guarantees structure, not factual correctness. AI-generated educational explanations can still be wrong. Automated tests mock OpenRouter; only an explicitly enabled live smoke test makes a real provider request. Code execution for coding assessments requires the separately configured sandbox.
