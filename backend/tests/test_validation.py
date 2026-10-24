"""Section 6 rows: model output validation, retry rule, proposals, stub model."""
import pytest

from app.scoring import (
    FLAG_MANUAL, build_proposals, merge_retry_report, validate_model_output,
    validate_student_grade,
)
from app.stub_model import SCENARIOS, StubModel, StubProviderError, stub_output
from tests.conftest import ST001, ST002


# ---------------------------------------------------------------- one student
def test_valid_grade_normalised(rubric, make_grade):
    r = validate_student_grade(make_grade(evidence={1: "named container"}), rubric, ST001)
    assert r["valid"]
    g = r["grade"]
    assert g["scores"] == {"1": 2, "2": 3, "3": 3}
    assert g["total"] == 8 and g["percentage"] == 100.0
    assert g["evidence_check"]["1"] == "found" and g["evidence_check"]["2"] == "none"


def test_out_of_range_score_invalid_and_not_clamped(rubric, make_grade):
    r = validate_student_grade(make_grade(scores={1: 3, 2: 3, 3: 3}), rubric, ST001)
    assert not r["valid"] and r["grade"] is None
    assert any("outside" in x for x in r["reasons"])


@pytest.mark.parametrize("bad", [-1, 1.5, "2", None, True])
def test_non_integer_scores_invalid(rubric, make_grade, bad):
    assert not validate_student_grade(make_grade(scores={1: bad, 2: 3, 3: 3}), rubric, ST001)["valid"]


def test_missing_criterion_invalid(rubric, make_grade):
    r = validate_student_grade(make_grade(scores={1: 2, 2: 3}), rubric, ST001)
    assert not r["valid"] and "Missing criterion id 3" in r["reasons"]


def test_unknown_criterion_invalid(rubric, make_grade):
    r = validate_student_grade(make_grade(scores={1: 2, 2: 3, 3: 3, 99: 1}), rubric, ST001)
    assert not r["valid"] and any("Unknown criterion id 99" in x for x in r["reasons"])


def test_duplicate_criterion_invalid(rubric, make_grade):
    g = make_grade()
    g["criteria"].append(dict(g["criteria"][0]))
    r = validate_student_grade(g, rubric, ST001)
    assert not r["valid"] and "Duplicate criterion id 1" in r["reasons"]


def test_model_cannot_set_backend_statuses(rubric, make_grade):
    for status in ("blank", "needs_manual_grading", "nonsense"):
        assert not validate_student_grade(make_grade(status=status), rubric, ST001)["valid"]


def test_fake_quote_flagged_and_score_kept(rubric, make_grade):
    r = validate_student_grade(make_grade(evidence={2: "this was never written"}), rubric, ST001)
    assert r["valid"]
    g = r["grade"]
    assert g["scores"]["2"] == 3                       # score kept
    assert g["evidence_check"]["2"] == "not_found"
    assert any("Quote not found in answer" in f for f in g["flags"])


def test_empty_quote_not_flagged(rubric, make_grade):
    g = validate_student_grade(make_grade(), rubric, ST001)["grade"]
    assert not any("Quote not found" in f for f in g["flags"])


def test_model_flags_are_kept(rubric, make_grade):
    g = validate_student_grade(make_grade(attention_flags=["unsure about scope"]), rubric, ST001)["grade"]
    assert "unsure about scope" in g["flags"]


def test_unassessable_with_marks_flagged(rubric, make_grade):
    g = validate_student_grade(make_grade(status="unassessable"), rubric, ST001)["grade"]
    assert any("unassessable" in f for f in g["flags"])


def test_pydantic_like_objects_accepted(rubric, make_grade):
    class Obj:
        def __init__(self, d): self.d = d
        def model_dump(self): return self.d
    assert validate_student_grade(Obj(make_grade()), rubric, ST001)["valid"]


# ---------------------------------------------------------------- whole batch
def test_valid_batch_blank_is_not_expected(rubric, submissions, make_grade, make_output):
    out = make_output(make_grade("ST001"), make_grade("ST002", scores={1: 1, 2: 1, 3: 0}))
    rep = validate_model_output(out, rubric, submissions)
    assert rep["all_valid"] and rep["retry_ids"] == []
    assert rep["precomputed"] == {"ST003": "blank"}
    assert set(rep["students"]) == {"ST001", "ST002"}


def test_missing_student_only_that_student_invalid(rubric, submissions, make_grade, make_output):
    rep = validate_model_output(make_output(make_grade("ST001")), rubric, submissions)
    assert rep["retry_ids"] == ["ST002"]
    assert rep["students"]["ST001"]["valid"]
    assert "missing" in rep["students"]["ST002"]["reasons"][0].lower()


def test_unknown_student_dropped_and_noted(rubric, submissions, make_grade, make_output):
    out = make_output(make_grade("ST001"), make_grade("ST002"), make_grade("ST999"))
    rep = validate_model_output(out, rubric, submissions)
    assert rep["dropped"] == ["ST999"] and rep["all_valid"]
    assert any("ST999" in n for n in rep["notes"])


def test_duplicate_student_rejects_all_rows(rubric, submissions, make_grade, make_output):
    out = make_output(make_grade("ST001"), make_grade("ST001"), make_grade("ST002"))
    rep = validate_model_output(out, rubric, submissions)
    assert not rep["students"]["ST001"]["valid"]
    assert rep["students"]["ST002"]["valid"]
    assert rep["retry_ids"] == ["ST001"]


def test_blank_student_never_graded_by_model_result_dropped(rubric, submissions, make_grade, make_output):
    out = make_output(make_grade("ST001"), make_grade("ST002"), make_grade("ST003"))
    rep = validate_model_output(out, rubric, submissions)
    assert "ST003" in rep["dropped"] and "ST003" not in rep["students"]


def test_clarification_output_grades_nobody(rubric, submissions, make_output):
    rep = validate_model_output(make_output(status="needs_clarification", clarification="Which?"), rubric, submissions)
    assert rep["retry_ids"] == ["ST001", "ST002"]


def test_garbage_output_does_not_crash(rubric, submissions):
    for junk in (None, {}, "text", {"status": "graded", "results": "x"}, {"status": "graded", "results": [None, 3, {"student_id": ["a"]}]}):
        rep = validate_model_output(junk, rubric, submissions)
        assert rep["retry_ids"] == ["ST001", "ST002"]


# ---------------------------------------------------------------- retry and proposals
def test_retry_fixes_invalid_student_and_keeps_valid_one(rubric, submissions):
    model = StubModel(["out_of_range", "valid"])
    first = validate_model_output(model.respond(rubric, submissions), rubric, submissions)
    assert first["retry_ids"] == ["ST001"]
    retry = validate_model_output(model.respond(rubric, submissions), rubric, submissions)
    merged = merge_retry_report(first, retry)
    assert merged["all_valid"] and model.calls == 2


def test_still_invalid_after_retry_becomes_needs_manual_grading(rubric, submissions):
    model = StubModel("out_of_range")  # bad every time
    first = validate_model_output(model.respond(rubric, submissions), rubric, submissions)
    merged = merge_retry_report(first, validate_model_output(model.respond(rubric, submissions), rubric, submissions))
    props = {p["student_id"]: p for p in build_proposals(submissions, rubric, merged)}
    assert props["ST001"]["answer_status"] == "needs_manual_grading"
    assert props["ST001"]["scores"] == {"1": None, "2": None, "3": None}
    assert FLAG_MANUAL in props["ST001"]["flags"]
    assert props["ST002"]["answer_status"] == "complete"      # others unaffected
    assert model.calls == 2                                    # retried once, never more


def test_proposals_cover_every_submission_in_order(rubric, submissions):
    rep = validate_model_output(stub_output("valid", rubric, submissions), rubric, submissions)
    props = build_proposals(submissions, rubric, rep)
    assert [p["student_id"] for p in props] == ["ST001", "ST002", "ST003"]
    blank = props[2]
    assert blank["answer_status"] == "blank" and blank["scores"] == {"1": 0, "2": 0, "3": 0}
    assert blank["total"] == 0 and blank["flags"]


def test_code_unassessable_gets_zeros_and_flag(rubric):
    subs = [{"student_id": "S1", "answer": "ab"}, {"student_id": "S2", "answer": ST002}]
    rep = validate_model_output(stub_output("valid", rubric, subs), rubric, subs)
    p = build_proposals(subs, rubric, rep)[0]
    assert p["answer_status"] == "unassessable" and p["total"] == 0 and p["flags"]


# ---------------------------------------------------------------- stub scenarios
BAD = ["out_of_range", "negative_score", "non_integer", "duplicate_student", "missing_student",
       "duplicate_criterion", "missing_criterion", "unknown_criterion", "bad_status", "clarification"]


@pytest.mark.parametrize("scenario", BAD)
def test_bad_stub_scenarios_need_retry(scenario, rubric, submissions):
    rep = validate_model_output(stub_output(scenario, rubric, submissions), rubric, submissions)
    assert rep["retry_ids"], scenario


def test_valid_stub_passes_validation(rubric, submissions):
    assert validate_model_output(stub_output("valid", rubric, submissions), rubric, submissions)["all_valid"]


def test_unknown_and_blank_grading_stubs_are_dropped_not_fatal(rubric, submissions):
    for scenario in ("unknown_student", "grades_blank_student"):
        rep = validate_model_output(stub_output(scenario, rubric, submissions), rubric, submissions)
        assert rep["all_valid"] and rep["dropped"], scenario


def test_fake_quote_stub_keeps_score_with_flag(rubric, submissions):
    rep = validate_model_output(stub_output("fake_quote", rubric, submissions), rubric, submissions)
    g = rep["students"]["ST001"]["grade"]
    assert rep["all_valid"] and g["scores"]["1"] == 2
    assert any("Quote not found" in f for f in g["flags"])


def test_failure_stub_raises_quota_error(rubric, submissions):
    with pytest.raises(StubProviderError) as exc:
        stub_output("failure", rubric, submissions)
    assert exc.value.kind == "quota"


def test_all_scenarios_are_exercised():
    covered = set(BAD) | {"valid", "unknown_student", "grades_blank_student", "fake_quote", "failure", "injection_obeyed"}
    assert covered == set(SCENARIOS)


def test_unknown_scenario_name_rejected(rubric, submissions):
    with pytest.raises(ValueError):
        stub_output("nope", rubric, submissions)
