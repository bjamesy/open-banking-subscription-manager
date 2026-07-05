# SubTrack Backend

Python / FastAPI backend for SubTrack. See `../docs/specs/architecture.md` for the system design.

## Setup

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env   # then fill in values; generate an ENCRYPTION_KEY (see .env.example)
```

## Run

```bash
uvicorn subtrack.main:app --reload
# API at http://localhost:8000 — docs at /docs, health at /health
```

## Database migrations (Alembic)

```bash
alembic revision --autogenerate -m "message"   # create a migration from model changes
alembic upgrade head                            # apply migrations
alembic downgrade -1                            # roll back one
```

## Tests / lint / types

```bash
pytest                                  # all tests
pytest tests/test_crypto.py::test_roundtrip   # a single test
ruff check .                            # lint
ruff format .                           # format
mypy src                               # type check
```

## Layout

- `src/subtrack/config.py` — settings loaded from env via pydantic-settings
- `src/subtrack/db/` — SQLAlchemy `Base`, engine/session, and models
- `src/subtrack/providers/` — `BankingProvider` ABC + Plaid implementation (adapted from the cresidential project)
- `src/subtrack/ingestion/` — transaction sync orchestration
- `src/subtrack/detection/` — subscription detection engine (heuristic + AI passes)
- `src/subtrack/api/routes/` — FastAPI routers
