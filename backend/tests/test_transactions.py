"""With P2: confirm is one transaction, and a second confirm is refused.

Needs TEST_DATABASE_URL (see conftest). These tests assume the planned signature
``save_reviewed_results(assessment_id, batch_id, run_id, results)`` where ``results`` is a
list of {"student_id", "scores": [{"criterion_id", "score"}], "feedback"}. A refusal may be
an exception or a returned error; both are accepted. The assertion that matters is the row
count: nothing partial is ever left behind.
"""
import json
import uuid

import pytest

pytestmark = pytest.mark.db


def make_run(conn, batch):
    """A succeeded run with one proposal per student, written straight to the tables."""
    from psycopg.types.json import Json
    cur = conn.cursor()
    rid = str(uuid.uuid4())
    snapshot = [{"id": c, "max_score": m, "position": i + 1, "name": f"c{c}", "description": ""}
                for i, (c, m) in enumerate(batch["criteria"])]
    cur.execute("INSERT INTO grading_runs (id, batch_id, status, model, rubric_snapshot, started_at, finished_at) "
                "VALUES (%s,%s,'succeeded','stub',%s,now(),now())", (rid, batch["batch_id"], Json(snapshot)))
    props = {}
    for sid, subid in batch["submissions"].items():
        zero = {str(c): 0 for c, _ in batch["criteria"]}
        cur.execute("INSERT INTO ai_proposals (run_id, submission_id, answer_status, scores, evidence, explanations, flags) "
                    "VALUES (%s,%s,'complete',%s,%s,%s,%s) RETURNING id",
                    (rid, subid, Json(zero), Json({}), Json({}), Json([])))
        props[sid] = cur.fetchone()[0]
    return rid, props


def payload(batch, scores_by_student):
    return [{"student_id": sid,
             "scores": [{"criterion_id": c, "score": s} for (c, _), s in zip(batch["criteria"], scores)],
             "feedback": ""}
            for sid, scores in scores_by_student.items()]


def count(conn, batch):
    cur = conn.cursor()
    cur.execute("SELECT count(*) FROM reviewed_results WHERE submission_id IN %s", (tuple(batch["submissions"].values()),))
    return cur.fetchone()[0]


def attempt(batch, run_id, results):
    from app.tools import save_reviewed_results
    try:
        return save_reviewed_results(batch["assessment_id"], batch["batch_id"], run_id, results)
    except Exception as exc:  # noqa: BLE001 - a refusal may be any exception type
        return exc


def test_valid_confirm_writes_every_student_once(conn, scratch_batch, client):
    rid, _ = make_run(conn, scratch_batch)
    res = attempt(scratch_batch, rid, payload(scratch_batch, {"A1": [1, 1, 1], "A2": [0, 0, 0]}))
    assert not isinstance(res, Exception), res
    assert count(conn, scratch_batch) == 2


def test_double_confirm_refused_and_nothing_added(conn, scratch_batch, client):
    rid, _ = make_run(conn, scratch_batch)
    body = payload(scratch_batch, {"A1": [1, 1, 1], "A2": [0, 0, 0]})
    assert not isinstance(attempt(scratch_batch, rid, body), Exception)
    second = attempt(scratch_batch, rid, body)
    assert isinstance(second, Exception) or "error" in json.dumps(second, default=str).lower() or "confirmed" in json.dumps(second, default=str).lower()
    assert count(conn, scratch_batch) == 2


def test_invalid_score_for_one_student_saves_nobody(conn, scratch_batch, client):
    rid, _ = make_run(conn, scratch_batch)
    top = scratch_batch["criteria"][0][1]
    attempt(scratch_batch, rid, payload(scratch_batch, {"A1": [1, 1, 1], "A2": [top + 1, 0, 0]}))
    assert count(conn, scratch_batch) == 0


def test_failure_midway_rolls_back_the_first_student(conn, scratch_batch, client):
    """Force the second insert to violate the unique constraint on submission_id. If the
    write is one transaction, A1's row must not survive."""
    from psycopg.types.json import Json
    rid, props = make_run(conn, scratch_batch)
    cur = conn.cursor()
    cur.execute("INSERT INTO reviewed_results (submission_id, proposal_id, run_id, scores, total, percentage, feedback, approved_at) "
                "VALUES (%s,%s,%s,%s,0,0,'',now())",
                (scratch_batch["submissions"]["A2"], props["A2"], rid, Json({})))
    before = count(conn, scratch_batch)
    assert before == 1
    attempt(scratch_batch, rid, payload(scratch_batch, {"A1": [1, 1, 1], "A2": [1, 1, 1]}))
    assert count(conn, scratch_batch) == before            # A1 was rolled back (or never written)


def test_unknown_run_refused(conn, scratch_batch, client):
    attempt(scratch_batch, str(uuid.uuid4()), payload(scratch_batch, {"A1": [1, 1, 1], "A2": [1, 1, 1]}))
    assert count(conn, scratch_batch) == 0
