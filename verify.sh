#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT_DIR"

echo "=== 1. Checking Ruff formatting ==="
./venv/bin/ruff format --check app/ tests/

echo "=== 2. Checking Ruff lints ==="
./venv/bin/ruff check app/ tests/

echo "=== 3. Checking Bandit security ==="
./venv/bin/bandit -r app/ -c .bandit

echo "=== 4. Running Pytest with coverage >= 35% ==="
PYTHONPATH=. ./venv/bin/pytest tests/ -v --cov=app --cov-fail-under=35

echo "=== ALL QUALITY GATES PASSED! ==="
