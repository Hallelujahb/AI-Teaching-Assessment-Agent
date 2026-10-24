# Gate 0 checklist (record of what actually passed)

| Check | Owner | Result | Notes |
| --- | --- | --- | --- |
| AI key made with billing off; chosen model answers a function-calling call; limits written down | P3 | TODO | Model, rate limits |
| Account region and age eligibility for the AI service | P3 | TODO | |
| Remote database created with no payment details, reachable | P2 | TODO | |
| Backend host serves HTTPS with no payment details | P2 | TODO | |
| Frontend host serves a page with no payment details | P1 | TODO | |
| Every coding assistant is on a free plan | All | TODO | |

Never add a card or enable billing. Switch services and update the register instead.

## Gate 0 procedure (Person 3)

Run `python -m app.check_ai` from `backend/`.

1. Fetch `GET https://openrouter.ai/api/v1/models?supported_parameters=tools` and filter to `:free` models with zero pricing.
2. Print id, context length, and whether `structured_outputs` is listed for each candidate.
3. Send one tiny function-calling request per candidate (at most 4 candidates).
4. Send one more request testing tools **together with** `response_format=json_object` on the best candidate.
5. Print a report: model ID, 20 req/min / 50 req/day limits, whether tools+format work together, and the resulting strategy (single loop vs tool loop + final schema call).

**If no free model passes tool calling:** the provider interface (`ai_provider.py`) lets a Gemini or Groq provider drop in via `AI_PROVIDER=gemini|groq`. Report this within 30 minutes.

**Reminders for the team:**
- Check the OpenRouter dashboard for account free-tier status and usage.
- `AI_MODEL` must be pinned to one explicit model ID (e.g. `provider/model:free`), not `openrouter/free`.
- `max_retries=0` is set in the OpenAI client to avoid burning quota on retries.
- `FORCE_AI_FAILURE=1` is available for Gate 2 testing without spending requests.
