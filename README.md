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

## Local development

- Backend: see `backend/README.md` (venv + uvicorn, sqlite by default)
- Frontend: see `frontend/README.md` (`npm run dev`, hot reload — preferred for
  UI iteration; the Docker frontend is a production build)

Architecture: `docs/specs/architecture.md` · UI conventions: `docs/specs/ui.md`
