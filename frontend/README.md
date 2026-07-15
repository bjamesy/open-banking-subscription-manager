# SubTrack Frontend

Vite + React + TypeScript SPA (stack matches the cresidential project; resolves
architecture §6.6). UI conventions follow `../docs/specs/ui.md` — data-first,
desktop-first, sidebar shell, tables over cards.

## Develop

```bash
cd frontend
npm install
cp .env.example .env   # optional: set VITE_GOOGLE_CLIENT_ID to show the Google button
npm run dev        # http://localhost:5173 — proxies /api/* to localhost:8000
```

Run the backend alongside (`uvicorn subtrack.main:app --reload` in `backend/`).
Set `BACKEND_URL` to proxy elsewhere. `VITE_GOOGLE_CLIENT_ID` must match the
backend's `GOOGLE_CLIENT_ID` (`backend/.env`) — the frontend only initiates
sign-in, the backend does the actual verification.

## Build

```bash
npm run build      # tsc typecheck + vite build -> dist/
```

## Layout

- `src/api/client.ts` — axios client (`/api` base), token storage, automatic
  refresh-on-401 with request replay, typed endpoints mirroring the backend
- `src/components/Layout.tsx` — sidebar shell; `ConnectBank.tsx` — Plaid Link
  (adapted from cresidential)
- `src/pages/` — Login (register/sign-in), Subscriptions (stats, table,
  confirm/dismiss, manual add), Transactions (filters + pagination), Accounts
  (linked accounts + connect)
