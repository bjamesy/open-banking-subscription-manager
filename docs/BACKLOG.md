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
- The application requires live privacy-policy/terms URLs — `/privacy` and
  `/terms` now exist (`frontend/src/pages/Privacy.tsx`, `Terms.tsx`), linked
  from `Login.tsx`, the `ConnectBank.tsx` consent modal, and `Settings.tsx`.
  **Both are placeholder text, not lawyer-reviewed** — needs real legal
  review before submitting to Plaid or relying on with actual users. Two
  known stubs inside: the Data Residency section (pending item 2's hosting
  decision) and the contact address (`privacy@subtrack.app` — swap for a
  real one).

### 2. Cloud deployment
No deploy target chosen. §6.3's single-instance constraint no longer applies
(no scheduler — see §5.2), so deployment topology is unconstrained on that
front. Still needed: TLS, secrets management (not .env files), Postgres
backups.

## Detection quality

### 3. AI prompt: exclude non-subscription recurring charges
Live run kept `CD Deposit`, `Credit Card Payment`, `Automatic Payment`,
`Gusto Payroll` as "subscriptions" — recurring, but transfers/payroll, not
subscriptions. Tweak `SYSTEM_PROMPT` in `detection/ai.py` (e.g. "bank
transfers, credit-card payments, deposits, and payroll are not
subscriptions — mark is_recurring=false") and re-verify against sandbox data.

### 4. Merchant normalizer refinement
`normalize_merchant` is deliberately crude (strips digits, lowercases,
truncates at first "."): `"SPOTIFY P1234ABCD"` → `"spotify p abcd"`. Good
enough because the AI pass cleans names, but heuristic-only mode (no API key)
shows raw-ish names. Improve suffix/location stripping if heuristic-only
matters.

## Parked (explicit scope decisions, revisit when relevant)

- **Apple OAuth** (§6.4) — Google Sign-In shipped (`POST /auth/google`,
  ID-token verification via `google-auth`, no `authlib`/redirect flow
  needed); Apple isn't requested yet and would need Sign in with Apple's
  own (JWT-based, client-secret-as-a-signed-JWT) flow.
- **Privacy compliance** (§6.8, PIPEDA / Quebec Law 25) — required before
  storing real Canadian user financial data. **Data deletion shipped**
  (`DELETE /auth/me`, Settings page — cascades Items/Accounts/Transactions/
  DetectedSubscriptions/RescanJobs, best-effort Plaid `/item/remove`).
  **Consent logging shipped** (`GET`/`POST /consent`, `ConsentRecord` —
  append-only, versioned via `CURRENT_VERSION` in `api/routes/consent.py`;
  gated in `ConnectBank.tsx` before a *fresh* bank link, disclosing that
  transaction data goes to Anthropic for AI detection — reconnects don't
  re-prompt since consent was already given at first link). **The
  disclosure copy is placeholder text, not reviewed by a lawyer** — needs
  real legal review before this is safe to rely on with actual users. Still
  open: data-residency review (Postgres location + Anthropic's US-based API
  are a cross-border transfer Law 25 cares about) — this isn't "code," it
  falls out of wherever this gets deployed and needs an actual privacy-law
  review, not just an engineering fix.
- **Product stretch** — renewal alerts (from `next_expected_charge`), spend
  trend charts, multi-account household view, unused-subscription flagging.
- **Orphaned rescan jobs on restart** (§5.2) — `POST /accounts/rescan` runs via
  FastAPI's in-process `BackgroundTasks`, tracked in a `RescanJob` row. If the
  backend restarts mid-job, that row stays `"running"` forever — nothing
  reconciles it, and the frontend poll just spins. Accepted for now (rare,
  low-stakes, user can just try again); revisit with a startup sweep
  (mark stale `running`/`pending` jobs `"failed"`) or a real task queue only
  if this becomes a real problem.
- **Access tokens outlive logout** — `/auth/logout` bumps `User.token_version`,
  which revokes all outstanding *refresh* tokens immediately, but access
  tokens carry no version claim and remain valid until their natural
  15-minute expiry. Accepted tradeoff (checking a DB column on every request
  to close that window wasn't worth it for a token this short-lived); revisit
  only if access token lifetime grows significantly.
