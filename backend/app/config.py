"""Reads environment variables. Values are read at call time, so tests can change them.

Variables: DATABASE_URL, AI_BASE_URL, AI_API_KEY, AI_MODEL, ALLOWED_ORIGINS,
DAILY_RUN_CAP, FORCE_AI_FAILURE. Never print any of them.

Owner: P2 (P3 adds AI settings here by tiny append-only PRs)
Plan: section 8
"""
import os

from dotenv import load_dotenv

load_dotenv()

# Limits from plan section 7. The first two also live in scoring.py (same values).
MAX_ANSWER_CHARS = 2000
MAX_ANSWERS_PER_BATCH = 10
MAX_BATCHES_PER_ASSESSMENT = 20
MAX_BODY_BYTES = 50_000
MAX_LABEL_CHARS = 80
STALE_RUN_MINUTES = 5

GRADE_RATE_LIMIT = "5/minute"
BATCH_RATE_LIMIT = "10/minute"


def database_url() -> str:
    url = os.environ.get("DATABASE_URL", "").strip()
    if not url:
        raise RuntimeError("DATABASE_URL is not set")
    return url


def allowed_origins() -> list[str]:
    raw = os.environ.get("ALLOWED_ORIGINS", "")
    return [o.strip().rstrip("/") for o in raw.split(",") if o.strip()]


def daily_run_cap() -> int:
    try:
        return int(os.environ.get("DAILY_RUN_CAP", "40"))
    except ValueError:
        return 40


def force_ai_failure() -> bool:
    return os.environ.get("FORCE_AI_FAILURE", "").strip().lower() not in ("", "0", "false", "no")


def ai_configured() -> bool:
    return all(os.environ.get(k, "").strip() and "replace" not in os.environ.get(k, "").lower()
               for k in ("AI_BASE_URL", "AI_API_KEY", "AI_MODEL"))
