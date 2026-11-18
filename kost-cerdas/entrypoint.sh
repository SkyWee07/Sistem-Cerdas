#!/bin/sh
set -eu

python manage.py migrate --noinput
python manage.py import_kos --if-empty
exec gunicorn kostcerdas.wsgi:application \
  --bind "0.0.0.0:${PORT:-3000}" \
  --workers "${WEB_CONCURRENCY:-2}" \
  --timeout 60 \
  --access-logfile - \
  --error-logfile -
