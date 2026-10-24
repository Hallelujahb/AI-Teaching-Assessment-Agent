# Open problems (keep short; remove a line when fixed)

| # | Problem | Owner |
| --- | --- | --- |
| 1 | `python -m pytest` may fail at collection: test_agent.py, test_ai_provider.py, test_parser.py and fakes.py import names that are not in the current ai_provider.py, prompts.py or agent.py | P3 |
| 2 | design-note.md, limitations.md, service-register.md and task_board.md describe things the code does not have (DAILY_MODEL_REQUEST_CAP, model_requests column, get_provider, catalog) | P3 and P5 |
| 3 | Clarification response shape: code returns status plus a text clarification; confirm the frontend reads the same | P1 |
| 4 | AI variable names differ between check_ai.py (OPENROUTER_API_KEY, AI_PROVIDER) and config.py (AI_API_KEY, AI_BASE_URL, AI_MODEL); .env.example needs the real provider | P3 |
| 5 | DAILY_RUN_CAP=40 is above what the free AI quota allows (about 2 to 4 requests per run) | P2 and P3 |
| 6 | Backend and frontend are not deployed, so Gate 1 cannot pass | P2 and P1 |
| 7 | Organizer answer on the save tool is not recorded | P5 |
| 8 | Frontend pages are stubs | P1 |
| 9 | Database tests are skipped until TEST_DATABASE_URL points at a throwaway database | P5 |