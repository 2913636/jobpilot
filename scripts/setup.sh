#!/usr/bin/env bash
set -euo pipefail

echo "=== JobPilot Setup ==="

# Copy env file if not exists
if [ ! -f .env ]; then
  cp .env.example .env
  echo "[OK] .env created from .env.example"
else
  echo "[SKIP] .env already exists"
fi

# Create Docker volumes
echo "[INFO] Initializing Docker volumes..."
docker-compose up -d postgres redis elasticsearch etcd minio neo4j nats
echo "[OK] Infrastructure services starting..."

# Wait for PostgreSQL to be healthy
echo "[INFO] Waiting for PostgreSQL..."
until docker-compose exec -T postgres pg_isready -U jobpilot 2>/dev/null; do
  sleep 2
done
echo "[OK] PostgreSQL is ready"

# Wait for Elasticsearch
echo "[INFO] Waiting for Elasticsearch..."
until curl -s http://localhost:9200/_cluster/health 2>/dev/null | grep -q -E 'green|yellow'; do
  sleep 2
done
echo "[OK] Elasticsearch is ready"

# Install Python dependencies
echo "[INFO] Installing Python dependencies..."
cd backend
python -m venv .venv 2>/dev/null || true
source .venv/Scripts/activate 2>/dev/null || source .venv/bin/activate
pip install -e . 2>/dev/null || true
cd ..
echo "[OK] Python dependencies installed"

# Install frontend dependencies
echo "[INFO] Installing frontend dependencies..."
cd frontend
npm install --legacy-peer-deps 2>/dev/null || true
cd ..
echo "[OK] Frontend dependencies installed"

# Build and start remaining services
echo "[INFO] Starting all services..."
docker-compose up -d

echo ""
echo "=== Setup Complete ==="
echo "Frontend:  http://localhost:3000"
echo "Traefik:   http://localhost:8080"
echo "MinIO:     http://localhost:9001"
echo "Neo4j:     http://localhost:7474"
echo ""
echo "Run 'make status' to check all services."
