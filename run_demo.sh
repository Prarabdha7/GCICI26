#!/usr/bin/env bash
# One-click demo launcher: seeds data, starts the auto-publisher worker in the
# background, then runs the FastAPI server in the foreground.
#
#   bash run_demo.sh
#
# Ctrl+C stops the server; the trap below stops the worker with it.
set -euo pipefail
cd "$(dirname "$0")"

if [ -f "venv/bin/activate" ]; then
    # shellcheck disable=SC1091
    source venv/bin/activate
fi

echo "==> Seeding demo data (safe to re-run — skips tables that already have rows)..."
python -m scripts.seed_demo

echo "==> Starting the auto-publisher worker in the background..."
python -m worker.scheduler &
WORKER_PID=$!

cleanup() {
    echo ""
    echo "==> Stopping the auto-publisher worker (pid ${WORKER_PID})..."
    kill "${WORKER_PID}" 2>/dev/null || true
}
trap cleanup EXIT INT TERM

echo ""
echo "════════════════════════════════════════════════════════════"
echo "  🚀 DEMO LIVE: Open http://localhost:8000/dashboard in your browser!"
echo "════════════════════════════════════════════════════════════"
echo ""

uvicorn app.main:app --host 0.0.0.0 --port 8000
