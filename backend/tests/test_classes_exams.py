"""Sign in by id, forgotten passwords, classes, assignments and student exams.
Needs TEST_DATABASE_URL (see conftest) after setup_db, seed and seed_users. Rows made here are removed afterwards."""
import uuid

import pytest

from app.auth import hash_password
from app.limits import limiter

pytestmark = pytest.mark.db

LECTURER = ("lecturer@qeleme.test", "Lecturer#123")
ST1 = ("st001@qeleme.test", "Student#123")
ST2 = ("st002@qeleme.test", "Student#123")
_tokens: dict = {}


@pytest.fixture(autouse=True)
def no_rate_limit():
    """Many sign-ins in one minute would hit the per-IP limit, which has nothing to do with these rules."""
    limiter.enabled = False
    yield
    limiter.enabled = True


def headers(client, who):
    if who[0] not in _tokens:
        r = client.post("/api/auth/login", json={"identifier": who[0], "password": who[1]})
        assert r.status_code == 200, r.text
        _tokens[who[0]] = r.json()["token"]
    return {"Authorization": "Bearer " + _tokens[who[0]]}


@pytest.fixture
def cleanup(conn):
    """Deletes classes and assignments made by a test (an assignment's batch goes with it)."""
    made = {"classes": [], "batches": [], "assessments": []}
    yield made
    cur = conn.cursor()
    for b in made["batches"]:
        cur.execute("DELETE FROM submission_batches WHERE id=%s", (b,))
    for c in made["classes"]:
        cur.execute("DELETE FROM classes WHERE id=%s", (c,))
    for a in made["assessments"]:
        cur.execute("DELETE FROM assessments WHERE id=%s", (a,))


@pytest.fixture
def assessment(client, cleanup):
    body = {"title": f"pytest {uuid.uuid4().hex[:6]}", "question": "What is a variable?", "reference_answer": "A named value.",
            "rubric": [{"name": "Criterion 1", "description": "d", "max_score": 2}, {"name": "Criterion 2", "description": "d", "max_score": 2}, {"name": "Criterion 3", "description": "d", "max_score": 2}]}
    r = client.post("/api/assessments", json=body, headers=headers(client, LECTURER))
    assert r.status_code == 201, r.text
    cleanup["assessments"].append(r.json()["id"])
    return r.json()["id"]


def make_class(client, cleanup, name=None, ids=("ST001", "ST002")):
    r = client.post("/api/classes", json={"name": name or f"Class {uuid.uuid4().hex[:5]}", "student_ids": list(ids)},
                    headers=headers(client, LECTURER))
    if r.status_code == 201:
        cleanup["classes"].append(r.json()["id"])
    return r


def assign(client, cleanup, aid, **body):
    r = client.post(f"/api/assessments/{aid}/assign", json=body, headers=headers(client, LECTURER))
    if r.status_code == 201:
        cleanup["batches"].append(r.json()["batch_id"])
    return r


# ---- sign in by id ----

@pytest.mark.parametrize("ident", ["st001@qeleme.test", "ST001", "st001", " ST001 "])
def test_student_signs_in_with_email_or_id(client, ident):
    r = client.post("/api/auth/login", json={"identifier": ident, "password": ST1[1], "as": "student"})
    assert r.status_code == 200 and r.json()["user"]["student_id"] == "ST001"


def test_lecturer_signs_in_with_staff_id(client, conn):
    staff_id = conn.execute("SELECT staff_id FROM users WHERE email=%s", (LECTURER[0],)).fetchone()[0]
    assert staff_id
    r = client.post("/api/auth/login", json={"identifier": staff_id.lower(), "password": LECTURER[1], "as": "lecturer"})
    assert r.status_code == 200 and r.json()["user"]["role"] == "lecturer"


def test_wrong_password_or_unknown_id_is_refused(client):
    assert client.post("/api/auth/login", json={"identifier": "ST001", "password": "nope-nope"}).status_code == 401
    assert client.post("/api/auth/login", json={"identifier": "ST999", "password": "nope-nope"}).status_code == 401


def test_old_email_field_still_works(client):
    assert client.post("/api/auth/login", json={"email": ST1[0], "password": ST1[1]}).status_code == 200


# ---- forgotten password ----

@pytest.fixture
def throwaway(conn):
    email = f"reset-{uuid.uuid4().hex[:6]}@qeleme.test"
    row = conn.execute("INSERT INTO users (email, name, role, student_id, password_hash, status) "
                       "VALUES (%s,'Reset Me','student',%s,%s,'active') RETURNING id, student_id",
                       (email, f"RS{uuid.uuid4().hex[:5].upper()}", hash_password("Oldpass#123"))).fetchone()
    yield {"id": row[0], "email": email, "student_id": row[1]}
    conn.execute("DELETE FROM users WHERE id=%s", (row[0],))


def request_reset(client, who):
    r = client.post("/api/auth/forgot", json={"identifier": who})
    assert r.status_code == 200
    reqs = client.get("/api/resets", headers=headers(client, LECTURER)).json()
    return [x for x in reqs if x["email"] == who or x["student_id"] == who]


def test_forgot_reveals_nothing_about_unknown_accounts(client):
    a = client.post("/api/auth/forgot", json={"identifier": "nobody@nowhere.test"})
    b = client.post("/api/auth/forgot", json={"identifier": ST1[0]})
    assert a.status_code == b.status_code == 200 and a.json() == b.json()


def test_reset_with_issued_code_changes_password_once(client, throwaway):
    (req,) = request_reset(client, throwaway["student_id"])
    assert req["issued"] is False
    code = client.post(f"/api/resets/{req['id']}/issue", headers=headers(client, LECTURER)).json()["code"]
    assert len(code) == 8 and code.isdigit()
    body = {"identifier": throwaway["student_id"], "code": code, "password": "Newpass#123"}
    assert client.post("/api/auth/reset", json=body).status_code == 200
    assert client.post("/api/auth/login", json={"identifier": throwaway["email"], "password": "Newpass#123"}).status_code == 200
    assert client.post("/api/auth/login", json={"identifier": throwaway["email"], "password": "Oldpass#123"}).status_code == 401
    assert client.post("/api/auth/reset", json=body).status_code == 401           # a code works once


def test_wrong_codes_lock_the_request(client, throwaway):
    (req,) = request_reset(client, throwaway["email"])
    code = client.post(f"/api/resets/{req['id']}/issue", headers=headers(client, LECTURER)).json()["code"]
    wrong = "00000000" if code != "00000000" else "11111111"
    for _ in range(5):
        r = client.post("/api/auth/reset", json={"identifier": throwaway["email"], "code": wrong, "password": "Newpass#123"})
        assert r.status_code == 401
    r = client.post("/api/auth/reset", json={"identifier": throwaway["email"], "code": code, "password": "Newpass#123"})
    assert r.status_code == 401


def test_reset_needs_a_real_new_password(client, throwaway):
    r = client.post("/api/auth/reset", json={"identifier": throwaway["email"], "code": "12345678", "password": "short"})
    assert r.status_code == 422


def test_student_cannot_see_or_issue_resets(client, throwaway):
    request_reset(client, throwaway["email"])
    assert client.get("/api/resets", headers=headers(client, ST1)).status_code == 403


# ---- classes ----

def test_class_with_name_and_students(client, cleanup):
    r = make_class(client, cleanup, name="12")
    assert r.status_code == 201
    mine = client.get("/api/classes", headers=headers(client, LECTURER)).json()
    row = next(c for c in mine if c["id"] == r.json()["id"])
    assert row["name"] == "12" and [s["student_id"] for s in row["students"]] == ["ST001", "ST002"]


def test_class_rules(client, cleanup):
    assert make_class(client, cleanup, name="  ").status_code == 422
    assert make_class(client, cleanup, ids=[]).status_code == 422
    assert make_class(client, cleanup, ids=["NOPE1"]).status_code == 422
    assert make_class(client, cleanup, ids=[f"ST{i}" for i in range(11)]).status_code == 422
    first = make_class(client, cleanup, name="Dup Class")
    assert first.status_code == 201
    assert make_class(client, cleanup, name="dup class").status_code == 409


def test_students_cannot_manage_classes(client):
    assert client.get("/api/classes", headers=headers(client, ST1)).status_code == 403
    assert client.post("/api/classes", json={"name": "x", "student_ids": ["ST001"]}, headers=headers(client, ST1)).status_code == 403


# ---- assignments and exams ----

def test_assigning_to_a_class_creates_a_batch_for_students(client, cleanup, assessment):
    cid = make_class(client, cleanup).json()["id"]
    r = assign(client, cleanup, assessment, class_id=cid, time_limit_minutes=20)
    assert r.status_code == 201 and r.json()["students"] == 2
    exams = client.get("/api/me/exams", headers=headers(client, ST1)).json()
    mine = next(e for e in exams if e["title"].startswith("pytest"))
    assert mine["status"] == "open" and mine["time_limit_minutes"] == 20


def test_assignment_rules(client, cleanup, assessment):
    assert assign(client, cleanup, assessment).status_code == 422                                  # nobody chosen
    assert assign(client, cleanup, assessment, student_ids=["ST001"], time_limit_minutes=0).status_code == 422
    assert assign(client, cleanup, assessment, student_ids=["ST001"], time_limit_minutes="ten").status_code == 422
    assert assign(client, cleanup, assessment, student_ids=["ST001"], time_limit_minutes=301).status_code == 422
    assert assign(client, cleanup, assessment, student_ids=["ST001"], time_limit_minutes=2.5).status_code == 422
    assert assign(client, cleanup, 999999, student_ids=["ST001"]).status_code == 404


def test_assigned_assessment_is_locked(client, cleanup, assessment):
    assert assign(client, cleanup, assessment, student_ids=["ST001"]).status_code == 201
    assert client.get(f"/api/assessments/{assessment}", headers=headers(client, LECTURER)).json()["locked"] is True
    body = {"title": "changed", "question": "q", "reference_answer": "a",
            "rubric": [{"name": "n1", "description": "d", "max_score": 1}, {"name": "n2", "description": "d", "max_score": 1}, {"name": "n3", "description": "d", "max_score": 1}]}
    assert client.put(f"/api/assessments/{assessment}", json=body, headers=headers(client, LECTURER)).status_code == 409


def test_student_only_sees_their_own_exams_and_never_the_rubric(client, cleanup, assessment):
    r = assign(client, cleanup, assessment, student_ids=["ST002"])
    aid = r.json()["id"]
    assert client.get(f"/api/me/exams/{aid}", headers=headers(client, ST1)).status_code == 404
    seen = client.get(f"/api/me/exams/{aid}", headers=headers(client, ST2))
    assert seen.status_code == 200 and seen.json()["question"] == "What is a variable?"
    assert "reference" not in seen.text.lower() and "rubric" not in seen.text.lower()


def test_submit_once_and_it_lands_in_the_batch(client, conn, cleanup, assessment):
    r = assign(client, cleanup, assessment, student_ids=["ST001"])
    aid, bid = r.json()["id"], r.json()["batch_id"]
    h = headers(client, ST1)
    assert client.post(f"/api/me/exams/{aid}/submit", json={"answer": "  "}, headers=h).status_code == 422
    assert client.post(f"/api/me/exams/{aid}/submit", json={"answer": "x" * 2001}, headers=h).status_code == 422
    assert client.post(f"/api/me/exams/{aid}/submit", json={"answer": "It stores a value."}, headers=h).status_code == 201
    assert client.post(f"/api/me/exams/{aid}/submit", json={"answer": "again"}, headers=h).status_code == 409
    rows = conn.execute("SELECT student_id, answer FROM submissions WHERE batch_id=%s", (bid,)).fetchall()
    assert rows == [("ST001", "It stores a value.")]
    listed = client.get(f"/api/assessments/{assessment}/batches", headers=headers(client, LECTURER)).json()
    assert [b["student_count"] for b in listed if b["id"] == bid] == [1]


def test_unassigned_student_cannot_submit(client, cleanup, assessment):
    aid = assign(client, cleanup, assessment, student_ids=["ST002"]).json()["id"]
    r = client.post(f"/api/me/exams/{aid}/submit", json={"answer": "hi there"}, headers=headers(client, ST1))
    assert r.status_code == 404


def test_timed_exam_hides_question_until_started(client, cleanup, assessment):
    aid = assign(client, cleanup, assessment, student_ids=["ST001"], time_limit_minutes=5).json()["id"]
    h = headers(client, ST1)
    assert client.get(f"/api/me/exams/{aid}", headers=h).json()["question"] is None
    assert client.post(f"/api/me/exams/{aid}/submit", json={"answer": "early"}, headers=h).status_code == 409
    started = client.post(f"/api/me/exams/{aid}/start", headers=h).json()
    assert started["question"] and started["status"] == "in_progress" and started["deadline"]
    again = client.post(f"/api/me/exams/{aid}/start", headers=h).json()
    assert again["started_at"] == started["started_at"]                                           # the clock does not restart


def test_late_answer_is_refused(client, conn, cleanup, assessment):
    aid = assign(client, cleanup, assessment, student_ids=["ST001"], time_limit_minutes=1).json()["id"]
    h = headers(client, ST1)
    client.post(f"/api/me/exams/{aid}/start", headers=h)
    conn.execute("UPDATE assignment_students SET started_at = now() - interval '5 minutes' WHERE assignment_id=%s", (aid,))
    assert client.get(f"/api/me/exams/{aid}", headers=h).json()["status"] == "expired"
    assert client.post(f"/api/me/exams/{aid}/submit", json={"answer": "late"}, headers=h).status_code == 409


def test_exam_closes_once_marking_starts(client, conn, cleanup, assessment):
    r = assign(client, cleanup, assessment, student_ids=["ST001"])
    aid, bid = r.json()["id"], r.json()["batch_id"]
    conn.execute("INSERT INTO grading_runs (batch_id, status, rubric_snapshot) VALUES (%s,'failed','[]'::jsonb)", (bid,))
    h = headers(client, ST1)
    assert client.post(f"/api/me/exams/{aid}/submit", json={"answer": "too late"}, headers=h).status_code == 409
    assert client.delete(f"/api/assignments/{aid}", headers=headers(client, LECTURER)).status_code == 409


def test_removing_an_assignment_unlocks_the_assessment(client, cleanup, assessment):
    aid = assign(client, cleanup, assessment, student_ids=["ST001"]).json()["id"]
    assert client.delete(f"/api/assignments/{aid}", headers=headers(client, LECTURER)).status_code == 200
    assert client.get(f"/api/assessments/{assessment}", headers=headers(client, LECTURER)).json()["locked"] is False


def test_assignment_batch_names_do_not_collide(client, cleanup, assessment):
    cid = make_class(client, cleanup, name="Same name").json()["id"]
    first = assign(client, cleanup, assessment, class_id=cid).json()["label"]
    second = assign(client, cleanup, assessment, class_id=cid).json()["label"]
    assert first == "Same name" and second == "Same name (2)"


def test_more_than_ten_students_refused(client, cleanup, assessment):
    assert assign(client, cleanup, assessment, student_ids=[f"S{i}" for i in range(11)]).status_code in (404, 422)
