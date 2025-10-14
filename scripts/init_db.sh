#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR=${ROOT_DIR:-/app}
SEED_SCRIPT=${SEED_SCRIPT:-/scripts/seed_users.py}

cd "$ROOT_DIR"

echo "[init_db] Running Alembic migrations..."
alembic upgrade head

if [ -f "$SEED_SCRIPT" ]; then
  echo "[init_db] Running seed script ${SEED_SCRIPT}..."
  python "$SEED_SCRIPT"
else
  echo "[init_db] No seed script found at ${SEED_SCRIPT}, skipping." >&2
fi
