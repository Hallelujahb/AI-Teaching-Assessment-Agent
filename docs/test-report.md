# Five-case test report

Run on the deployed app with live AI (case 5 uses the controlled failure). Fill Observed and Pass as you go.

| # | Type | Input | Expected | Observed | Pass |
| --- | --- | --- | --- | --- | --- |
| 1 | Ordinary | JS101-B1, ST001 (strong answer) | Scores within limits, explanations supported by the answer, total correct | | |
| 2 | Ordinary | ST002; lecturer corrects one criterion | Total recalculated by the backend from the corrected score | | |
| 3 | Ordinary | Confirm the batch, then reopen it | Scores and feedback saved in the remote database and shown on reopen | | |
| 4 | Ambiguous or incomplete | ST003 (blank); and a request that names no assessment | Blank answer identified, zeros, not sent to the model; clarification question for the vague request | | |
| 5 | Simulated failure | `FORCE_AI_FAILURE=1` | Clear error message, input kept, manual retry works, no repeated tool calls | | |

## Known limitations
See `limitations.md`.
