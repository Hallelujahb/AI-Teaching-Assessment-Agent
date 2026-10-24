"""Lecturer review rules (422 field errors), test case 2, and batch input rules."""
import pytest

from app.scoring import (
    MAX_ANSWER_CHARS, MAX_ANSWERS_PER_BATCH, build_proposals, validate_batch_input,
    validate_model_output, validate_review,
)
from app.stub_model import stub_output


@pytest.fixture
def proposals(rubric, submissions):
    rep = validate_model_output(stub_output("valid", rubric, submissions), rubric, submissions)
    return build_proposals(submissions, rubric, rep)


def row(sid, s1=1, s2=1, s3=0, feedback=""):
    return {"student_id": sid, "scores": [{"criterion_id": 1, "score": s1}, {"criterion_id": 2, "score": s2},
                                          {"criterion_id": 3, "score": s3}], "feedback": feedback}


def good(**over):
    req = {"run_id": "r1", "results": [row("ST001", 2, 3, 3), row("ST002"), row("ST003", 0, 0, 0)]}
    req.update(over)
    return req


def fields(res):
    return [e["field"] for e in res["errors"]]


def test_valid_review_backend_calculates_totals(rubric, proposals):
    res = validate_review(good(), rubric, proposals)
    assert res["valid"]
    by = {r["student_id"]: r for r in res["results"]}
    assert (by["ST001"]["total"], by["ST001"]["percentage"]) == (8, 100.0)
    assert (by["ST002"]["total"], by["ST002"]["percentage"]) == (2, 25.0)


def test_lecturer_correction_recalculates_total(rubric, proposals):  # test case 2
    req = good()
    req["results"][1] = row("ST002", 1, 2, 0)           # lecturer raises criterion 2 from 1 to 2
    res = validate_review(req, rubric, proposals)
    st2 = next(r for r in res["results"] if r["student_id"] == "ST002")
    assert (st2["total"], st2["percentage"]) == (3, 37.5)
    assert next(p for p in proposals if p["student_id"] == "ST001")["total"] == 8  # proposal untouched


def test_client_supplied_total_is_ignored(rubric, proposals):
    req = good()
    req["results"][1]["total"] = 8
    res = validate_review(req, rubric, proposals)
    assert next(r for r in res["results"] if r["student_id"] == "ST002")["total"] == 2


def test_scores_mapping_form_accepted(rubric, proposals):
    req = good()
    req["results"][1] = {"student_id": "ST002", "scores": {"1": 1, "2": 1, "3": 0}}
    assert validate_review(req, rubric, proposals)["valid"]


def test_missing_student(rubric, proposals):
    req = good(results=[row("ST001", 2, 3, 3), row("ST002")])
    res = validate_review(req, rubric, proposals)
    assert not res["valid"] and res["results"] == []
    assert any("ST003" in e["message"] for e in res["errors"])


def test_unknown_student(rubric, proposals):
    req = good()
    req["results"].append(row("ST999"))
    assert "results[3].student_id" in fields(validate_review(req, rubric, proposals))


def test_repeated_student(rubric, proposals):
    req = good()
    req["results"].append(row("ST001", 2, 3, 3))
    assert "results[3].student_id" in fields(validate_review(req, rubric, proposals))


def test_missing_criterion(rubric, proposals):
    req = good()
    req["results"][0]["scores"].pop()
    res = validate_review(req, rubric, proposals)
    assert "results[0].scores" in fields(res) and "criterion 3" in res["errors"][0]["message"].lower()


def test_unknown_criterion(rubric, proposals):
    req = good()
    req["results"][0]["scores"][0]["criterion_id"] = 42
    assert "results[0].scores[0].criterion_id" in fields(validate_review(req, rubric, proposals))


def test_repeated_criterion(rubric, proposals):
    req = good()
    req["results"][0]["scores"].append({"criterion_id": 1, "score": 2})
    assert "results[0].scores[3].criterion_id" in fields(validate_review(req, rubric, proposals))


@pytest.mark.parametrize("bad", [3, -1, 1.5, "2", None, True])
def test_bad_score_gives_field_error(rubric, proposals, bad):
    req = good()
    req["results"][0]["scores"][0]["score"] = bad     # criterion 1 has max 2
    res = validate_review(req, rubric, proposals)
    assert not res["valid"] and "results[0].scores[0].score" in fields(res)


def test_every_error_is_reported_not_just_the_first(rubric, proposals):
    req = good()
    req["results"][0]["scores"][0]["score"] = 9
    req["results"][1]["scores"][1]["score"] = -2
    assert len(validate_review(req, rubric, proposals)["errors"]) == 2


def test_needs_manual_grading_student_requires_scores(rubric, submissions):
    rep = validate_model_output(stub_output("out_of_range", rubric, submissions), rubric, submissions)
    props = build_proposals(submissions, rubric, rep)    # ST001 -> needs_manual_grading
    req = good()
    req["results"][0] = {"student_id": "ST001", "scores": [], "feedback": ""}
    res = validate_review(req, rubric, props)
    assert not res["valid"]
    assert any("needs a lecturer score" in e["message"] for e in res["errors"])
    assert validate_review(good(), rubric, props)["valid"]   # fine once the lecturer scores


def test_run_id_required(rubric, proposals):
    assert "run_id" in fields(validate_review(good(run_id=""), rubric, proposals))
    assert "run_id" in fields(validate_review({"results": good()["results"]}, rubric, proposals))


def test_results_must_be_a_list(rubric, proposals):
    assert fields(validate_review({"run_id": "r", "results": "x"}, rubric, proposals)) == ["results"]


def test_feedback_must_be_text(rubric, proposals):
    req = good()
    req["results"][0]["feedback"] = 5
    assert "results[0].feedback" in fields(validate_review(req, rubric, proposals))


def test_garbage_request_does_not_crash(rubric, proposals):
    for junk in (None, [], "x", {"run_id": "r", "results": [None, 3, {"student_id": 7}]}):
        assert not validate_review(junk, rubric, proposals)["valid"]


# ---------------------------------------------------------------- batch input (caps)
def rows(n):
    return [{"student_id": f"S{i}", "answer": "an answer"} for i in range(n)]


def test_good_batch_ok():
    assert validate_batch_input(rows(3))["status_code"] == 200


def test_blank_answer_is_allowed():
    assert validate_batch_input([{"student_id": "S1", "answer": ""}])["status_code"] == 200


def test_duplicate_ids_give_409_listing_ids():
    res = validate_batch_input(rows(2) + [{"student_id": "S0", "answer": "x"}, {"student_id": " S1 ", "answer": "y"}])
    assert res["status_code"] == 409 and res["duplicate_ids"] == ["S0", "S1"]


@pytest.mark.parametrize("sid", ["", "   ", None, 5])
def test_empty_student_id_422(sid):
    res = validate_batch_input([{"student_id": sid, "answer": "x"}])
    assert res["status_code"] == 422 and res["errors"][0]["field"] == "submissions[0].student_id"


def test_answer_length_boundary():
    assert validate_batch_input([{"student_id": "S", "answer": "a" * MAX_ANSWER_CHARS}])["status_code"] == 200
    res = validate_batch_input([{"student_id": "S", "answer": "a" * (MAX_ANSWER_CHARS + 1)}])
    assert res["status_code"] == 422 and res["errors"][0]["field"] == "submissions[0].answer"


def test_batch_size_boundary():
    assert validate_batch_input(rows(MAX_ANSWERS_PER_BATCH))["status_code"] == 200
    assert validate_batch_input(rows(MAX_ANSWERS_PER_BATCH + 1))["status_code"] == 422


@pytest.mark.parametrize("junk", [None, [], "x", {}])
def test_empty_or_wrong_type_422(junk):
    assert validate_batch_input(junk)["status_code"] == 422


def test_field_errors_win_over_duplicates():
    res = validate_batch_input([{"student_id": "S", "answer": "x"}, {"student_id": "S", "answer": "x" * 2001}])
    assert res["status_code"] == 422 and res["duplicate_ids"] == ["S"]
