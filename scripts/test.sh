#!/usr/bin/env bash
# Run the test suite
set -euo pipefail

cd "$(dirname "$0")/.."

export SKIP_STARTUP_DB=true
export REDIS_ENABLED=false

echo "→ pytest"
uv run pytest tests/ -v --tb=short
