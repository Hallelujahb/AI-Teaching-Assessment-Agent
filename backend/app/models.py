"""Pydantic request models for the API.

Batch and review bodies are checked by scoring.validate_batch_input and
scoring.validate_review (P4) so the 409 and 422 field errors come from one place.
ModelOutput and friends live in ai_models.py (P3 and P4).

Owner: P2
Plan: section 7
"""
from typing import Optional

from pydantic import BaseModel, Field


class GradeRequest(BaseModel):
    """POST /api/agent/grade. Everything is optional so the clarification path works."""
    request: Optional[str] = Field(default=None, max_length=500)
    assessment_id: Optional[int] = None
    batch_id: Optional[int] = None
