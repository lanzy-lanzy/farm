#!/usr/bin/env bash
# Seenode start command: ./startup.sh   (Port: 8000)
# Migrations run here (not in build) because the SQLite database lives on the
# persistent /data volume, which is only mounted at runtime.
set -euo pipefail

# Ensure the persistent data directory exists (the /data volume mount point).
mkdir -p "${DATA_DIR:-.}"

python manage.py migrate --noinput
python manage.py bootstrap_admin

# One worker + threads: safest concurrency model for SQLite.
exec gunicorn config.wsgi \
    --bind 0.0.0.0:8000 \
    --workers 1 \
    --threads 4 \
    --timeout 120 \
    --access-logfile -