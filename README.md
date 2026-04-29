# Enterprise FastAPI Boilerplate

Configuration-first FastAPI boilerplate for enterprise APIs with multi-database support and pluggable authentication.

## Features

- FastAPI + Pydantic v2
- SQLAlchemy ORM with dedicated engines
  - PostgreSQL async engine
  - Oracle dedicated engine
- MongoDB async client (Motor)
- Redis-backed caching + rate limiting middleware (in-memory fallback)
- Alembic migrations for relational schema evolution
- OpenTelemetry instrumentation (FastAPI, SQLAlchemy, Mongo)
- Auth mode switching by configuration
  - `custom_jwt`
  - `api_key`
  - `entra`
- Tag-based health checks for each dependency
- CI workflow with lint, compile, and smoke tests

## Documentation Map

- Configuration reference: [docs/configuration.md](docs/configuration.md)
- Runbook and operations: [docs/operations.md](docs/operations.md)

## Project Structure

```text
app/
  api/
    deps.py
    v1/
      router.py
      routes/
        auth.py
        users.py
        items.py
        health.py
  core/
    auth_provider.py
    config.py
    logging.py
    redis.py
    security.py
    telemetry.py
  db/
    base.py
    session.py
    seed.py
    models/
      user.py
      item.py
  middleware/
    cache.py
    rate_limit.py
    request_context.py
  schemas/
  services/
  main.py
alembic/
docker-compose.yml
.github/workflows/ci.yml
tests/
scripts/
```

## Quick Start (Local)

```bash
pip install -e .[dev]
cp .env.example .env
alembic upgrade head
uvicorn app.main:app --reload --port 8000
```

Open API docs:

- http://localhost:8000/docs

## One-Command Infra + API

```bash
docker compose up -d --build
```

This starts PostgreSQL, Oracle Free, MongoDB, Redis, OTEL Collector, and the API.

## Auth Modes

Set `AUTH_PROVIDER` in `.env`:

- `custom_jwt`
  - enables `/api/v1/auth/register` and `/api/v1/auth/login`
- `api_key`
  - requires `STATIC_API_KEY_HEADER` + `STATIC_API_KEY_VALUE`
- `entra`
  - requires Entra issuer/audience/JWKS-related settings

Inspect active mode:

```bash
curl -s http://localhost:8000/api/v1/auth/provider
```

## Dummy Seed User

- Email: `admin@example.com`
- Password: `Admin@12345`

## Health Checks

- `GET /api/v1/health`
- `GET /api/v1/health/postgres`
- `GET /api/v1/health/oracle`
- `GET /api/v1/health/mongodb`
- `GET /api/v1/health/redis`

## Test and CI

Run locally:

```bash
bash scripts/lint.sh
bash scripts/test.sh
```

GitHub Actions CI:

- Ruff check
- Python compile check
- pytest smoke suite
