#!/usr/bin/env bash
set -e

echo "=========================================================="
echo " Starting Website Change Detector Services (Development)   "
echo "=========================================================="

# 1. Start Docker containers (PostgreSQL and Redis)
echo "[1/4] Ensuring PostgreSQL and Redis are running..."
docker compose up -d

# 2. Wait for Postgres and Redis health
echo "[2/4] Verifying backing services..."
until docker exec changedetection-postgres pg_isready -U postgres -d changedetection > /dev/null 2>&1; do
    echo "Waiting for PostgreSQL..."
    sleep 1
done
until docker exec changedetection-redis redis-cli ping > /dev/null 2>&1; do
    echo "Waiting for Redis..."
    sleep 1
done

# 3. Instructions for running application processes
echo "=========================================================="
echo "Backing services are UP and HEALTHY."
echo ""
echo "To run all components in dedicated terminal tabs:"
echo ""
echo "1. Backend API (FastAPI):"
echo "   cd backend && PYTHONPATH=. venv/bin/uvicorn app.main:app --port 8000 --reload"
echo ""
echo "2. RQ Worker (Playwright & Checks):"
echo "   cd backend && PYTHONPATH=. venv/bin/python worker.py"
echo ""
echo "3. Automatic Scheduler:"
echo "   cd backend && PYTHONPATH=. venv/bin/python scheduler.py"
echo ""
echo "4. Frontend Web App:"
echo "   cd frontend && npm run dev"
echo "=========================================================="
