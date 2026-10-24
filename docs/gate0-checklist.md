# Gate 0 checklist

Nothing is assumed to work until it is checked in our own accounts. Never add a card or turn on billing.

- [ ] AI provider (P3): key created, `python -m app.check_ai` returns a tool call, model name, rate limit or credit balance and terms noted
- [ ] Database (P2): free Postgres created with no payment details, reachable from a laptop
- [ ] Backend host (P2): hello-world FastAPI deployed, answers over HTTPS
- [ ] Frontend host (P1): Vite hello-world deployed
- [ ] Model limits (P3): requests per minute and per day known
- [ ] Organizer question (P5): must the model also select the save tool?
