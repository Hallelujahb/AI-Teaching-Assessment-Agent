"""Agent loop with caps, clarification path and one retry.

run_grading(request_text, assessment_id, batch_id) is called by routes/grading.py.

Flow
  1. Work out which assessment and batch is meant (ids from the request, or matched from its text
     against assessment titles and batch labels). If that is not clear, or the assessment has no
     rubric or reference answer, return a clarification question. No run, no model call, no guess.
  2. Create the run (committed at once, so a failed run still leaves a record).
  3. Tool phase: the model calls get_assessment_criteria and get_submissions (both logged with the
     run id). Blank and too-short answers are removed from what the model sees.
  4. One grading call for the whole batch. scoring.validate_model_output checks every student.
  5. Invalid students: ONE retry call, for those students only. Still invalid -> needs_manual_grading.
  6. scoring.build_proposals + runs.save_proposals (one transaction), then return the run view.

Caps per run (plan section 4): 4 tool-phase model turns + the grading call = 5 turns, 4 tool calls,
60 seconds in total (AGENT_TIMEOUT_SECONDS). The single retry is the only call on top of that.
Any failure closes the run as failed and raises AIError with the run id. Nothing loops by itself.

Owner: P3
Plan: section 4
"""
from __future__ import annotations

import json
import logging
import re
import time

from psycopg.types.json import Json

from . import ai_provider, config, prompts, runs, scoring, tools
from .ai_models import output_schema
from .db import get_conn
from .errors import AIError, AppError, NotFound

log = logging.getLogger("qeleme")

DEFAULT_QUESTION = "Which assessment and batch should I grade? Pick one, or name it in the request."
_STOP_WORDS = {"with", "that", "this", "from", "into", "batch", "grade", "answers", "assessment"}


class _Clarification(Exception):
    """Internal: unwinds the run when the model needs the lecturer to say more."""

    def __init__(self, question: str):
        super().__init__(question)
        self.question = question


# ---------------------------------------------------------------- entry point


# The real modules, captured at import time for default fallback.
_tools_module = tools
_runs_module = runs
_scoring_module = scoring


def run_grading(request_text: str | None, assessment_id: int | str | None, batch_id: int | str | None,
                provider=None, tools=None, runs=None, scoring=None) -> dict:
    """Grade one batch.

    Returns a dict with ``outcome`` key:
      - ``{"outcome": "graded", "run_id": ..., "results": [...]}``
      - ``{"outcome": "needs_clarification", "run_id": ..., "clarification": {"question": str}}``
      - ``{"outcome": "error", "run_id": ..., "error": {"kind": str, "message": str}}``

    ``provider``, ``tools``, ``runs`` and ``scoring`` default to the real modules;
    tests pass fakes to avoid network and database calls.
    """
    _tools = tools if tools is not None else _tools_module
    _runs = runs if runs is not None else _runs_module
    _scoring = scoring if scoring is not None else _scoring_module
    _provider = provider or ai_provider

    # FORCE_AI_FAILURE short-circuits before any work (test case 5).
    if config.force_ai_failure():
        return {"outcome": "error", "run_id": None, "error": {"kind": "quota", "message": "force_ai_failure"}}

    # Resolve target: if both ids provided, skip DB lookup.
    aid, bid, question = _resolve(request_text, assessment_id, batch_id, _tools)
    if question:
        return {"outcome": "needs_clarification", "run_id": None,
                "clarification": {"question": question}}

    assessment = _tools.fetch_assessment(aid)
    problem = _assessment_problem(assessment)
    if problem:
        return {"outcome": "needs_clarification", "run_id": None,
                "clarification": {"question": problem}}
    if not config.force_ai_failure() and not provider and not config.ai_configured():
        return {"outcome": "error", "run_id": None, "error": {"kind": "unavailable", "message": "not configured"}}

    rubric = [{k: c.get(k) for k in ("id", "position", "name", "description", "max_score")}
              for c in assessment["rubric"]]
    run_id = _runs.create_run(bid, config.ai_model() or None, rubric)   # 404 / 409 come from here
    try:
        result = _run(run_id, aid, bid, assessment, rubric, request_text, _provider, _tools, _runs, _scoring)
        return {"outcome": "graded", "run_id": run_id, **result}
    except _Clarification as ask:
        _close(_runs, run_id, "Clarification requested")
        return {"outcome": "needs_clarification", "run_id": run_id,
                "clarification": {"question": ask.question}}
    except AIError as exc:
        _close(_runs, run_id, exc.message)
        kind = exc.extra.get("kind") or "invalid_output"
        return {"outcome": "error", "run_id": run_id, "error": {"kind": kind, "message": exc.message}}
    except AppError as exc:
        _close(_runs, run_id, "Grading stopped")
        return {"outcome": "error", "run_id": run_id, "error": {"kind": "bad_request", "message": exc.message}}
    except ValueError:
        log.exception("Proposals did not match the batch")
        _close(_runs, run_id, "Proposals did not match the batch")
        return {"outcome": "error", "run_id": run_id, "error": {"kind": "invalid_output", "message": "Proposals did not match"}}
    except Exception:
        log.exception("Unexpected error in grading run %s", run_id)
        _close(_runs, run_id, "Unexpected error")
        return {"outcome": "error", "run_id": run_id, "error": {"kind": "unexpected", "message": "Unexpected error"}}


# The real modules, captured at import time for default fallback.


def _resolve(request_text, assessment_id, batch_id, _tools):
    """Resolve (assessment_id, batch_id, clarification). If both ids given, return them directly."""
    if assessment_id is not None and batch_id is not None:
        return assessment_id, batch_id, None
    # Fall back to catalog-based resolution (needs database or fake catalog).
    return _resolve_target(request_text, assessment_id, batch_id)


def _clarification(run_id: str | None, question: str) -> dict:
    return {"outcome": "needs_clarification", "run_id": run_id, "clarification": {"question": question}}


def _close(_runs, run_id: str, message: str) -> None:
    try:
        _runs.finish_run(run_id, "failed", message)
    except Exception:  # noqa: BLE001 - never hide the real error
        log.warning("Could not close run %s", run_id)


# ---------------------------------------------------------------- which assessment and batch?


def _words(text: str) -> set[str]:
    return set(re.findall(r"[a-z0-9]+", (text or "").lower()))


def _resolve_target(request_text, assessment_id, batch_id):
    """Returns (assessment_id, batch_id, clarification_question). A question means: ask, do not guess."""
    with get_conn() as conn:
        assessments = conn.execute("SELECT id, title FROM assessments ORDER BY id").fetchall()
        batches = conn.execute(
            "SELECT b.id, b.assessment_id, b.label, EXISTS (SELECT 1 FROM reviewed_results r "
            "JOIN submissions s ON s.id=r.submission_id WHERE s.batch_id=b.id) AS confirmed "
            "FROM submission_batches b ORDER BY b.id").fetchall()
    return pick_target(request_text, assessment_id, batch_id, assessments, batches)


def pick_target(request_text, assessment_id, batch_id, assessments, batches):
    """Pure matching logic (no database), so it can be unit tested."""
    text = (request_text or "").lower()
    by_id = {a["id"]: a for a in assessments}
    if not assessments:
        return None, None, "There are no assessments yet, so there is nothing to grade."

    if batch_id is not None:
        batch = next((b for b in batches if b["id"] == batch_id), None)
        if batch is None:
            raise NotFound("Batch not found.")
        if assessment_id is not None and assessment_id != batch["assessment_id"]:
            return None, None, "That batch belongs to a different assessment. Which assessment and batch do you mean?"
        return batch["assessment_id"], batch["id"], None

    if assessment_id is None:
        hits = _match_assessments(text, assessments, batches)
        if len(hits) != 1:
            return None, None, _which_assessment(assessments, many=len(hits) > 1)
        assessment_id = hits[0]
    elif assessment_id not in by_id:
        raise NotFound("Assessment not found.")

    candidates = [b for b in batches if b["assessment_id"] == assessment_id]
    if not candidates:
        return None, None, f"{by_id[assessment_id]['title']} has no batches of answers yet."
    named = [b for b in candidates if b["label"].lower() in text]
    open_ones = [b for b in candidates if not b["confirmed"]]
    chosen = named[0] if len(named) == 1 else (
        candidates[0] if len(candidates) == 1 else (open_ones[0] if len(open_ones) == 1 else None))
    if chosen is None:
        labels = ", ".join(b["label"] for b in candidates)
        return None, None, f"Which batch of {by_id[assessment_id]['title']} should I grade? Options: {labels}."
    return assessment_id, chosen["id"], None


def _match_assessments(text: str, assessments: list[dict], batches: list[dict]) -> list[int]:
    request_words = _words(text)
    hits = []
    for a in assessments:
        code = a["title"].split(":")[0].strip().lower()
        title_words = {w for w in _words(a["title"]) if len(w) >= 4 and w not in _STOP_WORDS}
        label_hit = any(b["assessment_id"] == a["id"] and b["label"].lower() in text for b in batches)
        if (code and code in text) or (request_words & title_words) or label_hit:
            hits.append(a["id"])
    return hits


def _which_assessment(assessments: list[dict], many: bool) -> str:
    options = "; ".join(f"{a['title']} (id {a['id']})" for a in assessments)
    lead = "That matches more than one assessment." if many else "Which assessment should I grade?"
    return f"{lead} Options: {options}. Which assessment and batch do you mean?"


def _assessment_problem(assessment: dict) -> str | None:
    title = assessment.get("title", "This assessment")
    if not assessment.get("rubric"):
        return f"{title} has no rubric yet, so I cannot grade it. Add a rubric first."
    if not str(assessment.get("reference_answer") or "").strip():
        return f"{title} has no reference answer yet, so I cannot grade it. Add one first."
    return None


# ---------------------------------------------------------------- the run


def _run(run_id, aid, bid, assessment, rubric, request_text, _provider, _tools, _runs, _scoring):
    deadline = time.monotonic() + config.agent_timeout_seconds()
    ctx: dict = {"criteria": None, "subs": None}

    _tool_phase(run_id, aid, bid, request_text, ctx, deadline, _provider, _tools, _scoring)

    subs = ctx["subs"]
    to_model = [s for s in subs if not _scoring.detect_answer_status(s["answer"])]   # blank never reaches the model
    graded_input = {**assessment, "rubric": rubric}

    if not to_model:
        output = {"status": "graded", "clarification": None, "results": []}
        _log_step(run_id, "model_grading", {"students": 0}, "skipped: every answer was blank or too short",
                  time.perf_counter())
        parsed_any = True
    else:
        output = _grading_call(run_id, "model_grading", graded_input, to_model, deadline, _provider)
        parsed_any = output is not None
        if isinstance(output, dict) and output.get("status") == "needs_clarification":
            question = output.get("clarification")
            raise _Clarification(question.strip() if isinstance(question, str) and question.strip() else DEFAULT_QUESTION)

    report = _scoring.validate_model_output(output, rubric, subs)
    if not report["all_valid"]:
        retry_ids = list(report["retry_ids"])
        problems = {sid: report["students"][sid]["reasons"] for sid in retry_ids}
        retry_subs = [s for s in subs if s["student_id"] in retry_ids]
        retry_output = _grading_call(run_id, "model_retry", graded_input,
                                     [s for s in retry_subs], deadline, _provider, problems=problems)
        parsed_any = parsed_any or retry_output is not None
        if not parsed_any:
            raise AIError("invalid_output")
        retry_report = _scoring.validate_model_output(retry_output, rubric, retry_subs)
        report = _scoring.merge_retry_report(report, retry_report)

    proposals = _scoring.build_proposals(subs, rubric, report)
    manual = sum(1 for p in proposals if p["answer_status"] == "needs_manual_grading")
    _log_step(run_id, "validate_model_output",
              {"students": len(subs), "needs_manual_grading": manual, "notes": report["notes"][:10]},
              f"ok: {len(proposals) - manual} proposed, {manual} need manual grading", time.perf_counter())

    _runs.save_proposals(run_id, proposals)
    view = _runs.get_run(run_id)
    return {"max_total": view["max_total"],
            "results": view["proposals"], "tool_log": view["tool_log"]}


# ---------------------------------------------------------------- tool phase


def _complete(ctx: dict) -> bool:
    return ctx["criteria"] is not None and ctx["subs"] is not None


def _tool_phase(run_id, aid, bid, request_text, ctx, deadline, _provider, _tools, _scoring) -> None:
    messages = [{"role": "system", "content": prompts.TOOL_PHASE_SYSTEM},
                {"role": "user", "content": prompts.tool_phase_user(request_text, aid, bid)}]
    calls_used = 0
    for _ in range(config.AGENT_MAX_TOOL_TURNS):
        reply = _provider.generate(messages, tools=prompts.TOOL_DECLARATIONS, deadline=deadline)
        if not reply.tool_calls:
            if _complete(ctx):
                return
            text = (reply.text or "").strip()               # no data fetched: the model is asking something
            raise _Clarification(text if text else DEFAULT_QUESTION)
        messages.append(reply.assistant_message)
        for call in reply.tool_calls:
            if calls_used >= config.AGENT_MAX_TOOL_CALLS:
                raise AIError("tool_limit")
            calls_used += 1
            content = _execute_tool(run_id, call, aid, bid, ctx, _tools, _scoring)
            messages.append({"role": "tool", "tool_call_id": call.id, "content": content})
        if _complete(ctx):
            return                                          # got everything: no wasted extra turn
    if not _complete(ctx):
        raise AIError("tool_limit")


def _as_int(value) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float) and value.is_integer():
        return int(value)
    if isinstance(value, str) and re.fullmatch(r"-?\d+", value.strip()):
        return int(value.strip())
    return None


def _execute_tool(run_id, call, aid, bid, ctx, _tools, _scoring) -> str:
    """Run one tool the model asked for and return the text the model sees. The ids are checked in
    code: a model that invents an id gets an error back and nothing runs."""
    args = json.loads(call.arguments) if isinstance(call.arguments, str) else (call.arguments or {})
    args = args if isinstance(args, dict) else {}
    if call.name == "get_assessment_criteria":
        if _as_int(args.get("assessment_id")) != aid:
            return json.dumps({"error": f"Unknown assessment id. Use assessment_id={aid}."})
        try:
            result = _tools.get_assessment_criteria(aid, run_id=run_id)
        except AppError as exc:
            return json.dumps({"error": exc.message})
        ctx["criteria"] = result
        return json.dumps({
            "question": result["question"], "reference_answer": result["reference_answer"],
            "max_total": result["max_total"],
            "rubric": [{"criterion_id": c["id"], "name": c["name"], "description": c["description"],
                        "max_score": c["max_score"]} for c in result["rubric"]]})
    if call.name == "get_submissions":
        if _as_int(args.get("assessment_id")) != aid or _as_int(args.get("batch_id")) != bid:
            return json.dumps({"error": f"Unknown id. Use assessment_id={aid} and batch_id={bid}."})
        try:
            result = _tools.get_submissions(aid, bid, run_id=run_id)
        except AppError as exc:
            return json.dumps({"error": exc.message})
        ctx["subs"] = result["submissions"]
        assessable = [s for s in result["submissions"] if not _scoring.detect_answer_status(s["answer"])]
        skipped = len(result["submissions"]) - len(assessable)
        return json.dumps({"batch": result["label"], "submissions": assessable,
                           "note": f"{skipped} blank or too-short answer(s) were handled by the system and are not listed."})
    return json.dumps({"error": f"Unknown tool {call.name!r}."})


# ---------------------------------------------------------------- grading calls


def _grading_call(run_id, label, assessment, answers, deadline, _provider, problems=None) -> dict | None:
    """One model call that grades the given students. Returns the parsed JSON dict, or None."""
    started = time.perf_counter()
    messages = [{"role": "system", "content": prompts.GRADING_SYSTEM},
                {"role": "user", "content": prompts.grading_prompt(assessment, answers, problems)}]
    ids = [a["student_id"] for a in answers]
    try:
        reply = _provider.generate(messages, schema=output_schema, deadline=deadline)
    except AIError as exc:
        _log_step(run_id, label, {"students": ids}, f"error: {exc.extra.get('kind')}", started)
        raise
    output = ai_provider.extract_json(reply.text)
    _log_step(run_id, label, {"students": ids}, "ok" if output is not None else "output was not valid JSON", started)
    return output


def _log_step(run_id, name, arguments, outcome, started) -> None:
    """Write an agent step (grading call, validation) to the tool log. Never raises."""
    try:
        with get_conn() as conn:
            conn.execute(
                "INSERT INTO tool_logs (run_id, tool_name, arguments, outcome, duration_ms) VALUES (%s,%s,%s,%s,%s)",
                (run_id, name, Json(arguments), str(outcome)[:300], int((time.perf_counter() - started) * 1000)))
    except Exception:  # noqa: BLE001
        log.warning("Could not write tool log for %s", name)
