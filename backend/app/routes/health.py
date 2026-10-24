"""GET /api/health. Never calls the model. Always answers 200 so the host keeps the service up;
read the fields to see what is wrong.

Owner: P2
Plan: section 7
"""
from fastapi import APIRouter

from .. import config
from ..db import get_conn

router = APIRouter()


@router.get("/api/health")
def health():
    try:
        with get_conn() as conn:
            conn.execute("SELECT 1")
        database = "ok"
    except Exception:  # noqa: BLE001
        database = "error"
    return {"backend": "ok", "database": database,
            "ai": "configured" if config.ai_configured() else "not_configured"}
