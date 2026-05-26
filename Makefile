.PHONY: up down build logs restart clean setup dev

# Start all services
up:
	docker-compose up -d

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
