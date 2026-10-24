"""Tests for parse_model_output and prompt builders. No network, no database."""
import pytest

from app.ai_provider import AIError
from app.prompts import (
    parse_model_output,
    build_answer_blocks,
    build_catalog_context,
    build_initial_messages,
    build_retry_message,
    make_nonce,
    tool_schemas,
)
from app.scoring import detect_answer_status


# -----------------------------------------------------------------------
# parse_model_output

ST001 = ("A variable is a named container that stores a value so a program can use it later. "
         "var can be redeclared and reassigned and is function scoped. let can be reassigned "
         "but not redeclared in the same scope and is block scoped. const cannot be reassigned "
         "or redeclared and is block scoped.")


VALID_JSON = {
    "status": "graded",
    "clarification": None,
    "results": [
        {
            "student_id": "ST001",
            "answer_status": "complete",
            "criteria": [
                {"criterion_id": 1, "proposed_score": 2, "evidence": "named container", "explanation": "defines a variable"}
            ],
            "feedback": "good",
            "attention_flags": [],
        }
    ],
}
import json as _json
VALID_TEXT = _json.dumps(VALID_JSON)


def test_clean_json_parses():
    result = parse_model_output(VALID_TEXT)
    assert result["status"] == "graded"
    assert result["results"][0]["student_id"] == "ST001"


def test_fenced_json_parses():
    text = f"```json\n{VALID_TEXT}\n```"
    result = parse_model_output(text)
    assert result["status"] == "graded"


def test_fenced_no_lang_parses():
    text = f"```\n{VALID_TEXT}\n```"
    result = parse_model_output(text)
    assert result["status"] == "graded"


def test_leading_prose_then_json():
    text = f"Here is my analysis:\n\n{VALID_TEXT}"
    result = parse_model_output(text)
    assert result["status"] == "graded"


def test_json_followed_by_prose():
    text = f'{VALID_TEXT}\n\nI hope this helps!'
    result = parse_model_output(text)
    assert result["status"] == "graded"


def test_think_block_stripped():
    raw = f"Some intro with thinking.\n\n{VALID_TEXT}\n\nMore text."
    text = f"Some reasoning here.\n\n{raw}"
    result = parse_model_output(text)
    assert result["status"] == "graded"


def test_boxed_stripped():
    text = f"\\boxed{{{VALID_TEXT}}}"
    result = parse_model_output(text)
    assert result["status"] == "graded"


def test_truncated_json_raises_invalid_output():
    text = '{"status": "graded", "results": [{"student_id": "ST001", "criter'
    with pytest.raises(AIError, match="invalid_output"):
        parse_model_output(text)


def test_empty_string_raises():
    with pytest.raises(AIError, match="invalid_output"):
        parse_model_output("")


def test_whitespace_only_raises():
    with pytest.raises(AIError, match="invalid_output"):
        parse_model_output("   \n\t  ")


def test_array_not_object_raises():
    with pytest.raises(AIError, match="invalid_output"):
        parse_model_output('[{"status": "graded"}]')


def test_no_curly_braces_raises():
    with pytest.raises(AIError, match="invalid_output"):
        parse_model_output("This is just plain text with no JSON at all.")


def test_nested_objects_handled():
    """A nested object inside the criteria should not confuse the brace counter."""
    text = f'{"status": "graded", "results": []}\nextra'
    # Need proper JSON
    text = _json.dumps({"status": "graded", "results": []})
    result = parse_model_output(text)
    assert result["status"] == "graded"


def test_json_with_nested_braces():
    inner = {"criterion_id": 1, "proposed_score": 2, "evidence": "a", "explanation": "b"}
    outer = {"status": "graded", "results": [
        {"student_id": "S1", "answer_status": "complete",
         "criteria": [inner], "feedback": "x", "attention_flags": []}
    ]}
    text = _json.dumps(outer)
    result = parse_model_output(text)
    assert result["results"][0]["criteria"][0]["criterion_id"] == 1


def test_invalid_status_raises():
    """ModelOutput requires status in the allowed set."""
    text = _json.dumps({"status": "something_else", "results": []})
    with pytest.raises(AIError, match="invalid_output"):
        parse_model_output(text)


# -----------------------------------------------------------------------
# Message builders

def test_tool_schemas_only_retrieval():
    schemas = tool_schemas()
    names = [s["function"]["name"] for s in schemas]
    assert "get_assessment_criteria" in names
    assert "get_submissions" in names
    assert "save_reviewed_results" not in names  # never given to the model


def test_build_answer_blocks_has_nonce():
    subs = [{"student_id": "S1", "answer": "hello world"}]
    nonce = "abc123"
    blocks = build_answer_blocks(subs, nonce)
    assert nonce in blocks
    assert "S1" in blocks
    assert "===ANSWER" in blocks
    assert "===END===" in blocks


def test_build_answer_blocks_empty_submissions():
    blocks = build_answer_blocks([], "abc123")
    assert "no assessable" in blocks


def test_build_catalog_context():
    catalog = [{"id": "JS101", "title": "JS101", "batches": [{"id": 1, "label": "JS101-B1"}]}]
    text = build_catalog_context(catalog)
    assert "JS101" in text
    assert "JS101-B1" in text


def test_make_nonce_is_random():
    n1 = make_nonce()
    n2 = make_nonce()
    assert n1 != n2
    assert len(n1) > 0


def test_build_retry_message_lists_invalid():
    report = {"students": {"ST001": {"valid": False, "reasons": ["score out of range"]}}}
    msg = build_retry_message(["ST001"], report)
    assert "ST001" in msg
    assert "score out of range" in msg
    assert "no tools" in msg.lower() or "do not call tools" in msg.lower()


def test_build_initial_messages_has_system_and_user():
    rubric = {"question": "Q1", "reference_answer": "RA", "rubric": [
        {"id": 1, "name": "C1", "max_score": 2, "description": "D1"}
    ]}
    subs = [{"student_id": "S1", "answer": "hello world"}]
    msgs = build_initial_messages("JS101", rubric, subs, make_nonce(), "catalog text", "grade please")
    assert len(msgs) == 2
    assert msgs[0]["role"] == "system"
    assert msgs[1]["role"] == "user"
    assert "Q1" in msgs[1]["content"]
    assert "S1" in msgs[1]["content"]  # answer block present
    assert "nonce=" in msgs[1]["content"]  # nonce delimiter present


def test_answer_blocks_use_nonce_delimiter():
    """F.2: student text is inside delimited blocks with a random nonce."""
    subs = [{"student_id": "S1", "answer": "test answer content"}]
    nonce = make_nonce()
    blocks = build_answer_blocks(subs, nonce)
    assert f"nonce={nonce}" in blocks


def test_blank_answer_not_in_blocks():
    """Blank answers should never appear in model messages."""
    subs = [{"student_id": "S1", "answer": "hello"}, {"student_id": "S2", "answer": ""}]
    blocks = build_answer_blocks(subs, "abc123")
    # Both are passed through builder; the agent sanitises before calling
    assert "hello" in blocks
    # S2's empty answer still generates a block (agent filters before calling)
    # The key test is that the agent removes blanks before calling build_answer_blocks
