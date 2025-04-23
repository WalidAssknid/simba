#!/bin/sh
set -e

echo "Starting application initialization..."

python manage.py migrate

PORT="${PORT:-8000}"

CORES=$(nproc)
WORKERS=$((CORES * 2))
if [ "$WORKERS" -lt 2 ]; then
  WORKERS=2
fi

echo "Starting Gunicorn on port $PORT with $WORKERS workers"

exec gunicorn simba.wsgi:application \
    --bind "0.0.0.0:$PORT" \
    --workers $WORKERS \
    --worker-class sync \
    --worker-connections 1000 \
    --timeout 240 \
    --max-requests 1000 \
    --max-requests-jitter 50 \
    --log-level info \
    --access-logfile - \
    --error-logfile - \
    --limit-request-line 4094 \
    --limit-request-fields 100
