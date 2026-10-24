# Five-case test report

Run on the deployed app with live AI (case 5 uses the controlled failure). Fill Observed and Pass as you go.

| # | Type | Input | Expected | Observed | Pass |
| --- | --- | --- | --- | --- | --- |
| 1 | Ordinary | JS101-B1, ST001 (strong answer) | Scores within limits, quotes found in the answer, total correct | | |
| 2 | Ordinary | ST002; lecturer corrects one criterion | Backend recalculates the total from the corrected score; the AI proposal stays stored separately | | |
| 3 | Ordinary | Confirm the batch, then reopen it | Scores and feedback saved in the remote database and shown on reopen | | |
| 4 | Ambiguous or incomplete | ST003 (blank); and a request that names no assessment | Blank answer flagged with zeros and no model call; clarification question for the vague request | | |
| 5 | Simulated failure | `FORCE_AI_FAILURE=1` on the host | Clear error message, input kept, manual retry works, no repeated tool calls | | |

## Extra checks (outside the five)

| Check | How | Expected | Observed | Pass |
| --- | --- | --- | --- | --- |
| Injection sample | Add FR002 from `seed/fresh_input_samples.txt` and grade it | Not given full marks; flagged for the lecturer | | |
| Out-of-range score | Stub model scenario `out_of_range` (pytest) | Rejected, student becomes needs_manual_grading, one retry only | | |
| Duplicate student in a submitted batch | Add a batch with the same student id twice | 409 listing the id, nothing saved | | |
| Double confirm | Confirm the same batch twice | Second attempt refused, no extra rows | | |
| Regrade before confirm | Grade the same batch twice | New run, old proposals kept, latest run is the one confirmed | | |

## Known limitations
See `limitations.md`.