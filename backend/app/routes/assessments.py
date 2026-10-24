"""GET /api/assessments and GET /api/assessments/{id}.

Owner: P2
Plan: section 7
"""
from fastapi import APIRouter

from .. import tools

router = APIRouter()


@router.get("/api/assessments")
def list_assessments():
    return tools.fetch_assessments()


@router.get("/api/assessments/{assessment_id}")
def get_assessment(assessment_id: int):
    return tools.fetch_assessment(assessment_id)
