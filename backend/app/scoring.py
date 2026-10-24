"""Validation and scoring rules (Person 4).

Rule for the whole project: the AI proposes, the code validates, the lecturer decides.
Nothing here touches the network or the database, so every rule is unit-testable.

Inputs may be plain dicts or Pydantic / dataclass objects. Everything is converted with
``to_plain`` at the entry point, so callers do not need to care which they hold.

Shapes used in this module
--------------------------
rubric         list of criteria: {"id": int, "max_score": int, ...}
submissions    list of {"student_id": str, "answer": str}
model output   ModelOutput from the build plan (status, clarification, results)
review request {"run_id": str, "results": [{"student_id": str,
                 "scores": [{"criterion_id": int, "score": int}], "feedback": str}]}
               ("scores" may also be a {criterion_id: score} mapping)
proposal       {"student_id", "answer_status", "scores", "evidence", "explanations",
                "flags", "feedback", ...}  (see ``build_proposals``)

Scores are whole numbers and are NEVER clamped. A bad score makes that student invalid.
"""
from __future__ import annotations

import dataclasses
import re
import unicodedata
from collections.abc import Mapping
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

# ---------------------------------------------------------------- constants

MODEL_STATUSES = ("complete", "incomplete", "unassessable")
BACKEND_STATUSES = ("blank", "needs_manual_grading")  # the model can never set these
ALL_STATUSES = MODEL_STATUSES + BACKEND_STATUSES

MAX_ANSWER_CHARS = 2000
MAX_ANSWERS_PER_BATCH = 10
MIN_LETTERS = 3

EVIDENCE_FOUND = "found"
EVIDENCE_NONE = "none"            # empty quote: no evidence, not a failure
EVIDENCE_NOT_FOUND = "not_found"  # quote does not appear in the answer

FLAG_BLANK = "Blank answer: no model call, zeros proposed"
FLAG_TOO_SHORT = "Answer has fewer than 3 letters: not assessable, no model call"
FLAG_MANUAL = "Automatic grading failed validation: lecturer must enter every score"
FLAG_INJECTION = "Answer contains instruction-like text aimed at the grader: check scores"


class ScoreError(ValueError):
    """Raised by check_score and the total/percentage helpers."""


# ---------------------------------------------------------------- helpers


def to_plain(obj: Any) -> Any:
    """Convert Pydantic models, dataclasses and mappings to plain dicts (shallow-safe)."""
    if obj is None or isinstance(obj, (str, int, float, bool, list, tuple)):
        return obj
    if hasattr(obj, "model_dump"):
        return obj.model_dump()
    if dataclasses.is_dataclass(obj) and not isinstance(obj, type):
        return dataclasses.asdict(obj)
    if isinstance(obj, Mapping):
        return dict(obj)
    if hasattr(obj, "__dict__"):
        return {k: v for k, v in vars(obj).items() if not k.startswith("_")}
    return obj


def _plain_list(seq: Any) -> list:
    if seq is None or isinstance(seq, (str, bytes)):
        return []
    try:
        return [to_plain(x) for x in seq]
    except TypeError:
        return []


def _is_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _rubric_map(rubric: Any) -> dict[int, int]:
    """criterion id -> max score."""
    out: dict[int, int] = {}
    for row in _plain_list(rubric):
        out[row["id"]] = row["max_score"]
    return out


def rubric_maximum(rubric: Any) -> int:
    """Maximum total, summed from the rubric rows."""
    return sum(_rubric_map(rubric).values())


def _dedupe(items: list[str]) -> list[str]:
    seen: set[str] = set()
    out = []
    for item in items:
        if item not in seen:
            seen.add(item)
            out.append(item)
    return out


# ---------------------------------------------------------------- answer status


def detect_answer_status(answer: Any) -> str | None:
    """'blank' for empty, whitespace-only or punctuation-only; 'unassessable' for fewer
    than 3 letters; otherwise None (send to the model)."""
    if answer is None or not isinstance(answer, str):
        return "blank"
    if not any(ch.isalnum() for ch in answer):
        return "blank"
    if sum(ch.isalpha() for ch in answer) < MIN_LETTERS:
        return "unassessable"
    return None


# ---------------------------------------------------------------- scores


def check_score(score: Any, maximum: int) -> int:
    """Return the score if it is an integer in 0..maximum, else raise ScoreError.
    Never clamps. Booleans, floats (even 2.0) and strings are rejected."""
    if not _is_int(score):
        raise ScoreError(f"Score must be a whole number, got {score!r}")
    if not _is_int(maximum) or maximum < 0:
        raise ScoreError(f"Invalid criterion maximum {maximum!r}")
    if score < 0 or score > maximum:
        raise ScoreError(f"Score {score} is outside the allowed range 0 to {maximum}")
    return score


def calculate_total(scores: Any) -> int:
    """Integer sum of criterion scores. Accepts a list or a {criterion_id: score} dict."""
    values = list(scores.values()) if isinstance(scores, Mapping) else list(scores)
    for v in values:
        if not _is_int(v):
            raise ScoreError(f"Cannot total a non-integer score: {v!r}")
    return sum(values)


def calculate_percentage(total: int, maximum: int) -> float:
    """total / maximum * 100, rounded half-up to one decimal place."""
    if not _is_int(total) or not _is_int(maximum):
        raise ScoreError("Total and maximum must be integers")
    if maximum <= 0:
        raise ScoreError("Rubric maximum must be above zero")
    if total < 0 or total > maximum:
        raise ScoreError(f"Total {total} is outside 0 to {maximum}")
    pct = (Decimal(total) * 100 / Decimal(maximum)).quantize(Decimal("0.1"), ROUND_HALF_UP)
    return float(pct)


# ---------------------------------------------------------------- evidence


_QUOTES = {"\u2018": "'", "\u2019": "'", "\u201c": '"', "\u201d": '"'}


def normalise_text(text: str) -> str:
    text = unicodedata.normalize("NFKC", text)
    for fancy, plain in _QUOTES.items():
        text = text.replace(fancy, plain)
    return " ".join(text.casefold().split())


def evidence_found(evidence: Any, answer: Any) -> str:
    """EVIDENCE_FOUND, EVIDENCE_NONE (empty quote) or EVIDENCE_NOT_FOUND.

    Whitespace and case are normalised; quote marks wrapped around the quote are ignored.
    A quote that is not a string is treated as not found."""
    if evidence is None:
        return EVIDENCE_NONE
    if not isinstance(evidence, str):
        return EVIDENCE_NOT_FOUND
    quote = normalise_text(evidence).strip("\"' ")
    if not quote:
        return EVIDENCE_NONE
    haystack = normalise_text(answer) if isinstance(answer, str) else ""
    return EVIDENCE_FOUND if quote in haystack else EVIDENCE_NOT_FOUND


# ---------------------------------------------------------------- injection defence in depth
# The prompt tells the model to ignore instructions inside answers. If that fails, code
# still catches the obvious cases. This is a heuristic backstop, not a guarantee.

_INJECTION_PATTERNS = [
    re.compile(r"\b(ignore|disregard|forget|override)\b.{0,30}\b(rubric|instructions?|rules?|criteria|prompt|marking)\b", re.I | re.S),
    re.compile(r"\b(give|award|grant|assign|mark|score)\b.{0,50}\b(full|maximum|max|top|perfect|100)\s*(marks?|score|points?|grade|%)", re.I | re.S),
    re.compile(r"\b(full|perfect|maximum)\s+marks\b", re.I),
    re.compile(r"\b(system|developer)\s+prompt\b", re.I),
    re.compile(r"\bnew\s+instructions?\b", re.I),
    re.compile(r"\byou\s+are\s+now\b", re.I),
]


def detect_injection(text: Any) -> bool:
    if not isinstance(text, str):
        return False
    return any(p.search(text) for p in _INJECTION_PATTERNS)


# ---------------------------------------------------------------- one student


def _invalid(reasons: list[str]) -> dict:
    return {"valid": False, "reasons": reasons, "grade": None}


def validate_student_grade(grade: Any, rubric: Any, answer: Any) -> dict:
    """Validate one student's model grade against the rubric and their answer.

    Returns {"valid": bool, "reasons": [...], "grade": normalised dict or None}.
    The normalised grade has: student_id, answer_status, scores, evidence, explanations,
    evidence_check ({criterion_id(str): found|none|not_found}), flags, feedback, total,
    percentage. A missing quote never invalidates a score: it adds a flag.
    """
    g = to_plain(grade)
    if not isinstance(g, dict):
        return _invalid(["Grade is not an object"])
    crit = _rubric_map(rubric)
    reasons: list[str] = []

    status = g.get("answer_status")
    if status not in MODEL_STATUSES:
        reasons.append(f"Invalid answer_status {status!r} (the model may only set {', '.join(MODEL_STATUSES)})")

    rows = g.get("criteria")
    if not isinstance(rows, list):
        return _invalid(reasons + ["criteria is missing or not a list"])

    seen: dict[int, dict] = {}
    duplicates: list[Any] = []
    for raw in rows:
        row = to_plain(raw)
        if not isinstance(row, dict):
            reasons.append("A criterion entry is not an object")
            continue
        cid = row.get("criterion_id")
        if not _is_int(cid) or cid not in crit:
            reasons.append(f"Unknown criterion id {cid!r}")
        elif cid in seen:
            if cid not in duplicates:
                duplicates.append(cid)
        else:
            seen[cid] = row
    for cid in duplicates:
        reasons.append(f"Duplicate criterion id {cid}")
    for cid in crit:
        if cid not in seen:
            reasons.append(f"Missing criterion id {cid}")

    for cid, row in seen.items():
        if cid in duplicates:
            continue
        try:
            check_score(row.get("proposed_score"), crit[cid])
        except ScoreError as exc:
            reasons.append(f"Criterion {cid}: {exc}")

    if reasons:
        return _invalid(reasons)

    flags: list[str] = []
    model_flags = g.get("attention_flags")
    if isinstance(model_flags, list):
        flags.extend(f for f in model_flags if isinstance(f, str) and f.strip())

    scores, evidence, explanations, checks = {}, {}, {}, {}
    for cid in crit:  # rubric order
        row = seen[cid]
        key = str(cid)
        scores[key] = row["proposed_score"]
        quote = row.get("evidence")
        evidence[key] = quote if isinstance(quote, str) else ""
        explanation = row.get("explanation")
        explanations[key] = explanation if isinstance(explanation, str) else ""
        checks[key] = evidence_found(quote, answer)
        if checks[key] == EVIDENCE_NOT_FOUND:
            flags.append(f"Quote not found in answer (criterion {cid})")

    total = calculate_total(scores)
    maximum = rubric_maximum(rubric)
    if status == "unassessable" and total > 0:
        flags.append("Marked unassessable but scores are above zero: check")
    if detect_injection(answer):
        flags.append(FLAG_INJECTION)
        if maximum > 0 and total == maximum:
            return _invalid(["Full marks given to an answer containing instructions to the grader"])

    feedback = g.get("feedback")
    return {
        "valid": True,
        "reasons": [],
        "grade": {
            "student_id": g.get("student_id"),
            "answer_status": status,
            "scores": scores,
            "evidence": evidence,
            "explanations": explanations,
            "evidence_check": checks,
            "flags": _dedupe(flags),
            "feedback": feedback if isinstance(feedback, str) else "",
            "total": total,
            "percentage": calculate_percentage(total, maximum),
        },
    }


# ---------------------------------------------------------------- whole batch


def validate_model_output(output: Any, rubric: Any, submissions: Any) -> dict:
    """Validate the model's output for a batch.

    Only students the code sent to the model (not blank, not unassessable by code) are
    expected. Returns:
      students     {student_id: {"valid", "reasons", "grade"}} for expected students
      precomputed  {student_id: "blank" | "unassessable"} decided in code
      retry_ids    expected students whose result is missing or invalid
      dropped      ids in the output that were not expected (unknown or code-handled)
      notes        run-log lines (drops, rejections)
      all_valid    True when retry_ids is empty
    """
    out = to_plain(output)
    out = out if isinstance(out, dict) else {}
    subs = _plain_list(submissions)

    answers: dict[str, str] = {}
    precomputed: dict[str, str] = {}
    expected: list[str] = []
    for s in subs:
        sid = s["student_id"]
        answers[sid] = s.get("answer") or ""
        code_status = detect_answer_status(answers[sid])
        if code_status:
            precomputed[sid] = code_status
        else:
            expected.append(sid)

    students: dict[str, dict] = {}
    notes: list[str] = []
    dropped: list[Any] = []

    if out.get("status") != "graded":
        for sid in expected:
            students[sid] = _invalid(["Model returned no grades"])
    else:
        by_id: dict[Any, list[dict]] = {}
        for raw in _plain_list(out.get("results")):
            row = raw if isinstance(raw, dict) else {}
            sid_raw = row.get("student_id")
            key = sid_raw if isinstance(sid_raw, str) else f"<invalid student_id {sid_raw!r}>"
            by_id.setdefault(key, []).append(row)

        for sid, rows in by_id.items():
            if sid not in answers:
                dropped.append(sid)
                notes.append(f"Dropped model result for unknown student id {sid!r}")
            elif sid in precomputed:
                dropped.append(sid)
                notes.append(f"Dropped model result for {sid}: answer was handled in code ({precomputed[sid]})")

        for sid in expected:
            rows = by_id.get(sid, [])
            if not rows:
                students[sid] = _invalid(["Student missing from model output"])
                notes.append(f"{sid}: missing from model output")
            elif len(rows) > 1:
                students[sid] = _invalid([f"Duplicate student id in model output ({len(rows)} rows), all rows rejected"])
                notes.append(f"{sid}: duplicate rows in model output, all rejected")
            else:
                students[sid] = validate_student_grade(rows[0], rubric, answers[sid])
                if not students[sid]["valid"]:
                    notes.append(f"{sid}: invalid ({'; '.join(students[sid]['reasons'])})")

    retry_ids = [sid for sid in expected if not students[sid]["valid"]]
    return {
        "students": students,
        "precomputed": precomputed,
        "retry_ids": retry_ids,
        "dropped": dropped,
        "notes": notes,
        "all_valid": not retry_ids,
    }


def merge_retry_report(first: dict, retry: dict) -> dict:
    """Combine the first report with the report from the single allowed retry.

    A student valid in the first report keeps that result. A student invalid in the first
    report takes the retry result only if that is valid. Whoever is still invalid is in
    ``retry_ids`` and becomes needs_manual_grading in ``build_proposals``."""
    students = dict(first["students"])
    for sid in first["retry_ids"]:
        candidate = retry["students"].get(sid)
        if candidate and candidate["valid"]:
            students[sid] = candidate
        elif candidate:
            students[sid] = candidate  # latest reasons
    still = [sid for sid in first["students"] if not students[sid]["valid"]]
    return {
        **first,
        "students": students,
        "retry_ids": still,
        "all_valid": not still,
        "notes": first["notes"] + ["--- retry ---"] + retry["notes"],
    }


def build_proposals(submissions: Any, rubric: Any, report: dict) -> list[dict]:
    """One proposal per submission, in batch order, for P2's ``save_proposals``.

    Keys: student_id, answer_status, scores {cid: int|None}, evidence, explanations,
    flags, feedback, total, percentage, plus evidence_check (optional, recomputable).
    * blank / code-unassessable: zeros proposed, flagged, never saw the model
    * valid model grade: as validated
    * invalid after retry: needs_manual_grading, no scores (None), flagged
    """
    crit = _rubric_map(rubric)
    keys = [str(c) for c in crit]
    proposals = []
    for s in _plain_list(submissions):
        sid = s["student_id"]
        base = {"student_id": sid, "evidence": {}, "explanations": {}, "feedback": "", "evidence_check": {}}
        if sid in report["precomputed"]:
            status = report["precomputed"][sid]
            proposals.append({
                **base, "answer_status": status,
                "scores": {k: 0 for k in keys},
                "flags": [FLAG_BLANK if status == "blank" else FLAG_TOO_SHORT],
                "total": 0, "percentage": 0.0,
            })
            continue
        result = report["students"].get(sid)
        if result and result["valid"]:
            grade = result["grade"]
            proposals.append({**grade, "student_id": sid})
        else:
            proposals.append({
                **base, "answer_status": "needs_manual_grading",
                "scores": {k: None for k in keys},
                "flags": [FLAG_MANUAL],
                "total": None, "percentage": None,
            })
    return proposals


# ---------------------------------------------------------------- lecturer review


def _err(field: str, message: str) -> dict:
    return {"field": field, "message": message}


def _scores_as_rows(scores: Any) -> list[dict]:
    if isinstance(scores, Mapping):
        rows = []
        for k, v in scores.items():
            try:
                cid: Any = int(k)
            except (TypeError, ValueError):
                cid = k
            rows.append({"criterion_id": cid, "score": v})
        return rows
    return [r if isinstance(r, dict) else to_plain(r) for r in _plain_list(scores)]


def validate_review(request: Any, rubric: Any, proposals: Any) -> dict:
    """Validate the lecturer's confirmation request.

    ``proposals`` supplies the batch's students and which need manual grading.
    Returns {"valid": bool, "errors": [{"field", "message"}], "results": [...]}.
    ``results`` (only when valid) holds student_id, scores {cid(str): int}, feedback,
    total, percentage, all calculated here. Nothing is clamped or defaulted.
    """
    req = to_plain(request)
    req = req if isinstance(req, dict) else {}
    crit = _rubric_map(rubric)
    maximum = rubric_maximum(rubric)
    props = {p["student_id"]: p for p in _plain_list(proposals)}
    errors: list[dict] = []

    run_id = req.get("run_id")
    if not isinstance(run_id, str) or not run_id.strip():
        errors.append(_err("run_id", "run_id is required"))

    rows = req.get("results")
    if not isinstance(rows, list):
        errors.append(_err("results", "results must be a list with one entry per student"))
        return {"valid": False, "errors": errors, "results": []}

    seen: set[str] = set()
    normalised: list[dict] = []
    for i, raw in enumerate(rows):
        base = f"results[{i}]"
        row = to_plain(raw)
        if not isinstance(row, dict):
            errors.append(_err(base, "Each result must be an object"))
            continue
        sid = row.get("student_id")
        if not isinstance(sid, str) or sid not in props:
            errors.append(_err(f"{base}.student_id", f"Unknown student id {sid!r}"))
            continue
        if sid in seen:
            errors.append(_err(f"{base}.student_id", f"Student {sid} appears more than once"))
            continue
        seen.add(sid)
        manual = props[sid].get("answer_status") == "needs_manual_grading"

        feedback = row.get("feedback", "")
        if feedback is None:
            feedback = ""
        if not isinstance(feedback, str):
            errors.append(_err(f"{base}.feedback", "Feedback must be text"))
            feedback = ""

        score_rows = _scores_as_rows(row.get("scores"))
        got: dict[int, int] = {}
        local_errors = 0
        for j, sr in enumerate(score_rows):
            sfield = f"{base}.scores[{j}]"
            cid = sr.get("criterion_id") if isinstance(sr, dict) else None
            if not _is_int(cid) or cid not in crit:
                errors.append(_err(f"{sfield}.criterion_id", f"Unknown criterion id {cid!r}"))
                local_errors += 1
                continue
            if cid in got:
                errors.append(_err(f"{sfield}.criterion_id", f"Criterion {cid} appears more than once"))
                local_errors += 1
                continue
            try:
                got[cid] = check_score(sr.get("score"), crit[cid])
            except ScoreError as exc:
                errors.append(_err(f"{sfield}.score", str(exc)))
                got[cid] = None  # type: ignore[assignment]  # seen, but invalid
                local_errors += 1
        missing = [c for c in crit if c not in got]
        for c in missing:
            if manual:
                msg = f"Criterion {c} needs a lecturer score: this answer could not be graded automatically"
            else:
                msg = f"Missing score for criterion {c}"
            errors.append(_err(f"{base}.scores", msg))
            local_errors += 1
        if local_errors == 0:
            total = calculate_total(got)
            normalised.append({
                "student_id": sid,
                "scores": {str(c): got[c] for c in crit},
                "feedback": feedback,
                "total": total,
                "percentage": calculate_percentage(total, maximum),
            })

    for sid in props:
        if sid not in seen:
            errors.append(_err("results", f"No result for student {sid}"))

    if errors:
        return {"valid": False, "errors": errors, "results": []}
    return {"valid": True, "errors": [], "results": normalised}


# ---------------------------------------------------------------- batch input (for P2's POST)


def validate_batch_input(rows: Any) -> dict:
    """Check a submitted batch of answers. P2 maps the result to HTTP:
    ``status_code`` is 422 for field errors, 409 for duplicate student ids, else 200.
    Nothing is saved unless status_code is 200."""
    errors: list[dict] = []
    items = rows if isinstance(rows, list) else None
    if items is None or not items:
        return {"valid": False, "status_code": 422, "duplicate_ids": [],
                "errors": [_err("submissions", "Provide at least one answer")]}
    if len(items) > MAX_ANSWERS_PER_BATCH:
        errors.append(_err("submissions", f"A batch can hold at most {MAX_ANSWERS_PER_BATCH} answers"))

    seen: set[str] = set()
    duplicates: list[str] = []
    for i, raw in enumerate(items):
        row = to_plain(raw)
        row = row if isinstance(row, dict) else {}
        sid = row.get("student_id")
        if not isinstance(sid, str) or not sid.strip():
            errors.append(_err(f"submissions[{i}].student_id", "Student id is required"))
        else:
            sid = sid.strip()
            if sid in seen and sid not in duplicates:
                duplicates.append(sid)
            seen.add(sid)
        answer = row.get("answer")
        if not isinstance(answer, str):
            errors.append(_err(f"submissions[{i}].answer", "Answer must be text (it may be empty)"))
        elif len(answer) > MAX_ANSWER_CHARS:
            errors.append(_err(f"submissions[{i}].answer", f"Answer is {len(answer)} characters; the limit is {MAX_ANSWER_CHARS}"))

    status = 422 if errors else (409 if duplicates else 200)
    return {"valid": status == 200, "status_code": status, "duplicate_ids": duplicates, "errors": errors}
