"""Run helpers: create_run, finish_run, save_proposals, stale run cleanup, run views.

A run is one grading attempt. The run row is committed first (status running) so a failed
run still leaves a record. Proposals are saved together with the change to succeeded in
one transaction. Old runs and proposals are never edited.

Owner: P2
Plan: section 5
"""
import uuid

import psycopg
from psycopg.types.json import Json

from . import config
from .errors import Conflict, NotFound
from .scoring import calculate_percentage, calculate_total, evidence_found

LIVE_STATUSES = ("complete", "incomplete", "unassessable", "blank", "needs_manual_grading")


def parse_uuid(value) -> str | None:
    try:
        return str(uuid.UUID(str(value)))
    except (ValueError, AttributeError, TypeError):
        return None


# ---------------------------------------------------------------- run lifecycle


def expire_stale_runs() -> int:
    """Mark runs still running after STALE_RUN_MINUTES as failed. Called before a new run."""
    from .db import get_conn
    with get_conn() as conn:
        cur = conn.execute(
            "UPDATE grading_runs SET status='failed', finished_at=now(), "
            "error='Run took too long and was stopped' "
            "WHERE status='running' AND started_at < now() - make_interval(mins => %s)",
            (config.STALE_RUN_MINUTES,))
        return cur.rowcount


def create_run(batch_id: int, model: str | None, rubric_snapshot: list[dict]) -> str:
    """Create a run (status running), committed at once. Returns the run id as text.

    409 if the batch is already confirmed or another run is running for it."""
    from .db import get_conn
    expire_stale_runs()
    try:
        with get_conn() as conn:
            if not conn.execute("SELECT 1 FROM submission_batches WHERE id=%s", (batch_id,)).fetchone():
                raise NotFound("Batch not found.")
            if conn.execute(
                "SELECT 1 FROM reviewed_results r JOIN submissions s ON s.id=r.submission_id "
                "WHERE s.batch_id=%s LIMIT 1", (batch_id,)).fetchone():
                raise Conflict("This batch is already confirmed and is read-only.")
            row = conn.execute(
                "INSERT INTO grading_runs (batch_id, status, model, rubric_snapshot) "
                "VALUES (%s, 'running', %s, %s) RETURNING id",
                (batch_id, model, Json(rubric_snapshot))).fetchone()
        return str(row["id"])
    except psycopg.errors.UniqueViolation:
        raise Conflict("A grading run is already in progress for this batch. Wait for it to finish.")


def finish_run(run_id: str, status: str, error: str | None = None) -> None:
    """Close a running run as 'failed' (or 'succeeded'). Does nothing if it already finished."""
    from .db import get_conn
    if status not in ("failed", "succeeded"):
        raise ValueError("status must be failed or succeeded")
    with get_conn() as conn:
        conn.execute(
            "UPDATE grading_runs SET status=%s, error=%s, finished_at=now() WHERE id=%s AND status='running'",
            (status, error[:500] if error else None, run_id))


def save_proposals(run_id: str, proposals: list[dict]) -> None:
    """Save one proposal per submission and mark the run succeeded, in ONE transaction.

    Each proposal needs student_id (or submission_id), answer_status, scores, evidence,
    explanations, flags and feedback (what scoring.build_proposals returns). Extra keys such
    as total, percentage and evidence_check are ignored: they are recomputed when read.
    Raises ValueError if the proposals do not cover the batch exactly once, and Conflict if
    the run is no longer running."""
    from .db import get_conn
    with get_conn() as conn:
        run = conn.execute("SELECT batch_id, status FROM grading_runs WHERE id=%s FOR UPDATE", (run_id,)).fetchone()
        if not run:
            raise NotFound("Run not found.")
        if run["status"] != "running":
            raise Conflict("This run is no longer running, so its results were not saved.")
        subs = conn.execute("SELECT id, student_id FROM submissions WHERE batch_id=%s", (run["batch_id"],)).fetchall()
        by_student = {s["student_id"]: s["id"] for s in subs}
        valid_ids = set(by_student.values())
        seen: set[int] = set()
        rows = []
        for p in proposals:
            sub_id = p.get("submission_id") if p.get("submission_id") in valid_ids else by_student.get(p.get("student_id"))
            if sub_id is None:
                raise ValueError(f"Proposal for unknown student {p.get('student_id')!r}")
            if sub_id in seen:
                raise ValueError(f"Two proposals for student {p.get('student_id')!r}")
            if p.get("answer_status") not in LIVE_STATUSES:
                raise ValueError(f"Invalid answer_status {p.get('answer_status')!r}")
            seen.add(sub_id)
            rows.append((run_id, sub_id, p["answer_status"], Json(p.get("scores") or {}),
                         Json(p.get("evidence") or {}), Json(p.get("explanations") or {}),
                         Json(p.get("flags") or []), p.get("feedback") or ""))
        if seen != valid_ids:
            raise ValueError("Proposals must cover every submission in the batch exactly once")
        for r in rows:
            conn.execute(
                "INSERT INTO ai_proposals (run_id, submission_id, answer_status, scores, evidence, "
                "explanations, flags, feedback) VALUES (%s,%s,%s,%s,%s,%s,%s,%s)", r)
        conn.execute("UPDATE grading_runs SET status='succeeded', finished_at=now(), error=NULL WHERE id=%s", (run_id,))


def latest_succeeded_run_id(conn, batch_id: int) -> str | None:
    row = conn.execute(
        "SELECT id FROM grading_runs WHERE batch_id=%s AND status='succeeded' "
        "ORDER BY started_at DESC, finished_at DESC LIMIT 1", (batch_id,)).fetchone()
    return str(row["id"]) if row else None


def count_runs_today() -> int:
    """Runs started today (database clock, UTC). Used for DAILY_RUN_CAP."""
    from .db import get_conn
    with get_conn() as conn:
        return conn.execute(
            "SELECT count(*) AS n FROM grading_runs WHERE started_at >= date_trunc('day', now())").fetchone()["n"]


# ---------------------------------------------------------------- views for the UI


def proposal_view(row: dict, rubric: list[dict], max_total: int) -> dict:
    """One student's proposal in the shape the frontend shows (see docs/api-examples.md).

    row needs: student_id, answer, answer_status, scores, evidence, explanations, flags, feedback.
    Evidence status is recomputed from the stored quote and the student's answer:
    found, none (no quote) or not_found."""
    scores = row.get("scores") or {}
    evidence = row.get("evidence") or {}
    explanations = row.get("explanations") or {}
    criteria = []
    values = []
    for c in rubric:
        key = str(c["id"])
        quote = evidence.get(key) or ""
        status = evidence_found(quote, row.get("answer") or "")
        score = scores.get(key)
        values.append(score)
        criteria.append({
            "criterion_id": c["id"], "name": c.get("name"), "max_score": c["max_score"],
            "proposed_score": score, "evidence": quote,
            "evidence_status": status,
            "evidence_found": None if status == "none" else status == "found",
            "explanation": explanations.get(key) or "",
        })
    total = pct = None
    if values and all(isinstance(v, int) and not isinstance(v, bool) for v in values):
        total = calculate_total(values)
        pct = calculate_percentage(total, max_total) if max_total > 0 and 0 <= total <= max_total else None
    return {
        "student_id": row["student_id"], "answer": row.get("answer") or "",
        "answer_status": row["answer_status"], "criteria": criteria,
        "feedback": row.get("feedback") or "", "attention_flags": row.get("flags") or [],
        "proposed_total": total, "proposed_percentage": pct,
    }


def get_run(run_id: str) -> dict:
    """GET /api/runs/{id}: the run, its proposals and its tool log."""
    from .db import get_conn
    rid = parse_uuid(run_id)
    if not rid:
        raise NotFound("Run not found.")
    with get_conn() as conn:
        run = conn.execute(
            "SELECT g.id, g.batch_id, g.status, g.model, g.rubric_snapshot, g.started_at, g.finished_at, g.error, "
            "b.assessment_id, b.label FROM grading_runs g JOIN submission_batches b ON b.id=g.batch_id "
            "WHERE g.id=%s", (rid,)).fetchone()
        if not run:
            raise NotFound("Run not found.")
        rubric = run["rubric_snapshot"] or []
        max_total = sum(c["max_score"] for c in rubric)
        rows = conn.execute(
            "SELECT s.student_id, s.answer, p.answer_status, p.scores, p.evidence, p.explanations, p.flags, p.feedback "
            "FROM ai_proposals p JOIN submissions s ON s.id=p.submission_id WHERE p.run_id=%s ORDER BY s.id",
            (rid,)).fetchall()
        logs = conn.execute(
            "SELECT tool_name, arguments, outcome, duration_ms, created_at FROM tool_logs WHERE run_id=%s ORDER BY id",
            (rid,)).fetchall()
        is_latest = latest_succeeded_run_id(conn, run["batch_id"]) == rid
    return {
        "run_id": rid, "batch_id": run["batch_id"], "assessment_id": run["assessment_id"],
        "batch_label": run["label"], "status": run["status"], "model": run["model"],
        "error": run["error"], "started_at": run["started_at"], "finished_at": run["finished_at"],
        "is_latest": is_latest, "max_total": max_total,
        "rubric": [{"id": c["id"], "position": c.get("position"), "name": c.get("name"),
                    "max_score": c["max_score"]} for c in rubric],
        "proposals": [proposal_view(r, rubric, max_total) for r in rows],
        "tool_log": logs,
    }
