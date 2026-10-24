"""Section 6 rows: score limits, totals, answer status, evidence."""
import pytest

from app.scoring import (
    EVIDENCE_FOUND, EVIDENCE_NONE, EVIDENCE_NOT_FOUND, ScoreError, calculate_percentage,
    calculate_total, check_score, detect_answer_status, evidence_found, rubric_maximum,
)
from tests.conftest import ST001, ST002


# ---- detect_answer_status
@pytest.mark.parametrize("answer", ["", "   ", "\n\t ", "...", "?!  -- ,", None])
def test_blank_variants(answer):
    assert detect_answer_status(answer) == "blank"


@pytest.mark.parametrize("answer", ["ab", "a b", "12", "x!", "42 ?"])
def test_fewer_than_three_letters_is_unassessable(answer):
    assert detect_answer_status(answer) == "unassessable"


@pytest.mark.parametrize("answer", ["abc", "I like football.", ST002, "let"])
def test_assessable_returns_none(answer):
    assert detect_answer_status(answer) is None


def test_non_latin_letters_count():
    assert detect_answer_status("\u1230\u120b\u121d") is None  # three Amharic letters


# ---- check_score
def test_score_above_max_is_rejected_not_clamped():
    with pytest.raises(ScoreError):
        check_score(3, 2)


@pytest.mark.parametrize("score,maximum", [(0, 2), (1, 2), (2, 2), (3, 3)])
def test_boundaries_accepted_and_returned_unchanged(score, maximum):
    assert check_score(score, maximum) == score


@pytest.mark.parametrize("bad", [-1, 1.5, 2.0, "2", None, True, [2]])
def test_non_integer_or_negative_rejected(bad):
    with pytest.raises(ScoreError):
        check_score(bad, 3)


# ---- totals and percentages
def test_rubric_maximum(rubric):
    assert rubric_maximum(rubric) == 8


def test_st001_total_and_percentage(rubric):
    total = calculate_total([2, 3, 3])
    assert total == 8
    assert calculate_percentage(total, rubric_maximum(rubric)) == 100.0


def test_st002_total_and_percentage(rubric):
    total = calculate_total({"1": 1, "2": 1, "3": 0})
    assert total == 2
    assert calculate_percentage(total, rubric_maximum(rubric)) == 25.0


@pytest.mark.parametrize("total,maximum,expected", [(1, 3, 33.3), (2, 3, 66.7), (3, 8, 37.5), (0, 8, 0.0), (1, 16, 6.3)])
def test_percentage_rounds_half_up_to_one_decimal(total, maximum, expected):
    assert calculate_percentage(total, maximum) == expected


def test_total_refuses_non_integers():
    with pytest.raises(ScoreError):
        calculate_total([2, 1.5])


@pytest.mark.parametrize("total,maximum", [(9, 8), (-1, 8), (1, 0)])
def test_percentage_refuses_impossible_inputs(total, maximum):
    with pytest.raises(ScoreError):
        calculate_percentage(total, maximum)


# ---- evidence
def test_exact_quote_found():
    assert evidence_found("const cannot be reassigned", ST002) == EVIDENCE_FOUND


def test_case_and_whitespace_normalised():
    assert evidence_found("  LET and   VAR\ncan be changed ", ST002) == EVIDENCE_FOUND


def test_wrapping_quote_marks_ignored():
    assert evidence_found('"Variables store values."', ST002) == EVIDENCE_FOUND


def test_missing_quote_not_found():
    assert evidence_found("var is function scoped", ST002) == EVIDENCE_NOT_FOUND


@pytest.mark.parametrize("empty", ["", "   ", None, '""'])
def test_empty_quote_is_no_evidence_not_failure(empty):
    assert evidence_found(empty, ST002) == EVIDENCE_NONE


def test_non_string_quote_is_not_found():
    assert evidence_found(42, ST002) == EVIDENCE_NOT_FOUND


def test_st001_quote_found():
    assert evidence_found("function scoped", ST001) == EVIDENCE_FOUND
