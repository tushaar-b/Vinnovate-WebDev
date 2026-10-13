# Project Changelog by Phases

## Phase 0: Project Scaffold and Environment Setup
- Initialized local Git repository and recorded project specifications.
- Configured `.gitignore` and `.env.example`.
- Created Docker Compose configuration for PostgreSQL 16 and Redis 7.
- Initialized FastAPI backend scaffold with Python 3.12, SQLAlchemy 2, Alembic, and Redis.
- Implemented `/api/health` endpoint reporting database and Redis connectivity.
- Initialized React / Vite / TypeScript / Tailwind CSS frontend scaffold with Lucide icons.
- Designed dashboard landing UI adhering to design tokens (light theme, observability SaaS styling).
- Verified backend health endpoint, database connection, Redis connection, and frontend production build.

## Phase 1: Real Website Monitoring Engine
- Implemented full SQLAlchemy 2 logical schema models (`monitors`, `monitor_rules`, `check_runs`, `versions`, `notification_channels`, `notification_outbox`) in `app/models/models.py`.
- Generated and applied initial Alembic migration `dd33de50a3fb_create_initial_schema.py`.
- Built strict SSRF defense service (`app/services/security.py`) enforcing DNS resolution verification, private CIDR filtering, allowed ports, scheme validation, and trusted test fixture boundaries.
- Built headless Playwright Chromium capture engine (`app/services/browser.py`) with subresource request interception, malicious redirect blocking, DOM content extraction, and strict resource cleanup in `finally` blocks.
- Implemented safe artifact storage service (`app/services/storage.py`) with path traversal prevention for screenshots.
- Implemented asynchronous check execution (`app/services/checker.py`) handling baseline version assignment, SHA-256 content hashing, and error classification.
- Implemented complete Monitor CRUD and checks API in `app/api/monitors.py` (`GET /api/monitors`, `POST /api/monitors`, `GET /api/monitors/{id}`, `PATCH /api/monitors/{id}`, `DELETE /api/monitors/{id}`, `POST /api/monitors/{id}/checks`, `GET /api/monitors/{id}/checks`, `GET /api/checks/{id}`, `GET /api/monitors/{id}/versions`, `GET /api/versions/{id}/screenshot`).
- Implemented deterministic local test fixture router (`app/api/fixture.py`) with configurable pricing, timestamps, error 500 simulation, anti-bot blocking simulation, and unsafe redirects.
- Built real React frontend monitoring UI:
  - `AddMonitorModal.tsx`: modal with live validation, interval/sensitivity selection, and quick test fixture preset chip.
  - `MonitorDetails.tsx`: monitor detail view with real Playwright screenshot image (`<img>`), extracted title, URL, SHA-256 hash, normalized text preview, and check execution history log.
  - Live dashboard with real metrics, search/filtering, and non-blocking "Check Now" execution with real-time polling.
- Authored automated test suite (`backend/tests/test_phase1.py`) with 12 new automated tests covering SSRF, CRUD, Playwright capture, screenshot persistence, and error classification. All 14 tests passing.
- Verified frontend production build with zero TypeScript errors.
- Captured proof screenshots for Dashboard, Monitor Details, and Add Monitor Modal in `REPORTS/screenshots/`.
