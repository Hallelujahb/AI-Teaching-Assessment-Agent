"""GET /api/runs/{run_id}: proposals and tool log.

Owner: P2
Plan: section 7
"""
from fastapi import APIRouter

from .. import runs

router = APIRouter()


@router.get("/api/runs/{run_id}")
def get_run(run_id: str):
    return runs.get_run(run_id)
