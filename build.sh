#!/usr/bin/env bash
# Seenode build command: ./build.sh
set -euo pipefail

pip install -r requirements.txt
python manage.py collectstatic --noinput