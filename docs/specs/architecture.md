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

**Responsibility:** Own the complete Plaid API surface — Link token creation, public-to-access-token exchange, transaction sync, and webhook receipt/verification. Nothing outside this layer calls the Plaid SDK directly.

**Library:** `plaid-python` (official SDK). Plaid's API versioning is coupled to SDK releases, and the SDK handles typed request/response objects — preferable to raw HTTP calls.

**Reuse:** A Plaid integration already exists in a prior project and is intended for reuse (confirmed). Before copying, audit it for the Plaid API version and `plaid-python` version it targets, and for whether it was written in Python — see §6.1.

**Key operations:** `link_token_create`, `item_public_token_exchange`, `transactions_sync` (cursor-based), and inbound webhook signature verification (`Plaid-Verification` JWT header).

**Abstraction boundary:** A `BankingProvider` abstract base class (`abc.ABC`) exposes `create_link_token`, `exchange_public_token`, `sync_transactions`, and `get_accounts`. The rest of the app depends on this ABC, not the Plaid class. This is the single seam where swapping or adding an aggregator (relevant given Canadian coverage uncertainty — see §6.2) requires code changes. Webhook payload parsing is provider-specific by nature and stays inside the Plaid module, not on the ABC.

### 2.2 Transaction Ingestion & Sync

**Responsibility:** Drive transaction sync for all active Items, translate Plaid transactions into normalized records, apply upsert semantics (`added` / `modified` / `removed`), and advance the stored cursor.

**Sync flow per Item:**
1. Load the stored `cursor` for the Item (empty string on first sync).
2. Call `transactions_sync(access_token, cursor)` in a loop until `has_more` is `False`.
3. Upsert `added`/`modified` transactions; mark `removed` transactions.
4. Persist the new `cursor` and `last_synced_at` **in the same DB transaction** as the writes, so a failure re-syncs cleanly from the last good cursor.
5. Enqueue a detection run for affected accounts.

**Scheduler:** `APScheduler` (in-process) for the polling fallback — avoids standing up Celery/Redis for the MVP. This assumes single-instance deployment (see §6.3); multi-instance would require moving the scheduler out-of-process to prevent duplicate jobs.

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

**Auth:** `python-jose` (JWT) + `bcrypt` used directly (passlib was dropped: unmaintained, warns on bcrypt≥4.1). Short-lived access tokens implemented; refresh tokens still open (§6.4).

**Config:** `pydantic-settings` — a `Settings` class reads DB URL, Plaid credentials, encryption key, and JWT secret from environment variables, validated at startup.

**Route groups:** `/auth`, `/link`, `/accounts`, `/transactions`, `/subscriptions`, `/webhooks/plaid` (signature-verified).

---

## 3. Data Flow

**3.1 Bank connection:** Browser requests a Link token → API calls `link_token_create` → Plaid Link runs in the browser → returns a `public_token` → API exchanges it for `access_token` + `item_id` → API stores an encrypted Item record → triggers initial sync → returns accounts.

**3.2 Transaction sync (incremental, cursor-based):** Triggered by a Plaid `TRANSACTIONS_SYNC_UPDATES_AVAILABLE` webhook (primary), a daily APScheduler poll (fallback), or an on-demand call after connection. The sync worker decrypts the access token, loops `transactions_sync` until `has_more` is false, upserts changes, commits the cursor atomically, and enqueues detection.

**3.3 Detection run:** Query normalized transactions → heuristic pass emits candidates → low-confidence candidates batched to Claude → merge results → upsert `DetectedSubscription` records, **preserving any user-set `confirmed`/`dismissed` status** rather than overwriting it.

**3.4 Surface to user:** `GET /subscriptions` returns detected + confirmed subscriptions; `PATCH /subscriptions/{id}` confirms/dismisses; `POST /subscriptions` adds one manually.

---

## 4. Core Entities

| Entity | Description |
|--------|-------------|
| `User` | Authenticated user. Owns Items and subscriptions. |
| `Item` | One Plaid connection to one institution. Holds the encrypted `access_token`, `item_id`, sync `cursor`, and error state. A user may have several. |
| `Account` | A single bank/credit account within an Item. |
| `Transaction` | A normalized Plaid transaction. Notable fields: `plaid_transaction_id` (idempotency key), `account_id`, `amount`, `currency`, `merchant_raw`, `merchant_normalized`, `posted_at`, `removed`, `raw_payload` (JSONB). |
| `DetectedSubscription` | Detection output: `merchant_normalized`, `amount`, `cadence`, `confidence_score`, `status` (detected/confirmed/dismissed), `next_expected_charge`, `detection_source`. |

---

## 5. Key Decisions & Tradeoffs

**5.1 Provider abstraction.** The `BankingProvider` ABC costs a thin indirection layer; the payoff is that adding or swapping an aggregator touches only a new implementation plus a factory lookup — relevant because Plaid's Canadian coverage is uncertain (§6.2).

**5.2 Sync: webhook-primary, polling fallback.** Webhooks are lower-latency and lower-cost but can be missed (downtime, delivery failure), so the daily poll is a correctness guarantee, not the primary path. Cursor-based `/transactions/sync` is used over date-range `/transactions/get` because it is idempotent and handles Plaid's modify/remove mutation model.

**5.3 Sync vs async Python.** Synchronous handlers + `psycopg2` for the MVP (simpler to debug); `asyncpg` + async SQLAlchemy is a defined upgrade if I/O contention appears — no framework change needed.

**5.4 Detection runs as a post-sync batch**, not per-transaction: the heuristic needs a window of transactions, AI calls batch better, and daily freshness is adequate for a subscription tracker. On-demand re-run is supported for UI-driven re-scoring.

**5.5 Secret & token handling.**

| Secret | Storage | Mechanism |
|--------|---------|-----------|
| `PLAID_CLIENT_ID`, `PLAID_SECRET`, `ANTHROPIC_API_KEY` | Env vars only | Read via `pydantic-settings`; never in DB |
| `ENCRYPTION_KEY` (Fernet) | Env var only | 32-byte URL-safe base64; rotate by re-encrypting Items |
| Plaid `access_token` per Item | DB, encrypted | Fernet; decrypted in-memory only during a sync call; never logged or returned in responses |
| JWT signing secret | Env var | `python-jose`; short-lived access + refresh tokens |

Access tokens are decrypted only inside the Plaid Integration Layer, immediately before a call. The `Item` ORM model exposes only the ciphertext column; decryption lives on the service layer, not the model.

---

## 6. Assumptions & Open Questions

Confirmed with the user: Python, Plaid, Canadian market, prior-Plaid-code reuse, "SubTrack" name, AI-assisted detection. The items below were **not** confirmed and should be resolved before implementation.

| # | Assumption | Needs confirmation |
|---|-----------|--------------------|
| 6.1 | The reusable Plaid integration is (or can be adapted to) Python and a current `plaid-python`. | Locate the prior project; confirm language and Plaid/SDK version before copying. |
| 6.2 | Plaid covers the target Canadian institutions. Plaid's Canadian coverage has historically trailed its US coverage. | Verify sandbox + production institution coverage. Evaluate a Canadian-native aggregator (e.g. Flinks) as a fallback behind the `BankingProvider` ABC. |
| 6.3 | Single-instance deployment (makes in-process APScheduler safe). | If multi-instance, move scheduling to an out-of-process worker (Celery + Redis) to avoid duplicate sync jobs. |
| 6.4 | Auth is username/password + JWT (**implemented**; access tokens only). | Confirm whether Google/Apple OAuth and refresh tokens are in scope. |
| 6.5 | The AI detection pass defaults to `claude-opus-4-8` (overridable via `ANTHROPIC_MODEL`). | Confirm the acceptable per-run API cost envelope; a cheaper model can be configured if needed. |
| 6.6 | **Resolved:** the frontend is a Vite + React + TypeScript SPA in `frontend/` (monorepo), consuming the JSON API via an `/api` proxy. Stack mirrors the prior cresidential project. | — |
| 6.7 | `raw_payload` (full Plaid object) is retained as JSONB for re-detection and debugging. | Confirm whether storage cost warrants pruning it. |
| 6.8 | No specific Canadian privacy-law (PIPEDA / Quebec Law 25) affordances are built for MVP. | Given real user financial data, confirm whether consent logging, data deletion, or residency requirements are in scope before storing production data. |
