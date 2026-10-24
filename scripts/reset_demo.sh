#!/usr/bin/env bash
# Wipes runs, proposals, results and added batches, then reseeds. Uses DATABASE_URL from backend/.env
cd "$(dirname "$0")/../backend" && source .venv/bin/activate && python -m app.seed --reset
