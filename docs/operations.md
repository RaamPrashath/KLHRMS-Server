# Operations Guide

## One Command Infra

Start all dependencies plus API:

```bash
docker compose up -d --build
```

Services:

- PostgreSQL on `5432`
- Oracle XE (Oracle Free) on `1521`
- MongoDB on `27017`
- Redis on `6379`
- OpenTelemetry Collector on `4318` (HTTP), `4317` (gRPC)
- API on `8000`

## Local Development

```bash
pip install -e .[dev]
cp .env.example .env
alembic upgrade head
uvicorn app.main:app --reload --port 8000
```

Offer-letter PDFs are rendered with Playwright/Chromium. The Docker image installs Chromium with `uv run playwright install --with-deps chromium`. For non-Docker local runs, install the browser once with `uv run playwright install chromium` before generating PDFs.

## CI and Local Test Scripts

```bash
bash scripts/lint.sh
bash scripts/test.sh
```

CI workflow runs:

- Ruff lint
- Python compile check
- Pytest smoke tests

## Auth Validation Checklist

1. Check active auth mode:

```bash
curl -s http://localhost:8000/api/v1/auth/provider
```

2. Validate credentials path by mode:

- `custom_jwt`: use `/api/v1/auth/login`
- `api_key`: include static header
- `entra`: include bearer token from Entra

## Health and DB Connectivity

```bash
curl -s http://localhost:8000/api/v1/health
curl -s http://localhost:8000/api/v1/health/postgres
curl -s http://localhost:8000/api/v1/health/oracle
curl -s http://localhost:8000/api/v1/health/mongodb
curl -s http://localhost:8000/api/v1/health/redis
```
