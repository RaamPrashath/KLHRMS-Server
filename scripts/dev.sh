#!/usr/bin/env bash
# Start the development server with hot reload
set -euo pipefail

cd "$(dirname "$0")/.."

uv run uvicorn app.main:app \
  --host 0.0.0.0 \
  --port "${APP_PORT:-8000}" \
  --reload \
  --reload-dir app
