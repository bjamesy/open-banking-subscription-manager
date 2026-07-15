# Architecture: SubTrack (Open Banking Subscription Manager)

**Type:** System design
**Status:** Draft
**Confirmed basis:** Python backend · Plaid (reusing a prior Plaid integration) · Canadian consumer market · AI-assisted (Claude) subscription detection. Everything not in this list is an assumption flagged in §6.

---

## 1. System Overview

SubTrack connects a Canadian consumer's bank accounts via Plaid's read-only transaction API, ingests and stores transaction history, runs a two-phase detection engine (heuristic then AI-assisted) to identify recurring subscription payments, and surfaces a managed list of those subscriptions to the user. The system is strictly read-only from the bank's perspective — no payment initiation or money movement.

This document covers system design only. Product scope, roadmap, data-model DDL, and detection-algorithm details are separate concerns and are not specified here.

---

## 2. High-Level Components

### 2.1 Plaid Integration Layer

**Responsibility:** Own the complete Plaid API surface — Link token creation, public-to-access-token exchange, and transaction sync. Nothing outside this layer calls the Plaid SDK directly.

**Library:** `plaid-python` (official SDK). Plaid's API versioning is coupled to SDK releases, and the SDK handles typed request/response objects — preferable to raw HTTP calls.

**Reuse:** adapted from a prior project's Plaid integration — see §6.1 (resolved).

**Key operations:** `link_token_create` (plain or update mode, passing `access_token` to re-auth an existing Item instead of creating one), `item_public_token_exchange`, `transactions_sync` (cursor-based). No inbound webhook handling — see §5.2.

**Error translation:** Plaid-specific errors (a raw `plaid.exceptions.ApiException`, HTTP-body JSON with `error_code`) are parsed and translated into the provider-agnostic `ProviderError`/`ReauthRequiredError` hierarchy (`providers/base.py`) before leaving this layer — `ingestion/sync.py` and route handlers only ever see the agnostic types, never Plaid SDK exceptions directly, per the `BankingProvider` abstraction boundary (§5.1). `ReauthRequiredError` (Plaid's `ITEM_LOGIN_REQUIRED`) sets `Item.status="error"` and is cleared by Link update mode via `POST /accounts/{item_id}/reconnect`.

**Abstraction boundary:** A `BankingProvider` abstract base class (`abc.ABC`) exposes `create_link_token`, `exchange_public_token`, `sync_transactions`, and `get_accounts`. The rest of the app depends on this ABC, not the Plaid class. This is the single seam where swapping or adding an aggregator (relevant given Canadian coverage uncertainty — see §6.2) requires code changes. Webhook payload parsing is provider-specific by nature and stays inside the Plaid module, not on the ABC.

### 2.2 Transaction Ingestion & Sync

**Responsibility:** Drive transaction sync for all active Items, translate Plaid transactions into normalized records, apply upsert semantics (`added` / `modified` / `removed`), and advance the stored cursor.

**Sync flow per Item:**
1. Load the stored `cursor` for the Item (empty string on first sync).
2. Call `transactions_sync(access_token, cursor)` in a loop until `has_more` is `False`.
3. Upsert `added`/`modified` transactions; mark `removed` transactions.
4. Persist the new `cursor` and `last_synced_at` **in the same DB transaction** as the writes, so a failure re-syncs cleanly from the last good cursor.
5. Enqueue a detection run for affected accounts.

**Trigger model:** No scheduler, no webhooks. Sync runs once at link time and otherwise only on explicit user action (`POST /accounts/rescan`) — see §5.2 for the rationale.

### 2.3 Persistence Layer

**Database:** PostgreSQL — the detection engine queries across transactions grouped by account and merchant, which fits indexed relational joins.

**ORM / migrations:** `SQLAlchemy 2.x` + `Alembic`. `psycopg2` for a synchronous MVP; `asyncpg` is the upgrade path if the API goes async end-to-end (§5.3).

**Secrets at rest:** Plaid `access_token` values are encrypted before storage (Fernet, via the `cryptography` library). The key comes from an environment variable and is never stored in the DB — full design in §5.5.

### 2.4 Subscription Detection Engine

**Responsibility:** Read `Transaction` records for a user and produce/update `DetectedSubscription` records. It owns no data store of its own.

**Inputs:** a set of `Transaction` records (by `user_id`, optionally `account_id`/date range) and a `confidence_threshold` controlling which heuristic candidates escalate to the AI pass.

**Outputs:** `DetectedSubscription` records with `cadence`, `confidence_score`, normalized `merchant_name`, `next_expected_charge`, and `detection_source`.

**Two-phase design (algorithm out of scope for this doc):**
- **Phase 1 — Heuristic:** normalize merchant names, group by merchant + amount, analyze intervals, score confidence. Zero external cost.
- **Phase 2 — AI-assisted (confirmed):** low-confidence candidates are sent to the Claude API (`anthropic` Python SDK) for structured classification (`is_recurring`, `cadence`, `confidence`, `clean_merchant_name`). Batched to control cost. Model choice is an open question (§6.5).

**Trigger:** runs after each successful sync for the affected accounts; also invokable on-demand (e.g. after a user confirms/dismisses a subscription).

### 2.5 API Layer

**Framework:** `FastAPI` — native async (aligns with async DB drivers), first-class Pydantic validation, auto-generated OpenAPI schema for frontend work, low overhead for a single-service MVP.

**Auth:** `python-jose` (JWT) + `bcrypt` used directly (passlib was dropped: unmaintained, warns on bcrypt≥4.1). Access + refresh tokens implemented, the latter revocable via `token_version` (§5.5); social login still open (§6.4).

**Config:** `pydantic-settings` — a `Settings` class reads DB URL, Plaid credentials, encryption key, and JWT secret from environment variables, validated at startup.

**Route groups:** `/auth`, `/link`, `/accounts` (including `POST /accounts/rescan`), `/transactions`, `/subscriptions`.

---

## 3. Data Flow

**3.1 Bank connection:** Browser requests a Link token → API calls `link_token_create` → Plaid Link runs in the browser → returns a `public_token` → API exchanges it for `access_token` + `item_id` → API stores an encrypted Item record → triggers initial sync → returns accounts.

**3.2 Transaction sync (incremental, cursor-based):** One-shot by default — triggered once right after `/link/exchange`, and otherwise only when the user calls `POST /accounts/rescan`. No background polling or webhook listener. The sync worker decrypts the access token, loops `transactions_sync` until `has_more` is false, upserts changes, commits the cursor atomically, and runs detection for the affected user(s).

**3.3 Detection run:** Query normalized transactions → heuristic pass emits candidates → low-confidence candidates batched to Claude → merge results → upsert `DetectedSubscription` records, **preserving any user-set `confirmed`/`dismissed` status** rather than overwriting it.

**3.4 Surface to user:** `GET /subscriptions` returns detected + confirmed subscriptions; `PATCH /subscriptions/{id}` confirms/dismisses; `POST /subscriptions` adds one manually.

---

## 4. Core Entities

| Entity | Description |
|--------|-------------|
| `User` | Authenticated user. Owns Items and subscriptions. |
| `Item` | One Plaid connection to one institution. Holds the encrypted `access_token`, `item_id`, sync `cursor`, and error state. A user may have several. `status`/`error` are set on `ReauthRequiredError` (e.g. Plaid `ITEM_LOGIN_REQUIRED`) and cleared by `POST /accounts/{item_id}/reconnect` after Link update mode. |
| `Account` | A single bank/credit account within an Item. |
| `Transaction` | A normalized Plaid transaction. Notable fields: `plaid_transaction_id` (idempotency key), `account_id`, `amount`, `currency`, `merchant_raw`, `merchant_normalized`, `posted_at`, `removed`, `raw_payload` (JSONB). |
| `DetectedSubscription` | Detection output: `merchant_normalized`, `amount`, `cadence`, `confidence_score`, `status` (detected/confirmed/dismissed), `next_expected_charge`, `detection_source`. |

---

## 5. Key Decisions & Tradeoffs

**5.1 Provider abstraction.** The `BankingProvider` ABC costs a thin indirection layer; the payoff is that adding or swapping an aggregator touches only a new implementation plus a factory lookup — relevant because Plaid's Canadian coverage is uncertain (§6.2).

**5.2 Sync: one-shot by default, manual re-scan on demand.** Originally designed as webhook-primary with a daily polling fallback (both required standing infra: webhook signature verification, an in-process — and later out-of-process — scheduler). Revisited: most users connect a bank once to see what they're paying for, not to run an ongoing monitoring service. The app now syncs once at link time and otherwise only when the user explicitly calls `POST /accounts/rescan` — no background polling, no webhook listener. This removes the single-instance deployment risk that motivated §6.3, and means the app never touches bank data without the user asking, which is a materially better position for §6.8 (PIPEDA / Law 25). Cursor-based `/transactions/sync` is still used over date-range `/transactions/get` because it is idempotent and handles Plaid's modify/remove mutation model — that choice is independent of what triggers a sync.

The re-scan itself doesn't run inline in the HTTP request either — it's a third-party-dependent pipeline (Plaid, then Claude), so `POST /accounts/rescan` creates a `RescanJob` row and hands the work to FastAPI's in-process `BackgroundTasks`, returning `202` immediately; the frontend polls `GET /accounts/rescan/{job_id}` until it's `done`/`failed`. This is deliberately *not* a task queue (Celery/Redis) — that's the same kind of standing infrastructure the scheduler removal (above) was trying to avoid, for what's now an occasional, user-initiated action. Accepted limitation: `BackgroundTasks` is unpersisted, so a server restart mid-job leaves that job's row `"running"` forever with no automatic recovery — tracked in `docs/BACKLOG.md`, not fixed, since it's rare and low-stakes.

**5.3 Sync vs async Python.** Synchronous handlers + `psycopg2` for the MVP (simpler to debug); `asyncpg` + async SQLAlchemy is a defined upgrade if I/O contention appears — no framework change needed.

**5.4 Detection runs as a post-sync batch**, not per-transaction: the heuristic needs a window of transactions and AI calls batch better. It runs once at link time and again on each manual re-scan (§5.2) — there is no scheduled re-run.

**5.5 Secret & token handling.**

| Secret | Storage | Mechanism |
|--------|---------|-----------|
| `PLAID_CLIENT_ID`, `PLAID_SECRET`, `ANTHROPIC_API_KEY` | Env vars only | Read via `pydantic-settings`; never in DB |
| `ENCRYPTION_KEY` (Fernet) | Env var only | 32-byte URL-safe base64; rotate by re-encrypting Items |
| Plaid `access_token` per Item | DB, encrypted | Fernet; decrypted in-memory only during a sync call; never logged or returned in responses |
| JWT signing secret | Env var | `python-jose`; short-lived access + refresh tokens |

Refresh tokens carry a `ver` claim checked against `User.token_version` in `/auth/refresh`; `POST /auth/logout` bumps it, revoking every outstanding refresh token for that user at once (global, not per-device — simplest option that satisfies "logout/compromise can invalidate tokens"). Access tokens are unversioned and remain valid until their short natural expiry even after logout — an accepted tradeoff (`docs/BACKLOG.md`), not a gap left open by oversight.

Access tokens are decrypted only inside the Plaid Integration Layer, immediately before a call. The `Item` ORM model exposes only the ciphertext column; decryption lives on the service layer, not the model.

---

## 6. Assumptions & Open Questions

Confirmed with the user: Python, Plaid, Canadian market, prior-Plaid-code reuse, "SubTrack" name, AI-assisted detection. The items below were **not** confirmed and should be resolved before implementation.

| # | Assumption | Needs confirmation |
|---|-----------|--------------------|
| 6.1 | **Resolved:** the Plaid integration is Python on a current `plaid-python`, implemented in `providers/plaid/provider.py` and sandbox-verified end-to-end. | — |
| 6.2 | **Sandbox-verified (2026-07-06):** Plaid sandbox with `country_codes=[CA]` lists RBC, Scotiabank, TD, BMO, CIBC, Tangerine, Desjardins, National Bank, Vancity, and ATB; full link → sync → detection pipeline ran against TD Canada Trust sandbox data (CAD). | Production institution coverage still needs verification when applying for Plaid production access. Flinks remains the fallback behind the `BankingProvider` ABC. |
| 6.3 | **Resolved:** no scheduler exists — sync is one-shot at link time plus manual re-scan (§5.2). Single-instance deployment is no longer a correctness requirement for sync. | — |
| 6.4 | Auth is username/password + JWT, with revocable refresh tokens (**implemented** — `token_version`, §5.5). | Confirm whether Google/Apple OAuth is in scope. |
| 6.5 | The AI detection pass defaults to `claude-opus-4-8` (overridable via `ANTHROPIC_MODEL`). | Confirm the acceptable per-run API cost envelope; a cheaper model can be configured if needed. |
| 6.6 | **Resolved:** the frontend is a Vite + React + TypeScript SPA in `frontend/` (monorepo), consuming the JSON API via an `/api` proxy. Stack mirrors the prior cresidential project. | — |
| 6.7 | **Resolved:** `raw_payload` (full Plaid object) is retained as JSONB on Postgres (`JSON().with_variant(JSONB(), "postgresql")`, plain JSON under sqlite dev) for re-detection and debugging. | Confirm whether storage cost warrants pruning it. |
| 6.8 | No specific Canadian privacy-law (PIPEDA / Quebec Law 25) affordances are built for MVP. | Given real user financial data, confirm whether consent logging, data deletion, or residency requirements are in scope before storing production data. |
