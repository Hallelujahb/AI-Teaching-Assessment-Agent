## Validation and scoring (Person 4)

**Principle.** The AI proposes, the code validates, the lecturer decides. Model output is untrusted. Every number that reaches the lecturer or the database is checked or calculated in `backend/app/scoring.py`, which has no network or database dependency and is covered by automated tests.

**Before the model.** `detect_answer_status` marks an answer `blank` (empty, whitespace or punctuation only) or `unassessable` (fewer than 3 letters). Those answers never reach the model. Zeros are proposed and a flag is added. Blank answers cost no quota and cannot be credited by mistake.

**After the model.** `validate_model_output` checks every student the model was asked about:

- Each rubric criterion appears exactly once, with no unknown ids.
- Each score is a whole number from 0 to that criterion's maximum. Scores are never clamped, because silently turning 3 into 2 would hide a model error and put a number in front of the lecturer that nobody chose. A bad score makes that student invalid instead.
- The model may only set `complete`, `incomplete` or `unassessable`. `blank` and `needs_manual_grading` belong to the backend.
- Missing students are marked invalid. Unknown students and results for answers handled in code are dropped and noted in the run log. A duplicated student has every row rejected.
- Invalid students are retried once, as a batch, for the whole run. Anyone still invalid becomes `needs_manual_grading`: no scores are proposed and the lecturer must enter every criterion before Confirm is enabled. Other students are unaffected.

**Evidence.** `evidence_found` normalises whitespace, case and quote marks, then checks that the quote appears inside the student's answer. An empty quote means "no supporting evidence found", which is not a failure. A quote that is not in the answer is shown as "Quote not found in answer" with a flag. The score is kept, because the quote may be a paraphrase while the mark is right, and the decision belongs to the lecturer.

**Injection.** The prompt tells the model that answers are data. If the model obeys anyway, code is the second layer. An answer containing instruction-like text is flagged, and a result that gives full marks to such an answer is rejected, then retried, then sent to manual grading. This is a heuristic backstop for obvious attacks, not a guarantee (see limitations).

**Lecturer review.** `validate_review` requires every student in the batch exactly once, every criterion exactly once, integer scores in range, and scores for every `needs_manual_grading` student. It returns field-level errors for the 422 response. Totals and percentages (rounded half-up to one decimal) are always calculated by the backend from the rubric maximums. Any total the browser sends is ignored.

**Atomic saves.** With P2, confirming writes every `reviewed_results` row in one transaction. A failure leaves no partial rows, the unique constraint on submission id refuses a second confirm, and the AI proposal is stored in its own table and never edited.
