#!/usr/bin/env bash
cd "$(dirname "$0")/../backend" && source .venv/bin/activate && uvicorn app.main:app --reload --port 8000
