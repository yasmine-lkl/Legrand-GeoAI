#!/bin/bash
# Start all Legrand GeoAI services

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"

# Kill any existing processes on our ports
lsof -ti:8000 | xargs kill -9 2>/dev/null
lsof -ti:3001 | xargs kill -9 2>/dev/null
sleep 1

# Start backend
cd "$PROJECT_DIR/backend"
source .venv/bin/activate
nohup uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload > /tmp/legrand-backend.log 2>&1 &
BACKEND_PID=$!
echo "Backend started (PID: $BACKEND_PID)"

# Wait for backend
sleep 4

# Test backend
echo "Testing backend..."
HEALTH=$(curl -s http://localhost:8000/api/health/)
echo "Health: $HEALTH"

# Start frontend
cd "$PROJECT_DIR/frontend"
nohup pnpm dev --port 3001 > /tmp/legrand-frontend.log 2>&1 &
FRONTEND_PID=$!
echo "Frontend started (PID: $FRONTEND_PID)"

# Start Hatchet worker (document ingestion)
cd "$PROJECT_DIR/backend"
nohup python -m app.hatchet.worker > /tmp/legrand-worker.log 2>&1 &
WORKER_PID=$!
echo "Worker started (PID: $WORKER_PID)"

sleep 5
echo ""
echo "============================================"
echo "  Legrand GeoAI is running!"
echo "  Backend:  http://localhost:8000"
echo "  Frontend: http://localhost:3001"
echo "  Worker:   PID $WORKER_PID"
echo "  API Docs: http://localhost:8000/docs"
echo "============================================"
echo ""
echo "Login credentials:"
echo "  Email:    admin@legrand-geoai.fr"
echo "  Password: Admin123!"
