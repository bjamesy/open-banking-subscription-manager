# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Current state

Monorepo. `backend/` is a working Python/FastAPI service; `frontend/` is a Vite + React + TypeScript SPA (stack mirrors the sibling `../cresidential` project — resolves architecture §6.6). Frontend UI conventions come from `docs/specs/ui.md`.

## Frontend commands (run from `frontend/`)

```bash
npm install
npm run dev      # http://localhost:5173 — proxies /api/* to the backend on :8000
npm run build    # tsc typecheck + vite build
```

All frontend API calls go through the `/api` prefix (Vite proxy strips it in dev) so SPA routes never collide with backend paths. `src/api/client.ts` holds tokens in localStorage and auto-refreshes on 401 with request replay.

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

Runs on the system Python 3.9 locally (Python 3.12 in Docker). `DATABASE_URL` defaults to sqlite for local dev; Postgres in Docker/production. The initial migration is **verified against Postgres 16** (applied cleanly via compose); `Transaction.raw_payload` JSON → JSONB remains a future optimization (architecture §6.7).

## Docker (whole project at once)

```bash
docker compose up --build   # frontend :5173 (nginx SPA + /api proxy), backend :8000, postgres 16
```

Secrets come from `backend/.env`; compose overrides `DATABASE_URL` to the `db` service. Backend container runs `alembic upgrade head` on start. The Docker frontend is a production build — use `npm run dev` for UI iteration.

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

Working end-to-end: config, models + initial migration, Fernet token crypto, the full Plaid provider (link/exchange/sync/accounts), transaction sync/upsert with account auto-creation, **JWT auth** (register/login via `bcrypt` directly — deliberately not passlib, which is unmaintained and warns on bcrypt≥4.1 — all data routes require a Bearer token), the **two-phase detection engine** (heuristic interval analysis in `detection/engine.py`; Claude structured-output pass in `detection/ai.py`, a no-op without `ANTHROPIC_API_KEY`), and **verified Plaid webhooks** (ES256 JWT + body-hash check in `providers/plaid/webhook.py`; `PLAID_VERIFY_WEBHOOKS=false` for local testing only) that trigger background sync + detection.

Also working: refresh tokens (typed access/refresh JWTs, `/auth/refresh`; stateless — no revocation list yet), `/accounts` and `/transactions` read routes (auth-scoped), and the APScheduler daily polling fallback for missed webhooks (in-process, `SYNC_POLL_INTERVAL_HOURS`, disabled when `APP_ENV=test`; assumes single-instance deployment).

Still open (production hardening): `raw_payload` JSON→JSONB, Plaid production readiness (CA institution coverage §6.2, webhook URL on link-token creation), Item error-state handling / re-link flow, logging config, cloud deployment, refresh-token revocation. Resolved since: migration verified on Postgres 16 (via Docker compose), CORS unnecessary (nginx/Vite proxy same-origin design), frontend built.

## UI philosophy

`docs/specs/ui.md` (user-authored) defines the UI conventions for the frontend when it gets built: data-first, desktop-first, information-dense operational UI (Linear/Stripe-dashboard style), consistent resource patterns, tables over cards, no decorative flourish. Follow it for any frontend work.

## Architecture

The system design lives in `docs/specs/architecture.md` — read it before making structural decisions. It defines the component boundaries (Plaid integration layer behind a `BankingProvider` ABC, cursor-based transaction sync, PostgreSQL/SQLAlchemy persistence, the detection engine, and a FastAPI layer), the data flow, the core entities, and — importantly — a list of open questions in §6 that are **not** yet decided (Canadian Plaid coverage, deployment topology, auth model, specific Claude model, frontend framework, privacy-law scope). Do not treat those open questions as settled; confirm with the user before building on them.
