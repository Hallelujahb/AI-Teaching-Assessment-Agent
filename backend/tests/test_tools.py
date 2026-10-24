"""The three tools and the seed data they rely on.
Needs TEST_DATABASE_URL (see conftest), seeded with `python -m app.seed`."""
import pytest

from app.scoring import detect_answer_status, rubric_maximum

pytestmark = pytest.mark.db


def test_three_tools_exist_with_the_planned_names(client):
    from app import tools
    for name in ("get_assessment_criteria", "get_submissions", "save_reviewed_results"):
        assert callable(getattr(tools, name)), name


def test_every_seeded_rubric_has_a_positive_maximum(conn):
    cur = conn.cursor()
    cur.execute("SELECT assessment_id, id, max_score FROM rubric_criteria")
    by = {}
    for aid, cid, m in cur.fetchall():
        by.setdefault(aid, []).append({"id": cid, "max_score": m})
    assert len(by) >= 2, "two assessments are needed so that 'which assessment?' is a real question"
    assert all(rubric_maximum(r) > 0 and len(r) >= 3 for r in by.values())


def test_js101_rubric_is_2_3_3_total_8(conn):
    cur = conn.cursor()
    cur.execute("SELECT c.max_score FROM rubric_criteria c JOIN assessments a ON a.id=c.assessment_id "
                "WHERE a.title ILIKE '%JS101%' OR a.title ILIKE '%javascript%' ORDER BY c.position")
    maxes = [r[0] for r in cur.fetchall()]
    if not maxes:
        pytest.skip("JS101 not found by title; adjust the query to the seed data")
    assert maxes == [2, 3, 3] and sum(maxes) == 8


def test_seeded_blank_answer_is_caught_by_code(conn):
    cur = conn.cursor()
    cur.execute("SELECT answer FROM submissions WHERE student_id='ST003' LIMIT 1")
    row = cur.fetchone()
    if row is None:
        pytest.skip("ST003 not seeded")
    assert detect_answer_status(row[0]) == "blank"
