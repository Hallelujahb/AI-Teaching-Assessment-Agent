# Service register

Guide template. One entry per service or tool; combine when one provider covers several purposes. No keys, passwords or payment details. Keep redacted plan evidence (screenshots) available if requested.

| Service and purpose | Free plan or model | Quota shown in provider dashboard | How we stay within it |
| --- | --- | --- | --- |
| Hosting and backend | TODO | TODO | TODO |
| Remote database | TODO | TODO | TODO |
| AI inference | OpenRouter, model `provider/model:free` (pinned, Gate 0 approved) | 20 requests/minute, 50 requests/day on non-billing account | max_retries=0 (no auto-retry); DAILY_MODEL_REQUEST_CAP=40 in limits.py; development on stub provider; live calls only for Gate 0 (≤5), Gate 2 (1), 5 test cases (4 live), 1 injection sample, 1 demo run, judges' fresh input. All prompt iteration done with the stub. |
| Development tools and other APIs | Antigravity, each member's coding assistant (free plan) | TODO | TODO |

Frontend hosting: add to the first row or a new row once chosen.

**Notes:**
- The model is selected via `AI_PROVIDER=openrouter` and `AI_MODEL=provider/model:free` in host secrets (never in the repo).
- `AI_BASE_URL` = `https://openrouter.ai/api/v1`, `AI_API_KEY` = `OPENROUTER_API_KEY`.
- `FORCE_AI_FAILURE=1` forces a quota-style error with zero provider calls, for failure testing without spending quota.
