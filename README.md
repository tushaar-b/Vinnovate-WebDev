# Website Change Detector

Monitor public web pages for meaningful changes. The application captures rendered page text and screenshots, filters configured noise, keeps version history, compares text and images, and can queue Discord, Telegram, or SMTP notifications.

## Problem and features

Websites change frequently, and manual checking creates noise and missed updates. This single-user application provides scheduled checks, watch and ignore selectors, normalized content comparisons, screenshot history, text and visual diffs, an activity feed, and an encrypted notification configuration store.

## Architecture

- **Frontend:** React, TypeScript, Vite, and Tailwind. It calls the backend API directly using `VITE_API_URL` when set; otherwise it uses same-origin `/api` paths.
- **API:** FastAPI with SQLAlchemy and Alembic.
- **Persistence:** PostgreSQL for monitors, checks, versions, and notification records; Redis/RQ for asynchronous jobs and scheduling coordination.
- **Capture:** Playwright Chromium; screenshot artifacts are written beneath `DATA_DIR`.
- **Processes:** API, RQ worker, and automatic scheduler run as separate processes.

Production deployments run FastAPI on Railway with PostgreSQL, Redis, and Playwright Chromium, with strict CORS restrictions, production authentication via HMAC-SHA256 session tokens and admin credentials, and the frontend hosted on Vercel.

## Local setup

Requirements: Python 3.12+, Node.js/npm, Docker Desktop, and Playwright Chromium. From the repository root:

```bash
cp .env.example .env
docker compose up -d postgres redis
python -m venv backend/.venv
backend/.venv/bin/pip install -r backend/requirements.txt
backend/.venv/bin/playwright install chromium
(cd backend && PYTHONPATH=. ../backend/.venv/bin/alembic upgrade head)
```

Set `ENCRYPTION_KEY` in `.env` to a generated Fernet key. Keep it stable and private; it is needed to decrypt stored notification credentials.

Start each process in a separate terminal:

```bash
cd backend && PYTHONPATH=. .venv/bin/uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
cd backend && PYTHONPATH=. .venv/bin/python worker.py
cd backend && PYTHONPATH=. .venv/bin/python scheduler.py
cd frontend && npm ci && npm run dev
```

Open `http://localhost:5173`. The API health endpoint is `http://localhost:8000/api/health`. Re-run migrations after pulling schema changes with `cd backend && PYTHONPATH=. .venv/bin/alembic upgrade head`.

## Environment variables

Backend settings are loaded from `.env` (see `.env.example`):

| Variable | Purpose |
| --- | --- |
| `ENVIRONMENT` | Runtime environment name (`production` enforces auth and disables dev fixtures/docs) |
| `ADMIN_PASSWORD` | Required in production. Password for web console login |
| `ALLOWED_ORIGINS` | Comma-separated list of allowed CORS origins (e.g. your Vercel URL) |
| `API_KEY` | Optional programmatic API key (`X-API-Key` or `Authorization: Bearer`) |
| `AUTH_TOKEN_SECRET` | Optional session token secret (derived from `ENCRYPTION_KEY` if unset) |
| `DATABASE_URL` | PostgreSQL SQLAlchemy URL |
| `REDIS_URL` | Redis connection used by RQ and coordination |
| `DATA_DIR` | Persistent screenshot and image diff directory |
| `ENCRYPTION_KEY` | Stable Fernet key for notification credentials |
| `VITE_API_URL` | Frontend API origin pointing to backend HTTPS on Railway |

Vercel project settings should use `frontend/` as the root directory, Vite as framework preset, `npm run build` as build command, and `dist` as output directory. `frontend/vercel.json` provides SPA fallback routing. Set `VITE_API_URL` to your Railway backend HTTPS origin, and ensure that exact Vercel frontend URL is included in `ALLOWED_ORIGINS` on Railway.

## Verification

Run the local verification script with `./scripts/test_implementation.sh`. It prints PASS, FAIL, and SKIPPED for checks it can actually perform. Backend service checks are skipped when the corresponding URL variable is absent. Run the deployed read-only probe with:

```bash
python scripts/smoke_test.py --frontend-url https://your-site.example --backend-url https://your-api.example
```

The smoke test checks HTTPS delivery, health dependencies, CORS, unauthenticated admin access, public response content, and browser loading (requires Playwright and Chromium). It does not create, modify, or delete monitor data. No deployed test results are available because no production deployment exists.

## Current results and limitations

- Frontend production build: **PASS** (`npm run build`, exit 0, 2026-10-16).
- Backend pytest suite: run using `./scripts/test_implementation.sh`; actual results are recorded in `REPORTS/final_submission.txt`.
- Production hosting: **BLOCKED**. Vercel CLI has no authenticated account, outbound DNS resolution to `vercel.com` failed, and the API has no administrative authentication.
- Docker-backed PostgreSQL/Redis checks could not run in this environment because access to the Docker daemon socket was denied.
- There is no multi-user authorization or public SaaS access control. Keep the API bound to localhost or a trusted private network until access protection, production CORS, and persistent hosting are configured.

## Troubleshooting

- **Database connection failure:** check PostgreSQL is running and `DATABASE_URL` points to the expected database.
- **Redis or queue unavailable:** start Redis and confirm `REDIS_URL`; run the worker separately.
- **Screenshots missing after restart:** configure `DATA_DIR` on persistent storage before hosting.
- **Notification decryption fails:** restore the original `ENCRYPTION_KEY`; do not rotate it while encrypted settings exist.
- **Vercel frontend requests fail:** set build-time `VITE_API_URL` to the secured HTTPS backend and allow the frontend origin in CORS.
- **Browser launch fails:** install Chromium with `playwright install chromium` in the backend runtime.
