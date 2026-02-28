#!/usr/bin/env bash
# HydroMAS deployment script — OpenClaw server deployment
# 用法: ./deploy.sh [dev|prod|test]
set -euo pipefail

MODE="${1:-dev}"
PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$PROJECT_DIR"

echo "=== HydroMAS Deployment — mode: $MODE ==="

# ---------- Preflight checks ----------

check_dep() {
    if ! command -v "$1" &>/dev/null; then
        echo "ERROR: $1 is not installed"
        exit 1
    fi
}

check_dep python3
check_dep pip

# ---------- Environment ----------

if [ ! -f .env ] && [ -f .env.example ]; then
    echo "WARN: .env not found, copying from .env.example"
    cp .env.example .env
    echo "  → Please edit .env with actual credentials before running in prod"
fi

if [ -f .env ]; then
    set -a
    source .env
    set +a
fi

# ---------- Install ----------

echo ""
echo "--- Installing dependencies ---"
case "$MODE" in
    dev)
        pip install -e ".[dev,web,alumina]" --quiet
        ;;
    prod)
        pip install -e ".[web,alumina]" --quiet
        ;;
    test)
        pip install -e ".[dev,web,alumina]" --quiet
        ;;
    docker)
        check_dep docker
        check_dep docker-compose
        echo "--- Building Docker image ---"
        docker-compose build
        echo "--- Starting services ---"
        docker-compose up -d
        echo ""
        echo "Services started. Check with: docker-compose ps"
        echo "  HydroMAS:  http://localhost:8000"
        echo "  Neo4j:     http://localhost:7474"
        echo "  TDengine:  http://localhost:6041"
        exit 0
        ;;
    *)
        echo "Usage: ./deploy.sh [dev|prod|test|docker]"
        exit 1
        ;;
esac

# ---------- Test (dev/test mode) ----------

if [ "$MODE" = "test" ] || [ "$MODE" = "dev" ]; then
    echo ""
    echo "--- Running tests ---"
    python -m pytest tests/ -q --tb=short
    echo ""
fi

# ---------- Start server ----------

if [ "$MODE" = "prod" ]; then
    echo ""
    echo "--- Starting production server ---"
    ENV=production exec uvicorn web.app:app \
        --host 0.0.0.0 \
        --port "${PORT:-8000}" \
        --workers "${WORKERS:-2}" \
        --log-level info
else
    echo ""
    echo "--- Starting development server ---"
    exec uvicorn web.app:app \
        --host 0.0.0.0 \
        --port "${PORT:-8000}" \
        --reload \
        --log-level debug
fi
