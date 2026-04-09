#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo_root"

docker compose up -d postgres redis
docker compose run --rm \
  -e TEST_DATABASE_URL=postgresql+psycopg://eve_trader:eve_trader@postgres:5432/eve_trader_test \
  backend \
  pytest -o addopts= -m integration
