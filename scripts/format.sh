#!/usr/bin/env bash
# Auto-format the codebase with ruff
set -euo pipefail

cd "$(dirname "$0")/.."

echo "→ ruff format"
uv run ruff format app tests

echo "→ ruff check --fix"
uv run ruff check --fix app tests
