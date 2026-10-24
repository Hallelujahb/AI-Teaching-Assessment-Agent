# Qeleme

AI teaching assessment agent for the AI Agent Hackathon, Project 2. A lecturer picks a batch of short answers. An agent retrieves the rubric and the answers and proposes scores with quoted evidence. Code validates everything. The lecturer corrects and confirms before anything is saved.

Full plan: copy Qeleme_Build_Plan.md into docs/ and read sections 1 to 4 first.

## Layout

- backend/app: FastAPI app, tools, agent, scoring (owners in each file header)
- backend/tests: pytest tests
- backend/schema.sql: database schema
- frontend/src: React with Vite
- seed/: demo assessments and fresh-input samples
- docs/: design note, test report, service register, API examples
- scripts/: dev, reset and smoke test helpers

## Owners

| Person | Area |
| --- | --- |
| P1 | frontend/ |
| P2 | backend/app/routes, tools.py, runs.py, db.py, models.py, config.py, errors.py, limits.py, main.py, schema.sql, setup_db.py, deployment |
| P3 | backend/app/agent.py, ai_provider.py, ai_models.py, prompts.py, check_ai.py |
| P4 | backend/app/scoring.py, stub_model.py, backend/tests/ |
| P5 | seed/, backend/app/seed.py, docs/, scripts/, README, integration tests |

## Run locally

Backend (fill in backend/.env first):

    cd backend
    python3 -m venv .venv
    source .venv/bin/activate
    pip install -r requirements.txt
    cp .env.example .env
    python -m app.check_ai
    python -m app.setup_db
    python -m app.seed

Frontend:

    cd frontend
    npm install
    cp .env.example .env
    npm run dev

After the first successful install, run `pip freeze > requirements.txt` so deployments use the same versions.

## Rules

Never commit .env or any key. Free plans only, no payment details anywhere. Short-lived branches off main, small pull requests, pull before you push.
