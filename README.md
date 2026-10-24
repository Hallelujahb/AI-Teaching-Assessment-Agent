# Qeleme: AI Teaching Assessment Agent

A lecturer reviews a batch of short answers. An agent retrieves the rubric and answers and proposes scores with explanations; code enforces limits and totals; the lecturer corrects and confirms before anything is saved.

- Live app: TODO (free hosts sleep; the first load can take about a minute)
- Backend: TODO

## Setup
```bash
cd backend && pip install -r requirements.txt
cp .env.example .env                 # placeholders only in the repo; real values stay local
python -m app.setup_db               # create tables
python -m app.seed                   # demo data, safe to run twice
cd ../frontend && npm ci && npm run dev
```
Scripts (run in Git Bash): `bash scripts/smoke_test.sh BACKEND_URL`, `bash scripts/wake_services.sh BACKEND_URL [FRONTEND_URL]`, plus `scripts/dev_backend.sh`, `scripts/dev_frontend.sh`.

## Deploy
TODO (P2): host settings and variable list (see both `.env.example` files).

## Demo order (10 min + 2 min questions and a fresh input)
Live request, clarification, tool log, proposed scores, correct one, confirm, reopen saved scores, show a failure example, judge's fresh answer (`seed/fresh_input_samples.txt`).

## Docs
`docs/api-examples.md`, `design-note.md`, `test-report.md`, `service-register.md`, `contribution-note.md`, `limitations.md`, `gate0-checklist.md`.
