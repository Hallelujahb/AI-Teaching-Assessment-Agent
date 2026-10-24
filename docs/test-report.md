# Test report

Run on the deployed app with live AI. Owner: P5.

| # | Type | Input | Expected | Observed | Pass |
| --- | --- | --- | --- | --- | --- |
| 1 | Ordinary | ST001, strong answer | Scores in range, quotes found in the answer, total correct | | |
| 2 | Ordinary | ST002, lecturer corrects one criterion | Backend recalculates the total. AI proposal stays stored separately | | |
| 3 | Ordinary | Confirm the batch, then reopen it | Saved in the remote database and shown on reopen | | |
| 4 | Ambiguous or incomplete | ST003 blank, and a request that names no assessment | Blank flagged with zeros and no model call for it. Clarification question for the vague request | | |
| 5 | Simulated failure | FORCE_AI_FAILURE=1 | Clear error, input kept, manual retry works, no repeated tool calls | | |

Extra checks: injection sample, out-of-range score from a stub, duplicate student in a batch, double confirm, regrade before confirm.
