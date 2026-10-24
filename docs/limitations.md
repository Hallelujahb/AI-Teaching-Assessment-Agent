# Known limitations (AI section, Person 3)

By scope (guide): short text answers only; demo-size data (one question, three answers); no handwriting recognition, plagiarism detection or student portal.

By hosting: free hosts sleep, so the first load after idle is slow; free AI quota is limited.

By AI provider:
- OpenRouter free models allow 20 requests per minute and 50 per day on a non-billing account. Failed requests can count against this allowance, so `max_retries=0` and there are no automatic retries. A manual retry button is the only retry path (plus the agent's single validation retry).
- Not every free model supports function calling or JSON schemas. Gate 0 tests this before the model ID is pinned.
- `AI_MODEL` is pinned to one explicit `:free` model for reproducibility. The `openrouter/free` router is not used because it picks a random free model.
- Free models may wrap output in markdown fences, think blocks, or extra prose; the parser strips these but complex nesting can still cause `invalid_output`.
- The daily request cap is enforced in `limits.py` and set to 40 (out of 50) to reserve 10 for the demo and judges' fresh input.

Injection protection is a prompt rule plus a code-layer heuristic that catches obvious instruction-like text in answers, so it is not a guarantee against subtle prompt injection. See also: only obvious injection attempts are detected; sophisticated ones may pass and should be caught during lecturer review.

Other limits (from the code):
- A batch holds at most 10 answers of at most 2,000 characters; an assessment holds at most 20 batches.
- Once a batch is confirmed it is read-only; a regrade needs a new batch.
- Rate limits are kept in memory, so they reset when the free host restarts.
- Seed data is fictitious: two assessments, three short answers each.
