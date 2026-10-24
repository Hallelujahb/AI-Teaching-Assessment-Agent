# Qeleme: AI Teaching Assessment Agent

A lecturer reviews a batch of short answers. An agent retrieves the rubric and answers and proposes scores with explanations; code enforces limits and totals; the lecturer corrects and confirms before anything is saved.

- Live app: TODO (free hosts sleep; the first load can take about a minute)
- Backend: TODO

## Setup (Windows, PowerShell)
```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env          # placeholders only in the repo; put real values in .env, never commit it
python -m app.setup_db               # create tables
python -m app.seed                   # demo data, safe to run twice
python -m pytest                     # logic tests; database tests are skipped unless TEST_DATABASE_URL is set
uvicorn app.main:app --port 8000
```
Frontend: `cd frontend; npm ci; npm run dev`.
Reset the demo data (wipes runs, proposals, results and added batches): `python -m app.seed --reset`. Never run it just before judging.
Scripts (run in Git Bash): `bash scripts/smoke_test.sh BACKEND_URL`, `bash scripts/wake_services.sh BACKEND_URL [FRONTEND_URL]`.

## Configuration
Backend (see `backend/.env.example`): `DATABASE_URL`, `AI_BASE_URL`, `AI_API_KEY`, `AI_MODEL`, `ALLOWED_ORIGINS`, `DAILY_RUN_CAP`, `FORCE_AI_FAILURE` (leave empty; set to 1 only for the failure test). `TEST_DATABASE_URL` is for pytest only and must be a throwaway database.
Frontend (see `frontend/.env.example`): `VITE_API_BASE_URL`, read at build time.

## Deploy
TODO (P2): host settings and the variable list for each host.

## Demo order (10 min + 2 min questions and a fresh input)
Live request, clarification, tool log, proposed scores, correct one, confirm, reopen saved scores, show a failure example, judge's fresh answer (`seed/fresh_input_samples.txt`).

## Docs
`docs/api-examples.md`, `docs/design-note.md`, `docs/test-report.md`, `docs/service-register.md`, `docs/contribution-note.md`, `docs/limitations.md`, `docs/gate0-checklist.md`, `docs/rule-coverage.md`, `docs/design-note-validation.md`, `docs/open-problems.md`.