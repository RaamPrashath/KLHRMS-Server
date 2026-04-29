#!/usr/bin/env bash
# Lint and type-check the codebase
set -euo pipefail

cd "$(dirname "$0")/.."

echo "→ ruff check"
uv run ruff check app tests

echo "→ mypy"
uv run mypy app
