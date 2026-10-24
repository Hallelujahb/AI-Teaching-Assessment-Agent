# API examples (P2 to confirm)

Base: `{VITE_API_BASE_URL}`. All JSON. Errors are short messages, never stack traces:
`{"error": "short message", "fields": {"field.path": "message"}}` (`fields` only on 422/409 where useful).
Ids follow schema.sql: assessment ids are text (e.g. "JS101"); batch and criterion ids are integers; run ids are UUIDs.

## GET /api/health
200 `{"backend": "ok", "database": "ok", "ai": "configured"}`   (`ai` is `configured` or `not_configured`, never calls the model)

## GET /api/assessments
200 `[{"id": "JS101", "title": "JS101: Variables in JavaScript"}]`

## GET /api/assessments/JS101   (get_assessment_criteria)
200
```json
{"id": "JS101", "title": "JS101: Variables in JavaScript",
 "question": "What is a variable in JavaScript, and how do let, const and var differ?",
 "reference_answer": "A variable is a named container ...",
 "rubric": [{"id": 1, "position": 1, "name": "Defines a variable", "description": "...", "max_score": 2},
            {"id": 2, "position": 2, "name": "Reassignment and redeclaration", "description": "...", "max_score": 3},
            {"id": 3, "position": 3, "name": "Scope", "description": "...", "max_score": 3}],
 "max_total": 8}
```

## GET /api/assessments/JS101/batches
200 `[{"id": 1, "label": "JS101-B1", "student_count": 3, "confirmed": false}]`

## POST /api/assessments/JS101/batches   (judge's fresh input)
Request `{"label": "Judge test 1", "submissions": [{"student_id": "FR001", "answer": "A variable is a thing in code."}]}`
201 `{"id": 2, "label": "Judge test 1", "student_count": 1}`
409 duplicate ids `{"error": "Duplicate student ids", "fields": {"submissions": "FR001"}}`
422 empty id or answer over 2,000 chars, 10 answers max, 20 batches per assessment max.

## POST /api/agent/grade
Request `{"request": "grade the JS101 batch", "assessment_id": "JS101", "batch_id": 1}`   (`assessment_id` and `batch_id` optional when the request text is used)
200 graded:
```json
{"status": "graded", "run_id": "6f1c...-uuid", "max_total": 8,
 "results": [{"student_id": "ST001", "answer_status": "complete",
   "criteria": [{"criterion_id": 1, "proposed_score": 2, "evidence": "A variable is a named container", "evidence_found": true, "explanation": "..."}],
   "feedback": "...", "attention_flags": [], "proposed_total": 8, "proposed_percentage": 100.0},
  {"student_id": "ST003", "answer_status": "blank", "criteria": [], "feedback": "", "attention_flags": ["Blank answer"], "proposed_total": 0, "proposed_percentage": 0.0}]}
```
200 clarification (P3 to confirm shape): `{"status": "needs_clarification", "run_id": "...", "clarification": "Which assessment and batch do you want graded?"}`
429 request volume limit reached (guide: control request volume). 502/504 AI quota or timeout:
`{"error": "The AI service is busy. Try again in a minute.", "kind": "quota", "run_id": "..."}` (`kind`: timeout, quota, invalid_output, tool_limit). The error keeps the request so the UI can offer a manual retry.

## GET /api/runs/{run_id}
200 `{"run_id": "...", "status": "succeeded", "model": "...", "proposals": [ ...as above... ], "tool_log": [{"tool_name": "get_assessment_criteria", "arguments": {"assessment_id": "JS101"}, "outcome": "ok", "duration_ms": 41, "created_at": "..."}]}`

## POST /api/batches/{batch_id}/review   (save_reviewed_results)
Request
```json
{"run_id": "6f1c...", "results": [{"student_id": "ST001", "scores": [{"criterion_id": 1, "score": 2}, {"criterion_id": 2, "score": 3}, {"criterion_id": 3, "score": 3}], "feedback": "Well done."}]}
```
200 `{"batch_id": 1, "approved_at": "...", "results": [{"student_id": "ST001", "total": 8, "percentage": 100.0}]}`
422 `{"error": "Review not valid", "fields": {"results[1].scores[0].score": "Must be a whole number from 0 to 2"}}`

## GET /api/batches/{batch_id}/results
200 `{"batch_id": 1, "approved_at": "...", "max_total": 8, "results": [{"student_id": "ST001", "scores": [{"criterion_id": 1, "score": 2}, {"criterion_id": 2, "score": 3}, {"criterion_id": 3, "score": 3}], "total": 8, "percentage": 100.0, "feedback": "..."}]}`
404 if not confirmed.
