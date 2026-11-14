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
| `ADMIN_USERNAME`       | admin username for first boot                      |
| `ADMIN_PASSWORD`       | strong password for first boot                     |
| `ADMIN_EMAIL`          | optional                                           |

Set `ALLOWED_HOSTS`/`CSRF_TRUSTED_ORIGINS` to the exact `*.seenode.app` host
assigned after the first deploy (or a custom domain once configured).

## 5. First boot

`startup.sh` runs automatically on every start:

1. `migrate` — creates the schema on the fresh volume database.
2. `bootstrap_admin` — creates the admin user from `ADMIN_USERNAME` /
   `ADMIN_PASSWORD` only while the user table is empty; afterwards it is a no-op.
3. Gunicorn binds `0.0.0.0:8000`.

Log in at `https://<your-app>.seenode.app/login/`, then create owner/staff
accounts from the app. Change the bootstrap password after first login.

## Notes

- Local development is unchanged: with no env vars set, `DEBUG=true` and the
  database/media stay in the project root.
- After changing dependencies: `uv lock && uv export --no-hashes --no-emit-project -o requirements.txt`, then commit both files.
- `weasyprint` is installed but unused (PDFs use fpdf2); it is harmless at runtime.
- HTTPS is terminated by Seenode; secure session/CSRF cookies and
  `SECURE_PROXY_SSL_HEADER` are enabled automatically when `DEBUG=false`.