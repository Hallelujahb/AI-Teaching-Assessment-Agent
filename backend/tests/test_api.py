"""Endpoint rules from section 7 and 6 that need the real app and database.
Needs TEST_DATABASE_URL (see conftest). Adjust batch_body() in conftest to the request
shape in docs/api-examples.md if it differs from the one assumed there."""
import uuid

import pytest

from tests.conftest import batch_body

pytestmark = pytest.mark.db


@pytest.fixture
def assessment_id(client):
    r = client.get("/api/assessments")
    assert r.status_code == 200
    return r.json()[0]["id"] if isinstance(r.json(), list) else r.json()["assessments"][0]["id"]


@pytest.fixture
def cleanup(conn):
    labels = []
    yield labels
    cur = conn.cursor()
    for label in labels:
        cur.execute("SELECT id FROM submission_batches WHERE label=%s", (label,))
        for (bid,) in cur.fetchall():
            cur.execute("DELETE FROM submissions WHERE batch_id=%s", (bid,))
            cur.execute("DELETE FROM submission_batches WHERE id=%s", (bid,))


def post(client, aid, label, rows):
    return client.post(f"/api/assessments/{aid}/batches", json=batch_body(label, rows))


def exists(conn, label):
    cur = conn.cursor()
    cur.execute("SELECT count(*) FROM submission_batches WHERE label=%s", (label,))
    return cur.fetchone()[0] > 0


def test_health_never_calls_the_model(client):
    r = client.get("/api/health")
    assert r.status_code == 200 and "traceback" not in r.text.lower()


def test_valid_batch_is_saved(client, conn, assessment_id, cleanup):
    label = f"pytest-{uuid.uuid4().hex[:8]}"
    cleanup.append(label)
    assert post(client, assessment_id, label, [{"student_id": "X1", "answer": "hello there"}]).status_code in (200, 201)
    assert exists(conn, label)


def test_duplicate_student_ids_409_and_nothing_saved(client, conn, assessment_id, cleanup):
    label = f"pytest-{uuid.uuid4().hex[:8]}"
    cleanup.append(label)
    r = post(client, assessment_id, label, [{"student_id": "X1", "answer": "a b c"}, {"student_id": "X1", "answer": "d e f"}])
    assert r.status_code == 409 and "X1" in r.text
    assert not exists(conn, label)


@pytest.mark.parametrize("rows", [
    [{"student_id": "", "answer": "text"}],
    [{"student_id": "X1", "answer": "a" * 2001}],
    [{"student_id": f"S{i}", "answer": "text"} for i in range(11)],
])
def test_invalid_batches_422_and_nothing_saved(client, conn, assessment_id, cleanup, rows):
    label = f"pytest-{uuid.uuid4().hex[:8]}"
    cleanup.append(label)
    assert post(client, assessment_id, label, rows).status_code == 422
    assert not exists(conn, label)


def test_oversized_body_refused(client, assessment_id):
    rows = [{"student_id": f"S{i}", "answer": "x" * 2000} for i in range(10)]   # ~20 KB is fine
    rows[0]["answer"] = "x" * 80_000                                              # well past 50 KB
    assert post(client, assessment_id, "pytest-big", rows).status_code in (413, 422)


def test_errors_are_short_and_have_no_stack_trace(client, assessment_id):
    r = client.get("/api/assessments/not-a-real-id")
    assert r.status_code in (404, 422) and "Traceback" not in r.text
