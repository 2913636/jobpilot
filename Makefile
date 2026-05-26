.PHONY: up down build logs restart clean setup dev test demo lint

# Start all services
up:
	docker-compose up -d

# Start with seed data
demo:
	docker-compose up -d
	sleep 15
	python scripts/seed.py
	@echo ""
	@echo "=== JobPilot Demo Ready ==="
	@echo "Frontend: http://localhost:3000"
	@echo "API Docs: http://localhost:8001/docs"
	@echo "Jaeger:   http://localhost:16686"
	@echo ""

# Run all tests
test:
	cd backend/services/user_service && pytest tests/ -v
	cd backend/services/resume_service && pytest tests/ -v
	cd backend/services/match_service && pytest tests/ -v
	cd backend/services/apply_service && pytest tests/ -v
	cd backend/services/interview_service && pytest tests/ -v
	cd backend/services/agent_service && pytest tests/ -v

# Lint all code
lint:
	cd backend && black --check . && isort --check-only . && ruff check .
	cd frontend && npx prettier --check "src/**/*.{ts,tsx,css}" && npx tsc --noEmit

# Stop all services
down:
	docker-compose down

# Build backend services
build:
	docker-compose build

# View logs (optional: make logs svc=user-service)
logs:
	docker-compose logs -f $(svc)

# Restart a specific service
restart:
	docker-compose restart $(svc)

# Tear down and remove volumes
clean:
	docker-compose down -v

# First-time setup
setup:
	bash scripts/setup.sh

# Start in development mode with hot reload
dev:
	docker-compose -f docker-compose.yml -f docker-compose.dev.yml up -d

# Show service status
status:
	docker-compose ps

# Run database migrations
migrate:
	docker-compose exec user-service alembic upgrade head

# Tail logs for all backend services
logs-backend:
	docker-compose logs -f user-service resume-service match-service apply-service interview-service agent-service

# Enter a service shell (usage: make shell svc=user-service)
shell:
	docker-compose exec $(svc) bash
