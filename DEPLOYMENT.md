# Deploying to Seenode

Target: https://seenode.com — web service from the GitHub repo `lanzy-lanzy/farm`.

Architecture: Django 6 + Gunicorn (1 worker, 4 threads), SQLite and uploaded
media on a persistent `/data` volume, static files served by WhiteNoise.
No external database service is required.

## 1. Push the repo

Seenode builds from GitHub, so commit and push the deploy files first:
`pyproject.toml`, `uv.lock`, `requirements.txt`, `build.sh`, `startup.sh`,
`.gitattributes`, `config/settings.py`, `config/urls.py`,
`accounts/management/commands/bootstrap_admin.py`.

## 2. Create the web service

In the Seenode dashboard, create a Web Service from the repo (branch `master`).

| Setting       | Value           |
| ------------- | --------------- |
| Python        | 3.13            |
| Build command | `bash build.sh` |
| Start command | `bash startup.sh` |
| Port          | `8000`          |

## 3. Persistent storage

In the service's Storage tab, add a volume:

- Mount path: `/data`
- Size: 5 GB (minimum; $0.50/GB/month). Size can be increased later, never decreased.

The database (`/data/db.sqlite3`) and uploads (`/data/media`) live here and
survive redeploys and restarts. Keep the service at exactly 1 replica.

## 4. Environment variables

The values live in the local, gitignored `.env` file. In the service's
Environment tab, use **Import from .env** and paste its contents (or set the
variables individually):

| Variable               | Value                                              |
| ---------------------- | -------------------------------------------------- |
| `DEBUG`                | `false`                                            |
| `SECRET_KEY`           | generate: `python -c "import secrets; print(secrets.token_urlsafe(50))"` |
| `ALLOWED_HOSTS`        | your app host, e.g. `your-app.seenode.app` (no scheme) |
| `CSRF_TRUSTED_ORIGINS` | `https://your-app.seenode.app` (with scheme)       |
| `DATA_DIR`             | `/data`                                            |
| `ADMIN_USERNAME`       | admin username                                     |
| `ADMIN_PASSWORD`       | admin password                                     |
| `ADMIN_EMAIL`          | optional                                           |
| `BUYER_USERNAME` / `BUYER_PASSWORD` | buyer portal login (linked to the `BUYER_CONTACT` buyer, default "Manila Egg Traders") |
| `SUPPLIER_USERNAME` / `SUPPLIER_PASSWORD` | supplier portal login (linked to the `SUPPLIER_CONTACT` supplier, default "Agrivet Feed Supply") |

The environment is the source of truth for these three logins: every boot
recreates or re-syncs them, so a password changed in the app reverts on the next
restart. To change one permanently, change it here and redeploy.

Set `ALLOWED_HOSTS`/`CSRF_TRUSTED_ORIGINS` to the exact `*.seenode.app` host
assigned after the first deploy (or a custom domain once configured).

## 5. First boot

`startup.sh` runs automatically on every start:

1. Volume check — logs `WARNING: DATA_DIR=... is not on a persistent volume`
   when `/data` is not mounted (the database would reset on every redeploy).
2. `migrate` — creates the schema on the fresh volume database.
3. `bootstrap_admin` — creates or re-syncs the admin, buyer and supplier
   accounts from the environment variables above (safe to run every boot).
4. Gunicorn binds `0.0.0.0:8000`.

Log in at `https://<your-app>.seenode.app/login/`, then create owner/staff
accounts from the app.

## Notes

- Local development is unchanged: with no env vars set, `DEBUG=true` and the
  database/media stay in the project root.
- After changing dependencies: `uv lock && uv export --no-hashes --no-emit-project -o requirements.txt`, then commit both files.
- `weasyprint` is installed but unused (PDFs use fpdf2); it is harmless at runtime.
- HTTPS is terminated by Seenode; secure session/CSRF cookies and
  `SECURE_PROXY_SSL_HEADER` are enabled automatically when `DEBUG=false`.