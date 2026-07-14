# Backlog

Everything intentionally not done yet, with enough context to pick up cold.
State as of 2026-07-06: full pipeline works end-to-end against Plaid sandbox
(see `specs/architecture.md` §6 for resolved assumptions).

## Production hardening (before real users / deployment)

### 1. Plaid production readiness
- Apply for Plaid production access; **verify Canadian institution coverage in
  production** — sandbox lists RBC/Scotiabank/TD/BMO/CIBC/Tangerine/Desjardins/
  National Bank/Vancity/ATB (§6.2), but production coverage is approved
  separately. Flinks remains the fallback behind the `BankingProvider` ABC.

### 2. Item error handling / re-link flow
`Item.status` / `Item.error` columns exist but nothing sets them. When Plaid
returns `ITEM_LOGIN_REQUIRED` (expired bank login), sync fails silently for
that Item (logged, skipped until the user re-scans). Needed: catch Plaid
errors in `ingestion/sync.py`, set `Item.status="error"` + `error` code,
surface in the Accounts UI, and implement Link **update mode** (link token
with `access_token`) for re-authentication.

### 3. Refresh-token revocation
Refresh JWTs are stateless (`security/auth.py`) — logout/compromise can't
invalidate them before expiry (30 days). Add a token table or `token_version`
column on `users`, checked in `/auth/refresh`.

### 4. `Transaction.raw_payload` JSON → JSONB (§6.7)
Model uses the generic `JSON` type (kept for sqlite dev compatibility).
Postgres migration should switch to JSONB for indexing/size. One Alembic
migration; guard with dialect check or accept Postgres-only.

### 5. Logging configuration
Root logger is unconfigured — app `logger.info(...)` (link exchange, manual
re-scan) is invisible under uvicorn. Configure structured logging (level from
env) at app startup; ensure tokens/PII never logged.

### 6. Cloud deployment
No deploy target chosen. §6.3's single-instance constraint no longer applies
(no scheduler — see §5.2), so deployment topology is unconstrained on that
front. Still needed: TLS, secrets management (not .env files), Postgres
backups.

## Detection quality

### 7. AI prompt: exclude non-subscription recurring charges
Live run kept `CD Deposit`, `Credit Card Payment`, `Automatic Payment`,
`Gusto Payroll` as "subscriptions" — recurring, but transfers/payroll, not
subscriptions. Tweak `SYSTEM_PROMPT` in `detection/ai.py` (e.g. "bank
transfers, credit-card payments, deposits, and payroll are not
subscriptions — mark is_recurring=false") and re-verify against sandbox data.

### 8. Merchant normalizer refinement
`normalize_merchant` is deliberately crude (strips digits, lowercases,
truncates at first "."): `"SPOTIFY P1234ABCD"` → `"spotify p abcd"`. Good
enough because the AI pass cleans names, but heuristic-only mode (no API key)
shows raw-ish names. Improve suffix/location stripping if heuristic-only
matters.

## Parked (explicit scope decisions, revisit when relevant)

- **Google/Apple OAuth** (§6.4) — email/password + JWT shipped; social login
  would add `authlib` and provider config.
- **Privacy compliance** (§6.8, PIPEDA / Quebec Law 25) — required before
  storing real Canadian user financial data: consent logging, data deletion
  endpoint (delete user → Items/transactions/subscriptions + Plaid
  `/item/remove`), data-residency review.
- **Product stretch** — renewal alerts (from `next_expected_charge`), spend
  trend charts, multi-account household view, unused-subscription flagging.
- **Orphaned rescan jobs on restart** (§5.2) — `POST /accounts/rescan` runs via
  FastAPI's in-process `BackgroundTasks`, tracked in a `RescanJob` row. If the
  backend restarts mid-job, that row stays `"running"` forever — nothing
  reconciles it, and the frontend poll just spins. Accepted for now (rare,
  low-stakes, user can just try again); revisit with a startup sweep
  (mark stale `running`/`pending` jobs `"failed"`) or a real task queue only
  if this becomes a real problem.
