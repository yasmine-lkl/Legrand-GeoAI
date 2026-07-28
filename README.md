# 🌍 Legrand GeoAI

**Agent IA interne pour la recherche documentaire.**

100% local · 100% sécurisé · 100% français

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────┐
│                         Caddy                           │
│              (Reverse Proxy + Auto-TLS)                 │
├────────────────────┬────────────────────────────────────┤
│    Frontend        │           Backend                  │
│    Next.js 15      │           FastAPI                  │
│    shadcn/ui       │     ┌─────────────────┐            │
│    TanStack        │     │   Auth (JWT)    │            │
│    Tailwind CSS    │     │   RBAC 3 rôles  │            │
│                    │     └────────┬────────┘            │
│                    │     ┌────────┴────────┐            │
│                    │     │   RAG Pipeline  │            │
│                    │     │  Embed → Search │            │
│                    │     │  Rerank → LLM   │            │
│                    │     └────────┬────────┘            │
├────────────────────┤     ┌────────┴────────┐            │
│                    │     │   Hatchet DAG   │            │
│                    │     │  validate→OCR   │            │
│                    │     │  (fan-out/page) │            │
│                    │     │  →chunk→embed   │            │
│                    │     │  →store→done    │            │
│                    │     └─────────────────┘            │
├────────────────────┴────────────────────────────────────┤
│  PostgreSQL 16 │ Hatchet+PG │ ChromaDB │ Ollama         │
│  (Users, Docs) │ (orchestr.)│ (Vectors)│ (LLM/Embed)    │
└────────────────┴────────────┴──────────┴────────────────┘
```

## 🔧 Stack technique

| Composant | Choix | Détails |
|-----------|-------|---------|
| **LLM** | Qwen3 32B | via Ollama, excellent en français |
| **Embeddings** | BGE-M3 | Dense + sparse + ColBERT, top français |
| **Reranker** | bge-reranker-v2-m3 | CrossEncoder pour la précision |
| **Extraction** | Docling | Parsing structuré (layout, ordre de lecture, tables TableFormer) → Markdown + HybridChunker |
| **OCR** | EasyOCR (fr) + Qwen3-VL | EasyOCR pour les scans ; repli Qwen3-VL (via Ollama) sur les pages difficiles (plans denses) |
| **RAG** | LangChain | Intégration native Ollama |
| **Vector DB** | ChromaDB | PersistentClient, cosine distance |
| **Backend** | FastAPI | Async, SQLAlchemy 2.0, Alembic |
| **Base de données** | PostgreSQL 16 | Users, documents, audit (RGPD) |
| **Orchestration** | Hatchet (self-hosted) | Pipeline documentaire 100% en DAG durable : fan-out OCR par page, retries par étape, limites de concurrence GPU/Ollama, crons, ré-indexation, observabilité |
| **Frontend** | Next.js 15 | shadcn/ui, TanStack, Tailwind CSS |
| **Auth** | JWT | 3 rôles : admin / user / viewer |
| **Proxy** | Caddy | Auto-TLS, headers sécurité |
| **Déploiement** | Docker Compose | Rootless, 3 réseaux isolés |

## 🚀 Démarrage rapide

### Prérequis

- Docker Engine ≥ 24.0 + Docker Compose v2
- GPU NVIDIA avec drivers + NVIDIA Container Toolkit (recommandé)
- 48 Go VRAM pour Qwen3 32B (ou 16 Go pour Qwen3 8B)

### Installation

```bash
# 1. Cloner le projet
cd "Legrand GeoAI"

# 2. Lancer le setup interactif
chmod +x setup.sh && ./setup.sh

# OU manuellement :
cp .env.example .env
# Éditer .env avec vos paramètres

# 3. Démarrer les services
make up

# 4. Appliquer les migrations
make migrate

# 5. Créer l'admin
make seed

# 6. Télécharger les modèles IA
make pull-models       # Full (Qwen3 32B + BGE-M3)
# ou
make pull-models-light # Light (Qwen3 8B + BGE-M3)
```

### Accès

| Service | URL |
|---------|-----|
| **Dashboard** | https://localhost:8443 |
| **API Docs** | https://localhost:8443/api/docs |
| **Health** | https://localhost:8443/api/health/ready |
| **Hatchet (orchestration)** | http://localhost:8899 |

> Ports Caddy : `8090` (HTTP) / `8443` (HTTPS), choisis pour éviter tout conflit
> avec d'autres projets locaux. Repassez à `80`/`443` dans `docker-compose.yml`
> pour un déploiement dédié.

**Identifiants par défaut :**
- Email : `admin@legrand-geoai.local`
- Mot de passe : (défini dans `.env`)

## 🪓 Hatchet — orchestration du pipeline

Hatchet est **100% responsable** du cycle de vie d'un document : dès l'upload,
le backend déclenche le workflow `document-ingestion` (DAG durable) au lieu d'un
simple job de file d'attente.

**Pipeline (DAG) :**

```
validate → extract → chunk → vectorize_store → finalize
              │
              └─ PDF scanné : fan-out OCR parallèle, 1 tâche « ocr-page » / page
```

**Apports performance / résilience :**
- **Parallélisme OCR** : chaque page d'un PDF scanné est OCRisée en parallèle, avec retry indépendant.
- **Retries par étape** : un échec d'embedding ne relance pas l'OCR ; reprise au dernier point validé.
- **Backpressure GPU** : clés de concurrence (OCR ≤ 2, Ollama ≤ 2) + rate limit d'embedding.
- **Idempotence** : `vectorize_store` purge puis réécrit les chunks → retries & ré-indexation sans doublon.
- **Temps réel** : progression streamée jusqu'à l'UI (SSE) — barre de progression par document.
- **Maintenance** : crons (relance des ingestions bloquées, purge des échecs anciens) + ré-indexation de collection.

**Dashboard d'observabilité :** `http://localhost:8899`.
Login initial : `admin@example.com` / `Admin123!!` (à changer en production).

**Jeton worker :** généré automatiquement par `setup.sh` au 1er démarrage.
Pour (re)générer manuellement :

```bash
make hatchet-token      # affiche un jeton ; copier dans .env -> HATCHET_CLIENT_TOKEN
make up                 # redémarre backend + hatchet-worker
```

**Ré-indexer une collection** (après changement de modèle/chunking) :

```bash
curl -X POST https://localhost/api/collections/<id>/reindex \
  -H "Authorization: Bearer <admin_token>"
```

## 📁 Structure du projet

```
Legrand GeoAI/
├── backend/
│   ├── app/
│   │   ├── config.py           # Configuration Pydantic Settings
│   │   ├── database.py         # Engine async SQLAlchemy
│   │   ├── dependencies.py     # Auth dependencies
│   │   ├── main.py             # FastAPI application
│   │   ├── middleware.py        # Rate limiting, security headers
│   │   ├── models/             # SQLAlchemy models
│   │   ├── routes/             # API endpoints
│   │   ├── schemas/            # Pydantic schemas
│   │   ├── security/           # JWT, passwords, RBAC
│   │   ├── services/           # Business logic
│   │   │   ├── prompts/        # System prompts français
│   │   │   ├── ocr_service.py
│   │   │   ├── text_extraction.py
│   │   │   ├── chunking.py
│   │   │   ├── embedding_service.py
│   │   │   ├── vector_store.py
│   │   │   ├── llm_service.py
│   │   │   ├── reranker_service.py
│   │   │   ├── rag_service.py
│   │   │   └── chat_service.py
│   │   └── hatchet/            # Orchestration Hatchet (client, workflows, worker)
│   ├── alembic/                # Database migrations
│   ├── seed_admin.py
│   ├── pyproject.toml
│   └── Dockerfile
├── frontend/
│   ├── src/
│   │   ├── app/                # Next.js pages
│   │   │   ├── dashboard/      # Chat, Collections, Documents, Users, Stats, Settings
│   │   │   └── page.tsx        # Login
│   │   ├── components/         # UI components
│   │   ├── lib/                # API client, types, utils
│   │   └── stores/             # Zustand auth store
│   ├── package.json
│   └── Dockerfile
├── docker-compose.yml
├── Caddyfile
├── Makefile
├── setup.sh
└── .env.example
```

## 🔒 Sécurité

- **Réseau** : 4 réseaux Docker isolés (frontend, backend, db, hatchet)
- **Auth** : JWT avec refresh token, RBAC 3 niveaux
- **Proxy** : Caddy avec auto-TLS interne, HSTS, X-Frame-Options DENY
- **Rate limiting** : Middleware FastAPI + Caddy
- **Audit** : Journalisation RGPD de toutes les actions
- **Docker** : Conteneurs rootless, `no-new-privileges`
- **Données** : 100% on-premise, aucune donnée externalisée

## 📋 Commandes Make

```bash
make up              # Démarrer tous les services
make down            # Arrêter tous les services
make migrate         # Appliquer les migrations BDD
make seed            # Créer l'administrateur initial
make hatchet-token   # Générer le jeton worker Hatchet (→ .env)
make hatchet-dash    # Afficher l'URL + identifiants du dashboard Hatchet
make logs-worker     # Logs du worker d'ingestion Hatchet
make pull-models     # Télécharger Qwen3 32B + BGE-M3
make pull-models-light # Télécharger Qwen3 8B + BGE-M3
make status          # État des conteneurs
make health          # Health check de l'API
make shell           # Shell dans le conteneur backend
make reset-db        # ⚠ Reset complet de la BDD
make format          # Formatter le code Python
make test            # Lancer les tests
```

## 🖥️ GPU recommandé

- **NVIDIA RTX 6000 Ada** (48 Go) — Qwen3 32B Q8 + BGE-M3 + reranker
- **NVIDIA RTX 4090** (24 Go) — Qwen3 8B + BGE-M3 + reranker
- Sans GPU : fonctionne en CPU (très lent pour l'inférence)

---

*Legrand GeoAI — Développé pour une utilisation 100% interne et sécurisée.*
