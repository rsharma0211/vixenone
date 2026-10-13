#!/bin/sh
set -e

if [ "$1" = "prepare" ]; then
    shift
    echo "Executing prepare command with args: $*..."
    exec python -m app.cli.prepare "$@"
fi

if [ "$#" -gt 0 ]; then
    exec "$@"
fi

ENV_LOWER=$(echo "${ENV:-development}" | tr '[:upper:]' '[:lower:]')
if [ "$ENV_LOWER" = "production" ] || [ "$ENV_LOWER" = "prod" ]; then
    PORT="${PORT:-8000}"
    echo "Starting Uvicorn API server in production mode on port ${PORT} (workers=1, no-reload)..."
    exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT}" --workers 1
else
    echo "Applying database migrations..."
    alembic upgrade head

    echo "Starting Uvicorn API server..."
    exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
fi
