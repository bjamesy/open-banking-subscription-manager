# open-banking-subscription-manager

SubTrack — connects Canadian bank accounts via Plaid, imports transactions,
and auto-detects recurring subscriptions.

## Boot everything (Docker)

```bash
cp backend/.env.example backend/.env   # fill in Plaid creds + ENCRYPTION_KEY
docker compose up --build
```

- App: http://localhost:5173 (SPA + `/api` proxy)
- API: http://localhost:8000 (docs at `/docs`)
- Postgres data persists in the `pgdata` volume (`docker compose down -v` resets)

## Testing with Plaid sandbox

With `PLAID_ENV=sandbox`, use Plaid's test credentials in the Link widget
(Accounts → "Connect bank account"):

| Prompt | Value |
|---|---|
| Phone number step | Skip via **"Continue without phone number"** (or `415-555-0011`, any code) |
| Institution | Any listed (e.g. TD Canada Trust — CA institutions appear with `PLAID_COUNTRY_CODES=CA`) |
| Username | `user_good` |
| Password | `pass_good` |

After linking, ~12 test accounts and ~48 transactions import automatically and
detection runs. The sandbox banner at the bottom of the Link widget also shows
the expected credentials for each step. More test personas (errors, MFA):
https://plaid.com/docs/sandbox/test-credentials/

## Local development

- Backend: see `backend/README.md` (venv + uvicorn, sqlite by default)
- Frontend: see `frontend/README.md` (`npm run dev`, hot reload — preferred for
  UI iteration; the Docker frontend is a production build)

Architecture: `docs/specs/architecture.md` · UI conventions: `docs/specs/ui.md`
