#!/bin/bash
cd "$(dirname "$0")/backend"
source .venv/bin/activate

# Kill any existing process on port 8000
lsof -ti:8000 | xargs kill -9 2>/dev/null
sleep 1

# Start uvicorn in background
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload &
BACKEND_PID=$!

# Wait for startup
sleep 5

# Test health
echo "=== HEALTH CHECK ==="
curl -s http://localhost:8000/api/health/
echo ""
echo "=== TEST LOGIN ==="
curl -s -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=admin@legrand-geoai.local&password=Admin123!"
echo ""
echo "=== DONE ==="
echo "Backend PID: $BACKEND_PID"
