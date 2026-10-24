"""The three tools: get_assessment_criteria, get_submissions, save_reviewed_results.

Each tool takes an optional run_id. When a run id is given, the call is written to
tool_logs (also when it fails), in its own transaction so the log survives a failure.
Routes that read data for the web page call the plain fetch_* functions (no run, no log).

Owner: P2
Plan: section 4
"""
import logging
import time

import psycopg
from psycopg.types.json import Json

from . import runs
from .db import get_conn
from .errors import Conflict, NotFound, Unprocessable, fields_from_errors
from .scoring import validate_review

log = logging.getLogger("qeleme")


# ---------------------------------------------------------------- tool log


def _write_log(run_id, tool_name, arguments, outcome, started):
    """Never raises: a logging problem must not break the tool call."""
    if not run_id:
        return
    try:
        with get_conn() as conn:
            conn.execute(
                "INSERT INTO tool_logs (run_id, tool_name, arguments, outcome, duration_ms) VALUES (%s,%s,%s,%s,%s)",
                (run_id, tool_name, Json(arguments), outcome[:300], int((time.perf_counter() - started) * 1000)))
    except Exception:  # noqa: BLE001
        log.warning("Could not write tool log for %s", tool_name)


def _logged(run_id, tool_name, arguments, fn):
    started = time.perf_counter()
    try:
        result = fn()
    except Exception as exc:  # noqa: BLE001
        _write_log(run_id, tool_name, arguments, f"error: {getattr(exc, 'message', None) or type(exc).__name__}", started)
        raise
    _write_log(run_id, tool_name, arguments, "ok", started)
    return result


# ---------------------------------------------------------------- plain reads (used by routes)


def fetch_assessments() -> list[dict]:
    with get_conn() as conn:
        return conn.execute("SELECT id, title FROM assessments ORDER BY id").fetchall()


def fetch_assessment(assessment_id: int) -> dict:
    with get_conn() as conn:
        a = conn.execute("SELECT id, title, question, reference_answer FROM assessments WHERE id=%s",
                         (assessment_id,)).fetchone()
        if not a:
            raise NotFound("Assessment not found.")
        rubric = conn.execute(
            "SELECT id, position, name, description, max_score FROM rubric_criteria "
            "WHERE assessment_id=%s ORDER BY position", (assessment_id,)).fetchall()
    a["rubric"] = rubric
    a["max_total"] = sum(c["max_score"] for c in rubric)
    return a


def fetch_batch_submissions(assessment_id: int, batch_id: int) -> dict:
    with get_conn() as conn:
        b = conn.execute("SELECT id, label FROM submission_batches WHERE id=%s AND assessment_id=%s",
                         (batch_id, assessment_id)).fetchone()
        if not b:
            raise NotFound("Batch not found for this assessment.")
        subs = conn.execute("SELECT student_id, answer FROM submissions WHERE batch_id=%s ORDER BY id",
                            (batch_id,)).fetchall()
    return {"assessment_id": assessment_id, "batch_id": batch_id, "label": b["label"], "submissions": subs}


def assessment_id_for_batch(batch_id: int) -> int:
    with get_conn() as conn:
        row = conn.execute("SELECT assessment_id FROM submission_batches WHERE id=%s", (batch_id,)).fetchone()
    if not row:
        raise NotFound("Batch not found.")
    return row["assessment_id"]


# ---------------------------------------------------------------- the three tools


def get_assessment_criteria(assessment_id: int, run_id: str | None = None) -> dict:
    """Question, reference answer, rubric rows with max scores, and the maximum total."""
    return _logged(run_id, "get_assessment_criteria", {"assessment_id": assessment_id},
                   lambda: fetch_assessment(assessment_id))


def get_submissions(assessment_id: int, batch_id: int, run_id: str | None = None) -> dict:
    """The batch's student answers (student_id and answer)."""
    return _logged(run_id, "get_submissions", {"assessment_id": assessment_id, "batch_id": batch_id},
                   lambda: fetch_batch_submissions(assessment_id, batch_id))


def save_reviewed_results(assessment_id: int, batch_id: int, run_id: str, results: list) -> dict:
    """Confirm the lecturer's reviewed results. One transaction, all students or nobody.

    Refuses with 409 if the batch is already confirmed or run_id is not the latest succeeded
    run, and with 422 (field errors from scoring.validate_review) for bad input. Totals and
    percentages are always calculated here, never taken from the client."""
    args = {"assessment_id": assessment_id, "batch_id": batch_id,
            "students": len(results) if isinstance(results, list) else None}
    return _logged(run_id if runs.parse_uuid(run_id) else None, "save_reviewed_results", args,
                   lambda: _save_reviewed_results(assessment_id, batch_id, run_id, results))


def _save_reviewed_results(assessment_id, batch_id, run_id, results) -> dict:
    rid = runs.parse_uuid(run_id)
    if not rid:
        raise Unprocessable("The review request is not valid.", {"run_id": "run_id is required"})
    try:
        with get_conn() as conn:
            batch = conn.execute("SELECT id FROM submission_batches WHERE id=%s AND assessment_id=%s FOR UPDATE",
                                 (batch_id, assessment_id)).fetchone()
            if not batch:
                raise NotFound("Batch not found for this assessment.")
            if conn.execute("SELECT 1 FROM reviewed_results r JOIN submissions s ON s.id=r.submission_id "
                            "WHERE s.batch_id=%s LIMIT 1", (batch_id,)).fetchone():
                raise Conflict("This batch is already confirmed.")
            latest = runs.latest_succeeded_run_id(conn, batch_id)
            if latest is None or latest != rid:
                raise Conflict("A newer grading run exists or this run is not available. Reload the review.")
            run = conn.execute("SELECT rubric_snapshot FROM grading_runs WHERE id=%s", (rid,)).fetchone()
            rubric = run["rubric_snapshot"]
            proposals = conn.execute(
                "SELECT p.id AS proposal_id, p.submission_id, s.student_id, p.answer_status "
                "FROM ai_proposals p JOIN submissions s ON s.id=p.submission_id WHERE p.run_id=%s ORDER BY s.id",
                (rid,)).fetchall()
            check = validate_review({"run_id": rid, "results": results}, rubric, proposals)
            if not check["valid"]:
                raise Unprocessable("The review is not valid.", fields_from_errors(check["errors"]))
            by_student = {p["student_id"]: p for p in proposals}
            approved_at = None
            out = []
            for r in check["results"]:
                p = by_student[r["student_id"]]
                row = conn.execute(
                    "INSERT INTO reviewed_results (submission_id, proposal_id, run_id, scores, total, percentage, feedback) "
                    "VALUES (%s,%s,%s,%s,%s,%s,%s) RETURNING approved_at",
                    (p["submission_id"], p["proposal_id"], rid, Json(r["scores"]), r["total"],
                     r["percentage"], r["feedback"])).fetchone()
                approved_at = row["approved_at"]
                out.append({"student_id": r["student_id"], "total": r["total"], "percentage": float(r["percentage"])})
    except psycopg.errors.UniqueViolation:
        raise Conflict("This batch is already confirmed.")
    return {"batch_id": batch_id, "run_id": rid, "approved_at": approved_at,
            "max_total": sum(c["max_score"] for c in rubric), "results": out}
