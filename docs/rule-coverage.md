# Rule coverage: section 6 of the build plan

Run `cd backend && python -m pytest`. Rows marked DB need `TEST_DATABASE_URL` pointing at a disposable, seeded Postgres and are skipped otherwise. Rows marked Manual are checked by hand on the deployed app (P5, test report).

| Section 6 case | Where it is tested |
| --- | --- |
| Student missing from model output | `test_validation.py::test_missing_student_only_that_student_invalid` |
| Unknown student id in model output | `test_unknown_student_dropped_and_noted` |
| Duplicate student id in model output | `test_duplicate_student_rejects_all_rows` |
| Unknown, duplicate or missing criterion id | `test_unknown_criterion_invalid`, `test_duplicate_criterion_invalid`, `test_missing_criterion_invalid` |
| Score not an integer, or outside 0 to max | `test_scoring.py::test_score_above_max_is_rejected_not_clamped`, `test_non_integer_or_negative_rejected`, `test_validation.py::test_non_integer_scores_invalid` |
| Invalid after the retry gives needs_manual_grading, one retry only | `test_still_invalid_after_retry_becomes_needs_manual_grading` (asserts 2 model calls) |
| Quote not found: flag, score kept | `test_fake_quote_flagged_and_score_kept`, `test_fake_quote_stub_keeps_score_with_flag` |
| Duplicate student ids in a submitted batch gives 409 | `test_review.py::test_duplicate_ids_give_409_listing_ids`; DB: `test_api.py::test_duplicate_student_ids_409_and_nothing_saved` |
| Empty student id, answer over 2,000 characters gives 422 | `test_empty_student_id_422`, `test_answer_length_boundary`; DB: `test_invalid_batches_422_and_nothing_saved` |
| Batch over 10 answers refused | `test_batch_size_boundary`; DB: `test_invalid_batches_422_and_nothing_saved` |
| Review with missing or repeated student or criterion, unknown id, bad score, no score for a manual student gives 422 field errors | `test_review.py`: `test_missing_student`, `test_unknown_student`, `test_repeated_student`, `test_missing_criterion`, `test_unknown_criterion`, `test_repeated_criterion`, `test_bad_score_gives_field_error`, `test_needs_manual_grading_student_requires_scores` |
| Database fails while confirming: rollback, no partial rows | DB: `test_transactions.py::test_failure_midway_rolls_back_the_first_student`, `test_invalid_score_for_one_student_saves_nobody` |
| Confirm clicked twice | DB: `test_double_confirm_refused_and_nothing_added` |
| Confirm committed but response lost (retry gets 409) | DB: same test as above (second call refused). The UI behaviour is Manual |
| Database fails while saving proposals; DB unreachable | Manual (P2/P5) |
| Turn or tool-call cap reached; timeout or 429; FORCE_AI_FAILURE | `test_failure_stub_raises_quota_error` covers the stub. The caps and test case 5 are Manual on the deployed app |
| Injection text inside an answer | `test_injection.py` (detection, obedient-model rejection, flagging, no false positives) |
| Code marks fewer than 3 letters as unassessable, skips the model | `test_fewer_than_three_letters_is_unassessable`, `test_code_unassessable_gets_zeros_and_flag` |
| Blank answers never sent to the model | `test_valid_batch_blank_is_not_expected`, `test_blank_student_never_graded_by_model_result_dropped` |
| Totals and percentages | `test_st001_total_and_percentage`, `test_st002_total_and_percentage`, `test_percentage_rounds_half_up_to_one_decimal`, `test_lecturer_correction_recalculates_total` |

## Handoff notes

**P3 (agent).** `scoring.detect_answer_status(answer)` before building the model input. After parsing, call `validate_model_output(output, rubric, submissions)`. If `retry_ids` is not empty, call the model once more and then `merge_retry_report(first, retry)`. Finish with `build_proposals(submissions, rubric, report)`, which returns one entry per submission in batch order, ready for `save_proposals`. Write `report["notes"]` to the run log. Import `StubModel` from `app.stub_model` to build and test the loop without quota.

One thing to check in `ai_models.py`: if `CriterionGrade.proposed_score` is declared `int = Field(ge=0)`, Pydantic will reject the whole batch for one negative score and will quietly turn `2.0` into `2` before validation sees it. Declaring it as plain `int` (or `float | int`) lets `validate_student_grade` reject just that student with a reason.

**P2 (backend).** `validate_review(request, rubric, proposals)` returns `{"valid", "errors": [{"field","message"}], "results": [...]}`. Return `errors` in the 422 body and write `results` (which carry the calculated total and percentage) inside the transaction. Use the rubric from the run's `rubric_snapshot`. `validate_batch_input(rows)` gives `status_code` 200, 409 (duplicate ids listed in `duplicate_ids`) or 422 (`errors`), and also enforces the 2,000 character and 10 answer caps. Per-criterion evidence status does not need a database column: call `evidence_found(evidence, answer)` again when serving `/api/runs` and `/api/batches/{id}/results`. The proposal dicts also carry a `feedback` string, which `ai_proposals` has no column for: store it inside the `explanations` JSON or add a column.

**P1 (frontend).** Field paths in 422 errors look like `results[2].scores[0].score`. Evidence text: `found` shows the quote, `not_found` shows "Quote not found in answer", `none` shows "No supporting evidence found".

**P5.** The stub scenarios are listed in `app/stub_model.py` (`SCENARIOS`). Use `out_of_range` for the extra check and `failure` for a stubbed quota error.
