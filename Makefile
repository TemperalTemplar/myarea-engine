# MyArea — Developer Makefile
# Usage: make <target>

.PHONY: help up down build logs shell db-init db-seed db-migrate fake-players

help:
	@echo ""
	@echo "  MyArea Game Engine — Dev Commands"
	@echo "  ──────────────────────────────────"
	@echo "  make up           Start all containers"
	@echo "  make down         Stop all containers"
	@echo "  make build        Rebuild Docker images"
	@echo "  make logs         Tail all container logs"
	@echo "  make shell        Open shell in web container"
	@echo "  make db-init      Create DB tables + run migrations"
	@echo "  make db-seed      Seed jobs, properties, items"
	@echo "  make db-migrate   Generate + apply new migration"
	@echo "  make fake-players Generate 50 fake players (dev)"
	@echo "  make admin        Create admin user (prompts)"
	@echo ""

up:
	docker compose up -d
	@echo "✅ MyArea is running → http://localhost"

down:
	docker compose down

build:
	docker compose build --no-cache

logs:
	docker compose logs -f

shell:
	docker compose exec web bash

db-init:
	docker compose exec web flask db upgrade
	@echo "✅ Migrations applied"

db-seed:
	docker compose exec web flask seed-db
	@echo "✅ Database seeded"

db-migrate:
	@read -p "Migration message: " msg; \
	docker compose exec web flask db migrate -m "$$msg"
	docker compose exec web flask db upgrade

fake-players:
	docker compose exec web flask gen-fake-players --count 50

admin:
	docker compose exec web flask create-admin

# ─── Cross-app ────────────────────────────────────────────────
shared-network:
	@docker network inspect myarea_shared_net > /dev/null 2>&1 || \
	  (docker network create myarea_shared_net && echo "✅ Shared network created")

verify-link:
	@echo "Testing connection to social app..."
	docker exec myarea_games_web curl -s \
	  -H "X-Service-Key: $$(grep SERVICE_API_KEY .env | cut -d= -f2)" \
	  http://myarea_social_web:5000/api/v1/service/user/test || \
	  echo "⚠️  Social app not reachable (is it running on shared network?)"
