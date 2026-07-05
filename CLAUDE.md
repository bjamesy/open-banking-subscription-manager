# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Current state

Monorepo. `backend/` is a scaffolded Python/FastAPI service (boots, DB migration applies, tests pass). `frontend/` is an empty placeholder — framework not chosen yet (architecture §6.6).

## Commands (run from `backend/`)

```bash
python3 -m venv .venv && source .venv/bin/activate && pip install -e ".[dev]"
cp .env.example .env    # fill in; generate ENCRYPTION_KEY per the comment in that file

uvicorn subtrack.main:app --reload    # serve; /docs, /health
alembic revision --autogenerate -m "msg" && alembic upgrade head   # migrations
pytest                                 # all tests
pytest tests/test_crypto.py::test_roundtrip   # single test
ruff check . && ruff format .          # lint / format
mypy src                               # type check
```

Runs on the system Python 3.9. `DATABASE_URL` defaults to sqlite for local dev; production is Postgres. The generated initial migration reflects sqlite — regenerate/verify against Postgres before deploying (and migrate `Transaction.raw_payload` JSON → JSONB, architecture §6.7).

## What the project is

SubTrack — an open banking subscription manager. It connects a Canadian consumer's bank accounts via Plaid (read-only), ingests transaction history, detects recurring subscription payments, and surfaces them for the user to review and manage. Strictly read-only: no payment initiation.

## Confirmed decisions

These are settled and should be treated as constraints:

- **Backend language:** Python
- **Open banking:** Plaid. The integration in `backend/src/subtrack/providers/plaid/provider.py` is adapted from the sibling `../cresidential` project (its `backend/app/services/plaid_service.py` and `routers/plaid.py`). Two deliberate changes vs. that source: country code `US` → `CA`, and access tokens are persisted Fernet-encrypted in Postgres rather than kept in an in-memory dict.
- **Market:** Canadian consumers
- **Detection:** two-phase — heuristic first, then an AI-assisted pass using the Claude API (`anthropic` SDK)
- **Working name:** SubTrack

## Implemented vs. stubbed

Working: config, models + initial migration, Fernet token crypto, the full Plaid provider (link/exchange/sync/accounts), transaction sync/upsert, and the API routes. **Not yet implemented** (deliberate scaffold gaps, each marked with a TODO in code): the detection engine (`detection/engine.py` raises `NotImplementedError`), user auth (`/link` and `/subscriptions` use a placeholder user — `TODO(auth)`), and Plaid webhook signature verification (`api/routes/webhooks.py`). Don't assume these are done.

## UI philosophy

`docs/specs/ui.md` (user-authored) defines the UI conventions for the frontend when it gets built: data-first, desktop-first, information-dense operational UI (Linear/Stripe-dashboard style), consistent resource patterns, tables over cards, no decorative flourish. Follow it for any frontend work.

## Architecture

The system design lives in `docs/specs/architecture.md` — read it before making structural decisions. It defines the component boundaries (Plaid integration layer behind a `BankingProvider` ABC, cursor-based transaction sync, PostgreSQL/SQLAlchemy persistence, the detection engine, and a FastAPI layer), the data flow, the core entities, and — importantly — a list of open questions in §6 that are **not** yet decided (Canadian Plaid coverage, deployment topology, auth model, specific Claude model, frontend framework, privacy-law scope). Do not treat those open questions as settled; confirm with the user before building on them.
