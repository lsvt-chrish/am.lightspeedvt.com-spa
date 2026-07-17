# AM Lightspeed VT - Docker commands
# Usage: make [target]
# Dev: make dev (DB only) or make up-dev (full stack with hot reload). Prod: make prod-up.

COMPOSE_DEV := -f docker-compose.yml -f docker-compose.dev.yml
COMPOSE_PROD := -f docker-compose.yml -f docker-compose.prod.yml --env-file .env.prod

.PHONY: help build build-no-cache up up-build down restart logs ps health shell-backend shell-frontend shell-db clean
.PHONY: dev up-dev up-dev-build prod-up prod-down deploy pull-prod-container down-volumes migrate

# Default target
help:
	@echo "AM Lightspeed VT - Available targets:"
	@echo ""
	@echo "  Development (local):"
	@echo "  make dev            - Start only DB (run backend/frontend locally with hot reload)"
	@echo "  make up-dev         - Full stack with backend hot reload (dev overrides)"
	@echo "  make up-dev-build   - Same as up-dev, rebuild images"
	@echo "  make build          - Build all images (default compose)"
	@echo "  make up             - Start all containers (default compose)"
	@echo "  make down           - Stop and remove containers"
	@echo "  make down-volumes   - Down and remove volumes (dev only)"
	@echo "  make restart        - Restart all containers"
	@echo ""
	@echo "  Production (images built and pushed to GHCR by GitHub Actions):"
	@echo "  make pull-prod-container - Pull latest images from registry and restart prod stack"
	@echo "  make prod-up        - Start prod stack from existing local images (.env.prod required)"
	@echo "  make prod-down      - Stop prod stack"
	@echo "  make deploy         - Alias for pull-prod-container"
	@echo ""
	@echo "  Common:"
	@echo "  make logs           - Follow logs from all services"
	@echo "  make logs-backend   - Backend logs only (and logs-frontend, logs-db)"
	@echo "  make ps             - Show container status"
	@echo "  make health         - Show health status of all containers"
	@echo "  make shell-backend  - Open shell in backend container"
	@echo "  make shell-frontend - Open shell in frontend container"
	@echo "  make shell-db        - Open psql in database container"
	@echo "  make migrate        - Run Alembic migrations against the running db"
	@echo "  make clean          - Remove containers, volumes, images (dev only)"

# Build all images
build:
	docker compose build

# Build without cache
build-no-cache:
	docker compose build --no-cache

# Start all services (detached)
up:
	docker compose up -d

# Start and build if needed
up-build:
	docker compose up -d --build

# Development: start only DB (run backend/frontend on host with hot reload)
dev:
	docker compose up -d db

# Development: full stack with backend volume mount and --reload
up-dev:
	docker compose $(COMPOSE_DEV) up -d

up-dev-build:
	docker compose $(COMPOSE_DEV) up -d --build

# Production: start with prod overrides (requires .env.prod from .env.example)
prod-up:
	docker compose $(COMPOSE_PROD) up -d

prod-down:
	docker compose $(COMPOSE_PROD) down

deploy: pull-prod-container

# Pull the newest published images from the registry and restart the prod stack
pull-prod-container:
	docker compose $(COMPOSE_PROD) pull
	docker compose $(COMPOSE_PROD) up -d

# Stop and remove containers, networks
down:
	docker compose down

# Down and remove volumes
down-volumes:
	docker compose down -v

# Restart all services
restart: down up

# Follow logs (all services)
logs:
	docker compose logs -f

# Logs for a specific service: make logs-backend, make logs-frontend, make logs-db
logs-backend:
	docker compose logs -f backend

logs-frontend:
	docker compose logs -f frontend

logs-db:
	docker compose logs -f db

# List running containers and status
ps:
	docker compose ps -a

# Show health status (requires containers to be running)
# Override with BACKEND_URL, FRONTEND_URL if you changed ports via .env
BACKEND_URL ?= http://localhost:8001
FRONTEND_URL ?= http://localhost:80
health:
	@echo "=== Backend (curl /health) ==="
	@curl -sf $(BACKEND_URL)/health && echo " OK" || echo " FAIL"
	@echo "=== Frontend (curl /health) ==="
	@curl -sf $(FRONTEND_URL)/health && echo " OK" || echo " FAIL"
	@echo "=== Database (pg_isready) ==="
	@docker compose exec -T db pg_isready -U $${POSTGRES_USER:-app} -d $${POSTGRES_DB:-appdb} && echo " OK" || echo " FAIL"

# Run Alembic migrations against the running db, from inside the backend container
migrate:
	docker compose exec backend uv run alembic upgrade head

# Shell into backend container
shell-backend:
	docker compose exec backend /bin/sh

# Shell into frontend container
shell-frontend:
	docker compose exec frontend /bin/sh

# Open psql in database container
shell-db:
	docker compose exec db psql -U app -d appdb

# Remove containers, volumes, and built images
clean: down
	docker compose down -v
	docker compose rm -f 2>/dev/null || true
	docker images 'am-lightspeedvt*' -q | xargs -r docker rmi -f 2>/dev/null || true
	@echo "Clean complete."
