# Website Change Detector

> Autonomous, precise website monitoring with headless Chromium captures, normalized content hashing, and visual difference inspection.

---

## Live Demo

- **Live Website:** [https://vinnovate-web-dev.vercel.app](https://vinnovate-web-dev.vercel.app/)
- **GitHub Repository:** [https://github.com/tushaar-b/Vinnovate-WebDev](https://github.com/tushaar-b/Vinnovate-WebDev)
- **Backend API:** [https://vinnovate-webdev-production.up.railway.app](https://vinnovate-webdev-production.up.railway.app/)

### Interactive Evaluation (No Login Required)
When you open the live deployed website, select **Explore Judge Workspace** on the entry screen. This creates a secure, temporary anonymous evaluation session instantly. You can enter any publicly reachable website URL (such as `https://example.com`), trigger **Check Now**, view the live headless browser snapshot, observe baseline generation, inspect captured screenshots, and test visual/text comparison features without needing an admin password or account.

---

## Project Overview

Modern websites update continuously, making manual verification tedious, unreliable, and noisy. Generic uptime checkers only track whether a web server returns HTTP 200, missing subtle content changes, visual regressions, broken pricing, or layout shifts.

Website Change Detector solves this by combining headless browser rendering with robust content normalization and versioned visual diffing. Rather than naively diffing volatile HTML markup or script telemetry, it captures the rendered DOM, strips ephemeral scripts and dynamic noise, computes cryptographic SHA-256 hashes of visible human-readable text, and tracks visual changes across historical checkpoints.

### Key Differentiators
- **Meaningful rendered webpage text extraction:** Traverses the rendered DOM in Playwright to extract visible human-facing text rather than raw HTML markup.
- **Dynamic script and tracking noise exclusion:** Automatically ignores ephemeral JavaScript variables, telemetry tokens, ad trackers, and dynamic timestamps.
- **SHA-256 change detection:** Computes cryptographic hashes over normalized content to reliably determine whether a change occurred.
- **Real browser snapshots:** Captures genuine full-viewport screenshots using headless Chromium.
- **Historical version comparison:** Maintains sequential snapshot checkpoints with side-by-side text diffing.
- **Visual difference inspection:** Generates visual difference overlays highlighting pixel modifications.
- **Region-specific monitoring rules:** Supports custom CSS `WATCH` and `IGNORE` rules with an interactive region picker.
- **Background scheduled checks:** Periodically evaluates targets through an asynchronous Redis RQ worker queue.
- **Isolated public evaluation workspace:** Provides evaluator access through short-lived, quota-managed sessions without exposing administrative privileges.
- **Reliable screenshot persistence across distributed services:** Stores captured screenshot bytes directly in PostgreSQL `VersionArtifact` rows, ensuring immediate screenshot availability across separated API and Worker instances.

---

## Key Features

- **Autonomous Website Monitoring:** Periodic polling of HTTP/HTTPS websites with configurable check intervals.
- **Visual & Text Diffs:** Compare version histories through colored word-level additions/deletions and visual overlay diffs.
- **Interactive Region Picker:** Visually select DOM elements to monitor or suppress without manually writing CSS selectors.
- **Activity Feed & Audit Trail:** Chronological log of all check runs, duration timings, HTTP status codes, and detected changes.
- **Encrypted Notification Channels:** Production credentials for Discord Webhooks, Telegram Bots, and SMTP Email encrypted at rest with Fernet.
- **SSRF & Abuse Protection:** Server-enforced host validation rejecting private subnets, loopbacks, cloud metadata (169.254.169.254), and unsafe ports.

---

## Technology Stack

- **Frontend:** React 18, TypeScript, Vite, Tailwind CSS, Lucide Icons.
- **Backend:** FastAPI (Python 3.12), SQLAlchemy, Alembic, Playwright Chromium.
- **Infrastructure:** Railway (FastAPI, Worker, Scheduler), Vercel (SPA Frontend), PostgreSQL, Redis + RQ.

---

## Architecture

```
                                  +-----------------------------+
                                  |   React + Vite Frontend     |
                                  |     (Hosted on Vercel)      |
                                  +--------------+--------------+
                                                 |
                                                 | HTTPS / REST (Bearer Auth)
                                                 v
                                  +-----------------------------+
                                  |     FastAPI Backend API     |
                                  |    (Hosted on Railway)      |
                                  +-------+--------------+------+
                                          |              |
                      Enqueues Check Job  |              | Reads / Writes Metadata
                                          v              v
+------------------+             +--------+---+    +-----+--------------------+
| Railway Cron     | Polls Due   |   Redis    |    |   PostgreSQL Database    |
| Scheduler        |------------>|  RQ Queue  |    | - Monitors & Check Runs  |
+------------------+             +--------+---+    | - Versions & Diffs       |
                                          |        | - VersionArtifact Images |
                      Dequeues Job        |        | - Encrypted Configs      |
                                          v        +-----+--------------------+
                                 +--------+------+       ^
                                 |  RQ Worker    |       | Persists Screenshots
                                 |  (Playwright) |-------+ & Extracted Hashes
                                 +---------------+
```

### Component Roles & Artifact Persistence
1. **Frontend:** Single-page application built with React and Vite. Interfaces with the FastAPI backend using scoped Bearer authentication (Admin or Judge).
2. **FastAPI:** Handles request routing, session validation, SSRF checks, quota enforcement, and comparison endpoints.
3. **PostgreSQL & VersionArtifact:** Stores application state. Captured screenshot binaries are saved into `VersionArtifact` database records, allowing the API and Worker to share binary images across isolated container filesystems.
4. **Redis & RQ Worker:** Decouples heavy browser execution. The worker executes Playwright headless Chromium, takes screenshots, extracts text, and evaluates SHA-256 hash deltas.
5. **Scheduler:** Runs continuously to trigger background checks for active monitors whose scheduled interval has elapsed, and disables expired judge monitors.

---

## Local Setup

### Prerequisites
- Python 3.12+
- Node.js 18+ and npm
- Docker and Docker Compose (for local PostgreSQL and Redis)

### Step-by-Step Installation

1. **Clone the repository:**
   ```bash
   git clone https://github.com/tushaar-b/Vinnovate-WebDev.git
   cd Vinnovate-WebDev
   ```

2. **Configure environment variables:**
   ```bash
   cp .env.example backend/.env
   ```

3. **Generate a Fernet encryption key:**
   ```bash
   python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
   ```
   Paste the generated string into `backend/.env` as `ENCRYPTION_KEY`.

4. **Start local PostgreSQL and Redis:**
   ```bash
   docker compose up -d postgres redis
   ```

5. **Create and activate a Python virtual environment:**
   ```bash
   # macOS / Linux
   python3 -m venv backend/venv
   source backend/venv/bin/activate

   # Windows
   python -m venv backend\venv
   backend\venv\Scripts\activate
   ```

6. **Install backend dependencies and Playwright Chromium:**
   ```bash
   pip install -r backend/requirements.txt
   playwright install chromium
   ```

7. **Run database migrations:**
   ```bash
   cd backend
   PYTHONPATH=. alembic upgrade head
   cd ..
   ```

8. **Install frontend dependencies:**
   ```bash
   cd frontend
   npm install
   cd ..
   ```

### Running Services Locally

Start each component in a separate terminal:

- **Terminal 1: FastAPI API Server**
  ```bash
  cd backend
  PYTHONPATH=. ./venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
  ```

- **Terminal 2: RQ Worker (Playwright)**
  ```bash
  cd backend
  PYTHONPATH=. ./venv/bin/python worker.py
  ```

- **Terminal 3: Scheduler**
  ```bash
  cd backend
  PYTHONPATH=. ./venv/bin/python scheduler.py
  ```

- **Terminal 4: Frontend Development Server**
  ```bash
  cd frontend
  npm run dev
  ```

Open `http://localhost:5173` in your browser.

---

## Usage

### 1. Judge Workspace (Public & Evaluator Access)
- Click **Explore Judge Workspace** on the landing page.
- An anonymous, scoped evaluation session is automatically initialized.
- Enter a public URL (e.g. `https://example.com`) and click **Add Website**.
- Click **Check Now** to trigger an on-demand Playwright capture.
- Monitor state transitions:
  - `BASELINE`: First snapshot captured. Serves as the comparison reference.
  - `UNCHANGED`: Content hash matches the previous version.
  - `CHANGED`: Visible rendered content differs from the previous snapshot.
- Open **Compare Versions** to inspect word additions, deletions, and visual image diffs.
- Configure CSS selectors under **Region Rules & Picker** to focus on or ignore specific DOM nodes.
- Quotas: Maximum 2 monitors per session, minimum 15-minute background interval, maximum 3 manual checks per hour.

### 2. Admin Login (Privileged Operations)
- Click **Sign In as Admin** on the landing page.
- Enter the administrative password (configured via `ADMIN_PASSWORD`).
- Access global system monitors, notification channel settings (Discord, Telegram, SMTP), and unconstrained monitoring parameters.

---

## Verification

The repository includes comprehensive automated verification suites.

### Full Test Suite & Build Verification
Run the verification shell script:
```bash
./scripts/test_implementation.sh
```
This script executes:
- Python and npm dependency validation.
- Frontend TypeScript type checking and Vite production build.
- Judge workspace isolation and quota tests (`tests/test_judge_workspace.py`).
- Essential security regression tests (`tests/test_production_access.py`, `tests/test_phase1.py`, SSRF tests).
- Visible text extraction and noise filtering tests (`tests/test_visible_content_extraction.py`).
- PostgreSQL and Redis connectivity checks.

### Live Production Smoke Test
Verify read-only endpoints and judge isolation against live or local deployments:
```bash
python3 scripts/smoke_test.py --frontend-url https://vinnovate-web-dev.vercel.app --backend-url https://vinnovate-webdev-production.up.railway.app
```

---

## Deployment

The application is deployed as distributed cloud services:

- **Frontend (Vercel):**
  - Continuous deployment connected to the `main` branch.
  - Output directory: `frontend/dist`.
  - Rewrite rules in `frontend/vercel.json` route all SPA navigation paths back to `index.html`.
  - Configured with `VITE_API_URL` pointing to the Railway API domain.

- **Backend (Railway):**
  - **API Service:** Runs `uvicorn app.main:app` with production CORS and Fernet key validation.
  - **Worker Service:** Runs `python worker.py` with Playwright Chromium for website rendering.
  - **Scheduler Service:** Runs `python scheduler.py` to trigger background intervals.
  - **Managed PostgreSQL & Redis:** Persistent database storage for relational metadata and VersionArtifact images.

---

## Limitations

- **Dynamic & Personalized Websites:** Sites requiring user authentication, CAPTCHA solvers, or exhibiting personalized location feeds may produce layout variations between runs.
- **Automation Defenses:** Websites employing strict bot detection (e.g., Cloudflare Under Attack mode) may block headless Chromium requests. In such cases, the system reports a descriptive capture failure rather than simulating success.
- **Canvas & Closed Shadow DOM:** Text drawn directly to an HTML `<canvas>` or encapsulated inside closed shadow roots cannot be extracted by standard DOM text traversal.
- **Judge Session Rate Limits:** Anonymous evaluation sessions are capped at 2 monitors and 3 manual checks per monitor per hour to prevent resource exhaustion of shared browser instances.
- **Screenshot Storage Growth:** Persistent full-page screenshots are stored in PostgreSQL. Long-running production instances monitoring hundreds of pages require regular retention pruning.
- **Sequential Change Observation:** Detecting a change requires at least two distinct captures where the source website content actually changes. First captures are always registered as `BASELINE`.
