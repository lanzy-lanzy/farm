#!/usr/bin/env bash
# Seenode start command: ./startup.sh   (Port: 8000)
# Migrations run here (not in build) because the SQLite database lives on the
# persistent /data volume, which is only mounted at runtime.
set -euo pipefail

# Ensure the persistent data directory exists (the /data volume mount point).
mkdir -p "${DATA_DIR:-.}"

# Loud warning when the database is NOT on a mounted volume: every redeploy or
# restart would then start from an empty database (accounts and data lost).
python - <<'PY'
import os
d = os.path.realpath(os.environ.get("DATA_DIR", "."))
p = d
while not os.path.ismount(p) and p != os.path.dirname(p):
    p = os.path.dirname(p)
if p == os.path.dirname(p):
    print(f"WARNING: DATA_DIR={d} is not on a persistent volume; data resets on every redeploy/restart.")
else:
    print(f"DATA_DIR={d} is on mounted volume {p}.")
PY

python manage.py migrate --noinput
python manage.py bootstrap_admin

# One worker + threads: safest concurrency model for SQLite.
exec gunicorn config.wsgi \
    --bind 0.0.0.0:8000 \
    --workers 1 \
    --threads 4 \
    --timeout 120 \
    --access-logfile -