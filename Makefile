# ============================================================
# Legrand GeoAI — Makefile
# ============================================================

.PHONY: up down logs logs-backend logs-worker migrate seed pull-models shell reset-db format test build hatchet-token hatchet-token-dev hatchet-dash

# --- Démarrage & arrêt ---
up:
	docker compose up -d --build

down:
	docker compose down

restart:
	docker compose restart

build:
	docker compose build --no-cache

# --- Logs ---
logs:
	docker compose logs -f

logs-backend:
	docker compose logs -f backend hatchet-worker

logs-worker:
	docker compose logs -f hatchet-worker

logs-frontend:
	docker compose logs -f frontend

# --- Hatchet (orchestrateur) ---
# Génère un jeton de worker à coller dans .env (HATCHET_CLIENT_TOKEN).
HATCHET_TENANT ?= 707d0855-80ab-4e1f-a156-f1c4546cbf52

hatchet-token:
	docker compose exec hatchet /hatchet-admin token create \
		--config /config --tenant-id $(HATCHET_TENANT)

hatchet-token-dev:
	docker compose -f docker-compose.dev.yml exec hatchet /hatchet-admin token create \
		--config /config --tenant-id $(HATCHET_TENANT)

hatchet-dash:
	@echo "Dashboard Hatchet : http://localhost:8899"
	@echo "Identifiants par défaut : admin@example.com / Admin123!!"

# --- Base de données ---
migrate:
	docker compose exec backend alembic upgrade head

migration:
	docker compose exec backend alembic revision --autogenerate -m "$(msg)"

seed:
	docker compose exec backend python seed_admin.py

reset-db:
	docker compose down -v
	$(MAKE) up
	sleep 10
	$(MAKE) migrate
	$(MAKE) seed

# --- Ollama models ---
pull-models:
	docker compose exec ollama ollama pull qwen3:32b
	docker compose exec ollama ollama pull bge-m3
	docker compose exec ollama ollama pull qwen3-vl:8b

pull-models-light:
	docker compose exec ollama ollama pull qwen3:8b
	docker compose exec ollama ollama pull bge-m3
	docker compose exec ollama ollama pull qwen3-vl:8b

# --- Développement ---
shell:
	docker compose exec backend bash

shell-db:
	docker compose exec postgres psql -U $${POSTGRES_USER:-geoai} -d $${POSTGRES_DB:-legrand_geoai}

format:
	docker compose exec backend ruff format app/
	docker compose exec backend ruff check --fix app/

test:
	docker compose exec backend pytest -v

# --- Setup complet ---
setup: up
	@echo "⏳ Attente des services..."
	@sleep 15
	$(MAKE) migrate
	$(MAKE) seed
	$(MAKE) pull-models
	@echo ""
	@echo "✅ Legrand GeoAI est prêt !"
	@echo "🌐 Dashboard : https://localhost"
	@echo "📚 API Docs  : https://localhost/api/docs"

setup-light: up
	@echo "⏳ Attente des services..."
	@sleep 15
	$(MAKE) migrate
	$(MAKE) seed
	$(MAKE) pull-models-light
	@echo ""
	@echo "✅ Legrand GeoAI est prêt (mode léger) !"
	@echo "🌐 Dashboard : https://localhost"

# --- Status ---
status:
	docker compose ps

health:
	@curl -sk https://localhost/api/health/ready | python3 -m json.tool 2>/dev/null || echo "❌ Services non prêts"
