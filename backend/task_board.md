# Task Board - Part G Steps

## Phase 0: zero dependencies. Start now (about T+0:00 to 1:30).

### 0.1 D2: `ai_models.py` (READY) ✅
- Pasted Pydantic code into `backend/app/ai_models.py`
- Verified import works with Python 3.12
- Types: CriterionGrade, ModelStudentGrade, ModelOutput, ProposalStatus

### 0.2 Gate 0: `check_ai.py` (READY-TO-DO) 🟡
- Run `python -m app.check_ai` from `backend/`
- List free models that support tools
- Print id, context length and whether `structured_outputs` is listed
- Run one tiny function-calling request per candidate (at most 4)
- Test tools together with a response format on the best candidate
- Print a report for Person 5 (model ID, limits, what worked)

### 0.3 `ai_provider.py` (BLOCKED)
- Needs OpenRouter Provider and StubProvider implementation
- Waits for Gate 0 model selection

### 0.4 `prompts.py` and parser (BLOCKED)
- Needs Appendix A prompts and `parse_model_output`
- Waits for model selection from Gate 0

### 0.5 Tool declarations (BLOCKED)
- JSON schemas for the two retrieval tools only
- Waits for model selection

### 0.6 `agent.py` against the ports (BLOCKED)
- Needs FakeTools, InMemoryRuns, loop, caps, retry
- Waits for model/tool decisions from Gate 0

### 0.7 Send handoffs and requests (BLOCKED)
- Five gap requests to Persons 2, 4, 5
- Clarification shape to Person 1
- Pending Gate 0 outcome

### 0.8 Draft design note (BLOCKED)
- D21 section and AI limitations
- Pending Gate 0 and D19 outcomes

## Phase 1: gated by dependencies

### 1.1 D7 + D8 land (T+1:30): write adapters
- Write ToolsPort and RunsPort adapters

### 1.2 D6 (T+1:30 to 2:00): host secrets
- Set OPENROUTER_API_KEY, AI_MODEL, AI_PROVIDER

### 1.3 D12 + D13 (T+1:15 / T+2:15): scoring stand-ins
- Swap real scoring.py stand-ins

### 1.4 D9 lands (T+2:30): save_proposals
- Call save_proposals once at end of run_grading

### 1.5 Noon mini-gate (T+3:00): deployed grade request
### 1.6 Gate 2 (T+3:30): happy path on public link

### 1.7 D18 lands: stub_model.py
- StubProvider delegates to stub_model.py

### 1.8 Hardening (T+3:30 to 4:30): error mapping, cap tests
### 1.9 D21 (T+4:30): design note section

## Tests needed (pytest not installed yet)
- tool cap and turn cap end run as failed
- timeout path
- unknown id never reaches tools
- blank/short answers never in model messages
- nonce delimiters present
- clarification returns without tool calls
- invalid output triggers exactly one retry
- student still invalid after retry → needs_manual_grading
- out-of-range stub score not accepted
- FORCE_AI_FAILURE=1 gives zero provider/tool calls
- all parser variants
- error mapping for 429, 402, 503, empty choices, error body
