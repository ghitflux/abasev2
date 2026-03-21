#!/bin/bash
# ============================================================
# ABASE v2 — Entrypoint Backend (Produção)
# Aguarda MySQL, roda migrations e collectstatic, inicia Gunicorn
# ============================================================
set -e

echo "[entrypoint] Aguardando MySQL em ${DATABASE_HOST}:${DATABASE_PORT}..."
until nc -z "${DATABASE_HOST:-mysql}" "${DATABASE_PORT:-3306}"; do
    sleep 2
done
echo "[entrypoint] MySQL disponível."

echo "[entrypoint] Rodando migrations..."
python manage.py migrate --noinput

echo "[entrypoint] Coletando static files..."
python manage.py collectstatic --noinput --clear

echo "[entrypoint] Iniciando servidor..."
exec "$@"
