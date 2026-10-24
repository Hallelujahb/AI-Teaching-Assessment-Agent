# API examples

Base: `{VITE_API_BASE_URL}`. All JSON. Ids follow schema.sql: assessment, batch and criterion ids are integers (JS101 is 1 after a reset); run ids are UUIDs.
Errors are short and never contain a stack trace:
`{"error": "short message", "message": "short message", "fields": {"field.path": "message"}}` (`fields` only on 409/422 where useful).

## GET /api/health
200 `{"backend": "ok", "database": "ok", "ai": "configured"}`. `ai` is `configured` or `not_configured`. Never calls the model.

## GET /api/assessments
200 `[{"id": 1, "title": "JS101: Variables in JavaScript"}, {"id": 2, "title": "PY101: Lists and tuples in Python"}]`

## GET /api/assessments/1   (get_assessment_criteria)
200
```json
{"id": 1, "title": "JS101: Variables in JavaScript",
 "question": "What is a variable in JavaScript, and how do let, const and var differ?",
 "reference_answer": "A variable is a named container ...",
 "rubric": [{"id": 1, "position": 1, "name": "Defines a variable", "description": "...", "max_score": 2},
            {"id": 2, "position": 2, "name": "Reassignment and redeclaration", "description": "...", "max_score": 3},
            {"id": 3, "position": 3, "name": "Scope", "description": "...", "max_score": 3}],
 "max_total": 8}
```
404 `{"error": "Assessment not found.", "message": "Assessment not found."}`

## GET /api/assessments/1/batches
200 `[{"id": 1, "label": "JS101-B1", "created_at": "...", "student_count": 3, "confirmed": false, "latest_run_id": null}]`

## POST /api/assessments/1/batches   (judge's fresh input)
Request `{"label": "Judge test 1", "submissions": [{"student_id": "FR001", "answer": "A variable is a thing in code."}]}`
201 `{"id": 3, "label": "Judge test 1", "student_count": 1}`
409 duplicate student ids, or label already used, or 20 batches already: `{"error": "Duplicate student ids: FR001", "message": "...", "fields": {"submissions": "FR001"}}`
422 empty id, answer over 2,000 characters, more than 10 answers, empty label.
413 body over 50 KB.

## POST /api/agent/grade
Request `{"request": "grade the JS101 batch", "assessment_id": 1, "batch_id": 1}`. All three fields are optional; the agent matches the request text against assessment titles and batch labels.
200 graded:
```json
{"status": "graded", "run_id": "6f1c0c0e-0000-0000-0000-000000000000", "max_total": 8,
 "results": [
  {"student_id": "ST001", "answer": "...", "answer_status": "complete",
   "criteria": [{"criterion_id": 1, "name": "Defines a variable", "max_score": 2, "proposed_score": 2,
                 "evidence": "A variable is a named container", "evidence_status": "found", "evidence_found": true,
                 "explanation": "..."}],
   "feedback": "...", "attention_flags": [], "proposed_total": 8, "proposed_percentage": 100.0},
  {"student_id": "ST003", "answer": "", "answer_status": "blank",
   "criteria": [{"criterion_id": 1, "name": "Defines a variable", "max_score": 2, "proposed_score": 0,
                 "evidence": "", "evidence_status": "none", "evidence_found": null, "explanation": ""}],
   "feedback": "", "attention_flags": ["Blank answer: no model call, zeros proposed"],
   "proposed_total": 0, "proposed_percentage": 0.0}],
 "tool_log": [{"tool_name": "get_assessment_criteria", "arguments": {"assessment_id": 1}, "outcome": "ok", "duration_ms": 41, "created_at": "..."}]}
```
`evidence_status` is `found`, `none` (no quote) or `not_found` (quote is not in the answer). A student the model could not grade validly has `answer_status` `needs_manual_grading`, `proposed_score` null and `proposed_total` null.
200 clarification: `{"status": "needs_clarification", "run_id": null, "clarification": "Which assessment should I grade? Options: ..."}`. `run_id` is null when the question comes before a run exists.
409 batch already confirmed, or a run is already in progress for the batch.
429 too many requests, or the daily run limit is reached.
502, 503 or 504 AI problem: `{"error": "The AI service is busy or its free quota is used up. Your input is kept. Try again in a minute.", "message": "...", "kind": "quota", "run_id": "..."}`. `kind` is `timeout` (504), `quota` (503), `invalid_output` (502), `tool_limit` (502) or `unavailable` (503). The input is kept so the UI can offer a manual retry.

## GET /api/runs/{run_id}
200
```json
{"run_id": "...", "batch_id": 1, "assessment_id": 1, "batch_label": "JS101-B1", "status": "succeeded",
 "model": "...", "error": null, "started_at": "...", "finished_at": "...", "is_latest": true, "max_total": 8,
 "rubric": [{"id": 1, "position": 1, "name": "Defines a variable", "max_score": 2}],
 "proposals": [ ...same shape as results above... ],
 "tool_log": [{"tool_name": "get_submissions", "arguments": {"assessment_id": 1, "batch_id": 1}, "outcome": "ok", "duration_ms": 38, "created_at": "..."}]}
```
404 for an unknown or malformed run id.

## POST /api/batches/1/review   (save_reviewed_results)
Request
```json
{"run_id": "6f1c0c0e-...", "results": [{"student_id": "ST001", "scores": [{"criterion_id": 1, "score": 2}, {"criterion_id": 2, "score": 3}, {"criterion_id": 3, "score": 3}], "feedback": "Well done."}]}
```
Every student in the batch and every criterion must appear exactly once. Totals sent by the browser are ignored.
200 `{"batch_id": 1, "run_id": "...", "approved_at": "...", "max_total": 8, "results": [{"student_id": "ST001", "total": 8, "percentage": 100.0}]}`
409 already confirmed, or a newer run exists.
422 `{"error": "The review is not valid.", "message": "...", "fields": {"results[1].scores[0].score": "Score 3 is outside the allowed range 0 to 2"}}`

## GET /api/results   (confirmed batches)
200 `[{"batch_id": 1, "label": "JS101-B1", "assessment_id": 1, "assessment_title": "JS101: Variables in JavaScript", "approved_at": "...", "student_count": 3}]`

## GET /api/batches/1/results   (reopen, with the AI proposal alongside)
200
```json
{"batch_id": 1, "batch_label": "JS101-B1", "assessment_id": 1, "run_id": "...", "approved_at": "...", "max_total": 8,
 "rubric": [{"id": 1, "position": 1, "name": "Defines a variable", "max_score": 2}],
 "results": [{"student_id": "ST001", "answer": "...",
              "scores": [{"criterion_id": 1, "score": 2}, {"criterion_id": 2, "score": 3}, {"criterion_id": 3, "score": 3}],
              "total": 8, "percentage": 100.0, "feedback": "...",
              "ai_proposal": { ...one proposal in the shape above... }}]}
```
404 if the batch has not been confirmed yet.