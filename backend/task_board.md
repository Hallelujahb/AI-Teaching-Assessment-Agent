# Task Board - Part G Steps

## Phase 0: zero dependencies. Start now (about T+0:00 to 1:30).

### 0.1 D2: `ai_models.py` (DONE) ✅
- Pydantic types: CriterionGrade, ModelStudentGrade, ProposalStatus
- Lenient `proposed_score: Any` per rule-coverage.md handoff note
- Verified import with Python 3.12

### 0.2 Gate 0: `check_ai.py` (DONE) ✅
- Fetches OpenRouter free models list, filters to :free with zero pricing
- Probes up to 4 candidates with one function-calling request each
- Tests tools + response_format on best candidate
- Prints report for Person 5

### 0.3 `ai_provider.py` (DONE) ✅
- `generate()` interface (ProviderResponse: text, tool_calls, usage)
- `OpenRouterProvider` via openai SDK (max_retries=0)
- `StubProvider` on scripted fake
- Error mapping: timeout, quota (429/402/503), invalid_output
- `FORCE_AI_FAILURE` support
- `tests/test_ai_provider.py`

### 0.4 `prompts.py` + parser (DONE) ✅
- System prompt, message builders (catalog context, answer blocks with nonce)
- Tool schemas for get_assessment_criteria + get_submissions (NOT save)
- `parse_model_output`: strips think/boxed/fences, balanced JSON extraction
- `tests/test_parser.py`

### 0.5 Tool declarations (DONE) ✅
- JSON schemas in `prompts.tool_schemas()` for the two retrieval tools only

### 0.6 `agent.py` + fakes + tests (DONE) ✅
- `agent.py`: loop, caps (turns/tools/timeout), id guard, sanitising, retry-once, proposal building
- `tests/fakes.py`: FakeTools, InMemoryRuns, FakeScoring, StubProvider helpers
- `tests/test_agent.py`: all required test cases
- `tests/test_parser.py`: all parser variants
- `tests/test_ai_provider.py`: error mapping

### 0.7 Handoffs and requests (DONE) ✅
- Five gap requests sent (see messages below)
- Proposal shape to Person 2
- Clarification shape to Person 1 (D16)

### 0.8 Draft design note (DONE) ✅
- Agent section, AI limitations, Gate 0 procedure

## Phase 1: gated by dependencies (C3 scan shows)

| D# | File | Status from scan |
|---|---|---|
| D2 | ai_models.py | READY |
| D3 | seed/assessments/*.json | READY (js101.json); py101.json is placeholder |
| D7 | tools.py | READY (get_assessment_criteria, get_submissions exist; catalog() MISSING) |
| D8 | runs.py | READY (create_run, finish_run exist) |
| D9 | runs.py: save_proposals | READY |
| D12 | scoring: detect_answer_status | READY |
| D13 | scoring: validate_model_output | READY |
| D18 | stub_model.py | READY |
| Config | config.py: AI settings | MISSING (has DATABASE_URL, AI_BASE_URL, AI_API_KEY, AI_MODEL, DAILY_RUN_CAP, FORCE_AI_FAILURE only) |
| Config | .env.example | MISSING (no OPENROUTER_API_KEY, AI_PROVIDER, AI_FALLBACK_MODELS, STRUCTURED_MODE, MAX_MODEL_TURNS, etc.) |
| Errors | errors.py: AIError | READY (exists at line 74) |
| Schema | model_requests column | MISSING |
| Limits | DAILY_MODEL_REQUEST_CAP | MISSING |
| Route | routes/grading.py | READY (calls run_grading) |

**BLOCKED messages to send:**
1. **Person 2 — catalog():** `get_assessment_criteria` and `get_submissions` exist in tools.py but `catalog()` does not. The agent needs a read-only catalog (assessment ids + titles, batch ids + labels) to resolve free-text requests. Request: add `catalog()` to tools.py backed by the same queries as `routes/assessments.py` + `routes/batches.py`. Workaround: agent uses injected catalog from FakeTools in tests; production returns empty list until catalog() lands.

2. **Person 2 — create_run nullable batch_id:** `create_run(batch_id, model, rubric_snapshot)` requires a non-null `batch_id`, but the free-text path may not resolve one before the run is created (on clarification, no batch exists). Request: make `batch_id` nullable in `runs.py`, add `attach_run_context(run_id, batch_id, rubric_snapshot)`, and allow a run status/outcome of "needs_clarification". Workaround: agent uses a synthetic UUID run id when create_run fails.

3. **Person 2 — model_requests counter:** `schema.sql` `grading_runs` table has no `model_requests` column. Request: add `model_requests INT DEFAULT 0` to `grading_runs`, increment it per outbound request in `runs.py`, and enforce `DAILY_MODEL_REQUEST_CAP=40` in `limits.py` alongside `DAILY_RUN_CAP`. Workaround: in-process counter in tests.

4. **Person 4 — raw parse leniency:** `ai_models.py` uses `proposed_score: Any` (lenient). Confirm this is the agreed approach so one bad score doesn't crash the whole batch parse. If P4 wants strict `int`, adjust and the parser will reject the batch.

5. **Person 4 — unassessable rule:** The stub sets all scores to 0 for unassessable answers. Confirm this is the agreed rule (G4 gap 5).

**Proposal shape for Person 2** (sent with run_grading return):
One dict per submission: `{"student_id", "answer_status", "scores": {cid_str: int|None}, "evidence": {cid_str: str}, "explanations": {cid_str: str}, "flags": list[str], "feedback": str, "total": int|None, "percentage": float|None}`.

**Clarification shape for Person 1** (D16):
`{"outcome": "needs_clarification", "run_id": str|null, "clarification": {"question": str}}`

## Tests needed (all written, pytest available)
- ✅ tool cap and turn cap end run as failed → test_agent.py
- ✅ timeout path → test_agent.py
- ✅ unknown id never reaches tools → test_agent.py
- ✅ blank and short answers never in model messages → test_agent.py
- ✅ nonce delimiters present → test_agent.py
- ✅ clarification returns without tool calls → test_agent.py
- ✅ invalid output triggers exactly one retry → test_agent.py
- ✅ student still invalid after retry → needs_manual_grading → test_agent.py
- ✅ out-of-range stub score not accepted → test_agent.py
- ✅ FORCE_AI_FAILURE=1 → zero provider/tool calls → test_agent.py
- ✅ all parser variants → test_parser.py
- ✅ error mapping for 429, 402, 503, empty choices, error body → test_ai_provider.py
- ✅ injection sample produces flags or rejection → test_agent.py
