"""List batches and add a batch of answers (the judge's fresh input).

Owner: P2
Plan: section 7
"""
from fastapi import APIRouter, Body, Request

from .. import config
from ..db import get_conn
from ..errors import Conflict, NotFound, Unprocessable, fields_from_errors
from ..limits import limiter
from ..scoring import validate_batch_input

import psycopg

router = APIRouter()


@router.get("/api/assessments/{assessment_id}/batches")
def list_batches(assessment_id: int):
    with get_conn() as conn:
        if not conn.execute("SELECT 1 FROM assessments WHERE id=%s", (assessment_id,)).fetchone():
            raise NotFound("Assessment not found.")
        rows = conn.execute(
            "SELECT b.id, b.label, b.created_at, "
            " (SELECT count(*) FROM submissions s WHERE s.batch_id=b.id)::int AS student_count, "
            " EXISTS (SELECT 1 FROM reviewed_results r JOIN submissions s ON s.id=r.submission_id "
            "         WHERE s.batch_id=b.id) AS confirmed, "
            " (SELECT g.id FROM grading_runs g WHERE g.batch_id=b.id AND g.status='succeeded' "
            "  ORDER BY g.started_at DESC LIMIT 1) AS latest_run_id "
            "FROM submission_batches b WHERE b.assessment_id=%s ORDER BY b.id", (assessment_id,)).fetchall()
    for r in rows:
        r["latest_run_id"] = str(r["latest_run_id"]) if r["latest_run_id"] else None
    return rows


@router.post("/api/assessments/{assessment_id}/batches", status_code=201)
@limiter.limit(config.BATCH_RATE_LIMIT)
def add_batch(request: Request, assessment_id: int, body: dict = Body(...)):
    label = body.get("label")
    label_errors = []
    if not isinstance(label, str) or not label.strip():
        label_errors.append({"field": "label", "message": "A batch name is required"})
    elif len(label.strip()) > config.MAX_LABEL_CHARS:
        label_errors.append({"field": "label", "message": f"The name can be at most {config.MAX_LABEL_CHARS} characters"})

    check = validate_batch_input(body.get("submissions"))
    errors = label_errors + check["errors"]
    if errors:
        raise Unprocessable("The batch is not valid.", fields_from_errors(errors))
    if check["status_code"] == 409:
        ids = ", ".join(check["duplicate_ids"])
        raise Conflict(f"Duplicate student ids: {ids}", {"submissions": ids})

    label = label.strip()
    rows = [(r["student_id"].strip(), r["answer"]) for r in body["submissions"]]
    try:
        with get_conn() as conn:
            if not conn.execute("SELECT 1 FROM assessments WHERE id=%s", (assessment_id,)).fetchone():
                raise NotFound("Assessment not found.")
            count = conn.execute("SELECT count(*) AS n FROM submission_batches WHERE assessment_id=%s",
                                 (assessment_id,)).fetchone()["n"]
            if count >= config.MAX_BATCHES_PER_ASSESSMENT:
                raise Conflict(f"This assessment already has {config.MAX_BATCHES_PER_ASSESSMENT} batches, the maximum.")
            batch_id = conn.execute(
                "INSERT INTO submission_batches (assessment_id, label) VALUES (%s,%s) RETURNING id",
                (assessment_id, label)).fetchone()["id"]
            for student_id, answer in rows:
                conn.execute("INSERT INTO submissions (batch_id, student_id, answer) VALUES (%s,%s,%s)",
                             (batch_id, student_id, answer))
    except psycopg.errors.UniqueViolation:
        raise Conflict("A batch with this name already exists for this assessment.", {"label": "Name already used"})
    return {"id": batch_id, "label": label, "student_count": len(rows)}
