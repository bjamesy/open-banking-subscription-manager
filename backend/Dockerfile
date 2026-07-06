FROM python:3.12-slim

WORKDIR /app

# Install dependencies first for layer caching.
COPY pyproject.toml ./
COPY src ./src
RUN pip install --no-cache-dir .

COPY alembic.ini ./
COPY alembic ./alembic

EXPOSE 8000

# Apply migrations, then serve. DATABASE_URL comes from the environment.
CMD ["sh", "-c", "alembic upgrade head && uvicorn subtrack.main:app --host 0.0.0.0 --port 8000"]
