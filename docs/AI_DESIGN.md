# AI Design

## What uses AI

The backend uses OpenRouter for structured generation where configured:

- Personalized course curricula and diagnostic questions
- Topic assessment questions and selected subjective-answer evaluations
- Topic-specific lesson content
- Tutor responses and assessment interpretation/remediation guidance

AI is optional. Provider failures, invalid output, or missing configuration use curated or deterministic fallbacks where available. A feature without a safe fallback returns an explicit error rather than fabricated success.

## Provider configuration

Configure these values in the backend environment or local `.env` file:

```text
OPENROUTER_API_KEY=your_key
OPENROUTER_BASE_URL=https://openrouter.ai/api/v1
OPENROUTER_MODEL=openrouter/free
```

Never commit the key. It is not sent to the browser or included in application logs.

## Context, validation, and caching

Each operation receives only the relevant persisted learner and course context, such as experience level, goal, selected track, current topic, completed work, skill evidence, and recent assessment results. Operation-specific Pydantic schemas validate structured responses before they are used. Validators also check identifiers, topic/type membership, required content, and answer privacy where applicable.

Reusable generated curricula, lessons, and assessments are persisted and loaded again when the relevant context matches. Tutor responses are tied to live conversation turns and are not response-cached.

## Deterministic responsibilities

The model does not control authentication, ownership, answer privacy, score calculation for objectively graded items, skill persistence, weakness status, topic completion, prerequisite enforcement, or database writes. These remain application decisions.

The adaptive engine uses saved assessment and skill evidence. Generated content may inform the learner-facing explanation or interpretation, but it cannot grant access, mark work complete, or override prerequisite order.

Topic skill scores use the latest result directly on the first observation and `0.6 * previous_score + 0.4 * latest_score` thereafter. The current bands are weak below 50%, developing from 50% to below 80%, and strong at 80% or above.

## Reliability and limits

Provider requests use bounded retries. Invalid or unavailable output is rejected and handled by the operation's curated/deterministic fallback. Provider logs record operational metadata, not prompt bodies, response bodies, credentials, or learner identifiers.

Schema validation guarantees structure, not factual correctness. AI-generated educational explanations can still be wrong. Automated tests mock OpenRouter; only an explicitly enabled live smoke test makes a real provider request. Code execution for coding assessments requires the separately configured sandbox.
