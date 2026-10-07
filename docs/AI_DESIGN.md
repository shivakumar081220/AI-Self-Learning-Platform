# AI Design Notes

## Why AI is used

OpenRouter is used for meaningful generative work in the Generative AI learning track:

- Diagnostic question generation
- Topic assessment question generation
- Learning explanations, examples, and analogies
- Personalized learning content
- Curriculum title, topic structure, objectives, and prerequisites for authenticated learners

The product remains useful without an AI provider because every AI feature has a curated or deterministic fallback.

## Provider configuration

The backend uses the OpenAI-compatible SDK with environment-driven settings:

```text
OPENROUTER_API_KEY=your_openrouter_api_key_here
OPENROUTER_BASE_URL=https://openrouter.ai/api/v1
OPENROUTER_MODEL=openrouter/free
```

The key is read only by the backend and is never returned to the frontend or written to logs.

## Context strategy

Prompts receive bounded context from persisted state:

- Learner experience level and goal
- Current persisted learner-curriculum topic metadata
- Relevant weak concepts
- Completed topics
- Recent assessment scores

The prompt tells the model to stay within the supplied topic and curriculum. It does not receive authority to change learner state.

## Structured output and validation

Diagnostic questions, assessment questions, and learning content are represented by Pydantic schemas. The backend validates:

- Required fields and lengths
- Question option indexes
- Unique question IDs
- Minimum concept coverage
- Topic and concept membership
- Exact requested topic ID and title for learning content

Invalid output is rejected and replaced with curated content.

## Deterministic responsibilities

Authentication, password verification, JWT validation, ownership authorization, and database access are deterministic application concerns. AI is never used for security decisions.

Application logic, not the model, controls:

- MCQ scoring
- Concept-level scores
- Historical skill updates
- Weakness thresholds and resolution
- Topic progress
- Prerequisite enforcement
- Path ranking and current position
- Recommendation category
- Database writes and ownership checks

Generated courses are validated and persisted once during onboarding. Later sessions load the same course rather than regenerating it on every refresh.

Topic assessment skill updates use `0.6 * previous_score + 0.4 * latest_score` after the first observation. Weak, developing, and strong thresholds are `<50%`, `50-79%`, and `>=80%`.

## Failure behavior

Missing API keys, provider errors, rate limits, network failures, empty responses, and malformed structured output all route to curated fallback questions or content. Automated tests mock the provider and never make real OpenRouter requests.

## Limitations

The MVP uses AI-domain onboarding and MCQs only. Tutor conversations, retrieval over external documents, refresh-token rotation, httpOnly cookie sessions, and multiple question formats are future work. Free-model output quality can vary, which is why the application validates output and maintains deterministic per-learner fallback material.
