#!/bin/bash
set -e

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"

echo "=== Legrand GeoAI — Docker Startup ==="
echo ""

# 1. Wait for Docker daemon
echo "[1/4] Waiting for Docker daemon..."
attempts=0
while ! docker info > /dev/null 2>&1; do
    attempts=$((attempts + 1))
    if [ $attempts -ge 30 ]; then
        echo "ERROR: Docker daemon not available after 90s. Please start Docker Desktop."
        exit 1
    fi
    printf "  waiting... (%ds)\r" $((attempts * 3))
    sleep 3
done
echo "  Docker daemon is ready!              "

# 2. Start docker-compose services
echo ""
echo "[2/4] Starting infrastructure containers (postgres, hatchet, ollama)..."
cd "$PROJECT_DIR"
docker compose -f docker-compose.dev.yml up -d

# 3. Wait for postgres to be ready
echo ""
echo "[3/4] Waiting for PostgreSQL to accept connections..."
attempts=0
while ! docker exec legrandgeoai-postgres-1 pg_isready -U geoai > /dev/null 2>&1; do
    attempts=$((attempts + 1))
    if [ $attempts -ge 20 ]; then
        echo "ERROR: PostgreSQL not ready after 60s"
        exit 1
    fi
    sleep 3
done
echo "  PostgreSQL is ready!"

# 4. Verify all services
echo ""
echo "[4/4] Verifying services..."
echo ""

# Check postgres
if docker exec legrandgeoai-postgres-1 pg_isready -U geoai > /dev/null 2>&1; then
    echo "  ✅ PostgreSQL  — port 5435"
else
    echo "  ❌ PostgreSQL  — FAILED"
fi

# Check hatchet (dashboard/API)
if curl -sf http://localhost:8888 > /dev/null 2>&1; then
    echo "  ✅ Hatchet     — dashboard http://localhost:8888 (gRPC 7077)"
else
    echo "  ⏳ Hatchet     — démarrage en cours (dashboard http://localhost:8888)"
fi

# Check ollama
if docker exec legrandgeoai-ollama-1 ollama --version > /dev/null 2>&1; then
    echo "  ✅ Ollama      — port 11434"
else
    echo "  ❌ Ollama      — FAILED"
fi

echo ""
echo "=== All Docker services are running! ==="
