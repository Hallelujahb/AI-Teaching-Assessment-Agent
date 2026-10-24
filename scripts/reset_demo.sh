#!/usr/bin/env bash
# Wipes runs, proposals, results and added batches, then reseeds. Uses DATABASE_URL from backend/.env
# Run from a laptop only. It deletes demo data, so never run it just before judging.
cd "$(dirname "$0")/../backend" && python -m app.seed --reset
