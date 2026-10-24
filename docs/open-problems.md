# Open problems (keep short; remove a line when fixed)

| # | Problem | Owner |
| --- | --- | --- |
| 1 | FIXED: `python -m pytest` collection passes; imports in test_agent.py, test_ai_provider.py, test_parser.py and fakes.py resolve to current modules | P3 |
| 2 | design-note.md, limitations.md, service-register.md and task_board.md describe things the code does not have (DAILY_MODEL_REQUEST_CAP, model_requests column, get_provider, catalog) | P3 and P5 |
| 3 | Clarification response shape: code returns status plus a text clarification; confirm the frontend reads the same | P1 |
| 4 | AI variable names differ between check_ai.py (OPENROUTER_API_KEY, AI_PROVIDER) and config.py (AI_API_KEY, AI_BASE_URL, AI_MODEL); .env.example needs the real provider | P3 |
| 5 | DAILY_RUN_CAP=40 is above what the free AI quota allows (about 2 to 4 requests per run) | P2 and P3 |
| 6 | Backend and frontend are not deployed, so Gate 1 cannot pass | P2 and P1 |
| 7 | Organizer answer on the save tool is not recorded | P5 |
| 8 | Frontend pages are stubs | P1 |
| 9 | Database tests are skipped until TEST_DATABASE_URL points at a throwaway database | P5 |
| 10 | FIXED: `make_nonce` is available in app.prompts (and tests collect) | P3 |
| 11 | FIXED: `ProviderResponse`, `get_provider`, `StubProvider` and `_STUB_TOOL_CALLS` resolve in app.ai_provider | P3 |
| 12 | FIXED: parser/prompt helpers resolve in app.prompts | P3 |
| 13 | FIXED: `FORCE_AI_FAILURE=1` returns a quota error before any provider or tool call | P3 |
| 14 | `catalog()` is missing from the tools layer, so free-text assessment/batch resolution is not integrated with the database | P2 |
| 15 | `create_run` requires a non-null `batch_id`, so the clarification path cannot create a run for an unresolved request | P2 |
