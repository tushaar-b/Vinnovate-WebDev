#!/usr/bin/env bash
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKEND="$ROOT/backend"
failures=0

report() {
  local state="$1" name="$2" detail="${3:-}"
  printf '%-7s %s' "$state" "$name"
  [[ -z "$detail" ]] || printf ' — %s' "$detail"
  printf '\n'
  [[ "$state" != FAIL ]] || failures=$((failures + 1))
}

run_check() {
  local name="$1"; shift
  if "$@"; then report PASS "$name"; else report FAIL "$name" "exit $?"; fi
}

echo 'Website Change Detector implementation checks'
if command -v python >/dev/null; then DEFAULT_PY=python
elif command -v python3 >/dev/null; then DEFAULT_PY=python3
else DEFAULT_PY=; fi
if [[ -z "$DEFAULT_PY" ]] || ! command -v npm >/dev/null; then
  report FAIL 'Required tools (Python, npm)' 'install both and retry'
else
  report PASS 'Required tools (Python, npm)'
fi

if [[ -x "$BACKEND/.venv/bin/python" ]]; then PY="$BACKEND/.venv/bin/python"; else PY="${PYTHON:-$DEFAULT_PY}"; fi
if [[ -z "$PY" ]]; then PY=python3; fi
if "$PY" -c 'import pytest, sqlalchemy, redis, alembic' >/dev/null 2>&1; then
  report PASS 'Backend Python dependencies'
else
  report FAIL 'Backend Python dependencies' 'install backend/requirements.txt in the selected Python environment'
fi

if [[ -d "$ROOT/frontend/node_modules" ]]; then report PASS 'Frontend dependencies'; else report FAIL 'Frontend dependencies' 'run npm ci in frontend/'; fi

if [[ -d "$ROOT/frontend/node_modules" ]]; then
  (cd "$ROOT/frontend" && npm run build)
  rc=$?; [[ $rc -eq 0 ]] && report PASS 'Frontend TypeScript check and production build' || report FAIL 'Frontend TypeScript check and production build' "exit $rc"
fi

if [[ -d "$BACKEND" ]]; then
  (cd "$BACKEND" && PYTHONPATH="$BACKEND" "$PY" -m pytest -q)
  rc=$?; [[ $rc -eq 0 ]] && report PASS 'Complete backend pytest suite' || report FAIL 'Complete backend pytest suite' "exit $rc"
  (cd "$BACKEND" && PYTHONPATH="$BACKEND" "$PY" -m pytest -q tests/test_phase1.py tests/test_phase2.py tests/test_phase5.py -k 'security or ssrf or credential or encryption or webhook or secret or redirect or unsafe')
  rc=$?; [[ $rc -eq 0 ]] && report PASS 'Essential security regression tests' || report FAIL 'Essential security regression tests' "exit $rc"
fi

if [[ -z "${DATABASE_URL:-}" ]]; then
  report SKIPPED 'PostgreSQL connectivity and Alembic state' 'DATABASE_URL is unset'
else
  (cd "$BACKEND" && PYTHONPATH="$BACKEND" "$PY" -c 'from app.database import check_database_connection; raise SystemExit(0 if check_database_connection() else 1)')
  rc=$?; [[ $rc -eq 0 ]] && report PASS 'PostgreSQL connectivity' || report FAIL 'PostgreSQL connectivity' "exit $rc"
  (cd "$BACKEND" && PYTHONPATH="$BACKEND" "$PY" -m alembic current)
  rc=$?; [[ $rc -eq 0 ]] && report PASS 'Alembic migration state' || report FAIL 'Alembic migration state' "exit $rc"
fi
if [[ -z "${REDIS_URL:-}" ]]; then
  report SKIPPED 'Redis connectivity and RQ queue availability' 'REDIS_URL is unset'
else
  (cd "$BACKEND" && PYTHONPATH="$BACKEND" "$PY" -c 'from app.redis_client import check_redis_connection; raise SystemExit(0 if check_redis_connection() else 1)')
  rc=$?; [[ $rc -eq 0 ]] && report PASS 'Redis connectivity' && report PASS 'RQ queue availability (Redis reachable)' || report FAIL 'Redis connectivity and RQ queue availability' "exit $rc"
fi

if [[ -n "${BACKEND_URL:-}" ]]; then
  "$PY" -c 'import os,urllib.request; u=os.environ["BACKEND_URL"].rstrip("/")+"/api/health"; r=urllib.request.urlopen(u,timeout=5); raise SystemExit(0 if r.status==200 else 1)'
  rc=$?; [[ $rc -eq 0 ]] && report PASS 'FastAPI health endpoint' || report FAIL 'FastAPI health endpoint' "exit $rc"
else report SKIPPED 'FastAPI health endpoint' 'set BACKEND_URL to a running API'; fi

for proc in worker scheduler; do
  if pgrep -af "python.*${proc}\.py" >/dev/null 2>&1; then report PASS "$proc process readiness"; else report SKIPPED "$proc process readiness" 'process not observable in this shell'; fi
done

echo "Failures: $failures"
(( failures == 0 ))
