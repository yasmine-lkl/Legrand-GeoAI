# 🌍 Legrand GeoAI

**Agent IA interne pour la recherche documentaire en géomatique.**

100% local · 100% sécurisé 

 Pour le chiffrage d'hébergement : **[HOSTING_COST_COMPARISON_10_20_USERS.md](HOSTING_COST_COMPARISON_10_20_USERS.md)**.

---

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                         Caddy                           │
│         (Reverse Proxy + TLS interne + headers)         │
│              8090 (HTTP) · 8443 (HTTPS)                 │
├────────────────────┬────────────────────────────────────┤
│    Frontend        │           Backend                  │
│    Next.js 15      │           FastAPI                  │
│    React 19        │     ┌─────────────────┐            │
│    TanStack        │     │ Auth JWT + RBAC │            │
│    Tailwind CSS    │     │  + clés API     │            │
│                    │     └────────┬────────┘            │
│                    │     ┌────────┴────────┐            │
│                    │     │  Pipeline RAG   │            │
│                    │     │ embed → search  │            │
│                    │     │ → rerank → gate │            │
│                    │     │ → parent-doc    │            │
│                    │     │ → LLM (SSE)     │            │
│                    │     └─────────────────┘            │
├────────────────────┤                                    │
│                    │     hatchet-worker (image backend) │
│                    │     ┌─────────────────┐            │
│                    │     │  DAG Hatchet    │            │
│                    │     │   validate      │            │
│                    │     │   → parse       │            │
│                    │     │   → vectorize   │            │
│                    │     │   → finalize    │            │
│                    │     └─────────────────┘            │
├────────────────────┴────────────────────────────────────┤
│ PostgreSQL 16 │ Hatchet + PG │ ChromaDB │ Ollama (GPU)  │
│ (users, docs, │ (orchestra-  │ (vecteurs│ (LLM, embed,  │
│  chat, audit) │  tion)       │  , local)│  VLM OCR)     │
└───────────────┴──────────────┴──────────┴───────────────┘
```

**8 conteneurs** : `caddy`, `frontend`, `backend`, `hatchet-worker`, `ollama`,
`postgres`, `hatchet`, `hatchet-postgres` · **4 réseaux Docker** isolés
(`frontend_net` exposé, `backend_net` / `db_net` / `hatchet_net` internes).

> `backend` et `hatchet-worker` sont **deux conteneurs bâtis depuis la même
> image** (`./backend`). Toute modification du code `backend/` impose de
> reconstruire **les deux** (`make up` le fait).

## 🔧 Stack technique

| Composant | Choix | Détails |
|-----------|-------|---------|
| **LLM** | Qwen3 8B (défaut) / 32B | via Ollama, excellent en français. `LLM_MODEL` dans `.env` |
| **Embeddings** | BGE-M3 | via Ollama, 1024 dim, multilingue, top français |
| **Reranker** | bge-reranker-v2-m3 | CrossEncoder (sentence-transformers), **CPU**, baké dans l'image |
| **Extraction** | Docling | layout, ordre de lecture, tables TableFormer → `DoclingDocument` |
| **OCR** | EasyOCR (fr/en) + repli VLM | EasyOCR via Docling ; repli `qwen2.5vl:7b` (Ollama) sur les pages < 40 caractères extraits |
| **Découpage** | Docling HybridChunker | ~512 tokens, tokenizer BGE-M3, `contextualize()` (titres préfixés) |
| **Vector DB** | ChromaDB | `PersistentClient` embarqué, distance cosinus, 1 collection Chroma par collection métier |
| **Backend** | FastAPI | async, SQLAlchemy 2.0, Alembic, structlog (JSON) |
| **Base de données** | PostgreSQL 16 | users, collections, documents, sessions de chat, audit (RGPD) |
| **Orchestration** | Hatchet lite (self-hosted) | DAG durable, retries par étape, limites de concurrence GPU, crons, stream de progression |
| **Frontend** | Next.js 15 (standalone) | React 19, composants shadcn/ui, TanStack Query/Table, Zustand, Tailwind |
| **Auth** | JWT + clés API | 3 rôles (admin / user / viewer), refresh token, header `X-Api-Key` |
| **Proxy** | Caddy 2 | TLS interne (`tls internal`), headers de sécurité, streaming SSE |
| **Déploiement** | Docker Compose | conteneurs non-root, `no-new-privileges`, 4 réseaux isolés |

> Il n'y a **ni Redis ni Celery** : la file de messages de Hatchet est adossée à
> PostgreSQL (image `hatchet-lite`).

## 🚀 Démarrage rapide (Docker — mode recommandé)

### Prérequis

- Docker Engine ≥ 24.0 + Docker Compose v2
- GPU NVIDIA + drivers + **NVIDIA Container Toolkit** (voir `setup-gpu.sh`)
- VRAM : **8 Go minimum** (profil léger Qwen3 8B), 16–24 Go confortable,
  48 Go pour Qwen3 32B. Sans GPU : fonctionne, mais l'inférence est très lente.
- ~40 Go de disque (images Docker + modèles Ollama)

### Installation

```bash
# 1. Se placer dans le projet
cd "Legrand GeoAI"

# 2. (si besoin) activer le GPU pour Docker — installe le NVIDIA Container Toolkit
bash setup-gpu.sh

# 3. Setup interactif (crée .env, build, migrations, admin, jeton Hatchet, modèles)
chmod +x setup.sh && ./setup.sh

# --- OU manuellement ---
cp .env.example .env          # puis éditer les mots de passe / modèles
make up                       # build + démarrage des 8 conteneurs
make hatchet-token            # copier le jeton dans .env → HATCHET_CLIENT_TOKEN
make up                       # redémarre backend + worker avec le jeton
make migrate                  # migrations Alembic
make seed                     # crée l'administrateur (ADMIN_EMAIL/.env)
make pull-models-light        # Qwen3 8B + BGE-M3 + VLM  (ou make pull-models)
```

> ⏱️ Le premier `make up` est long (~15–25 min) : l'image backend **bake** les
> modèles Docling, EasyOCR, le tokenizer BGE-M3 et le reranker pour fonctionner
> **hors-ligne** (`HF_HUB_OFFLINE=1`). Le téléchargement des modèles Ollama
> ajoute 6–20 Go selon le profil.

### Accès

| Service | URL |
|---------|-----|
| **Dashboard** | https://localhost:8443 |
| **API Docs (Swagger)** | https://localhost:8443/api/docs |
| **ReDoc** | https://localhost:8443/api/redoc |
| **Health (détaillé)** | https://localhost:8443/api/health/ready |
| **Hatchet (orchestration)** | http://localhost:8899 |

> Le certificat est auto-signé (`tls internal`) : le navigateur affiche un
> avertissement, et en CLI il faut `curl -k`.
>
> Ports Caddy `8090`/`8443` choisis pour éviter tout conflit avec d'autres
> projets locaux. Repasser à `80`/`443` dans `docker-compose.yml` pour un
> déploiement dédié.

**Identifiants par défaut :** définis dans `.env` (`ADMIN_EMAIL` /
`ADMIN_PASSWORD`). `.env.example` propose `admin@legrand-geoai.local` —
**à changer avant toute mise en production.**

## 💻 Développement local (hors Docker)

Utile pour itérer sur le backend avec rechargement à chaud. L'infrastructure
(Postgres, Hatchet, Ollama) tourne en Docker, le code Python tourne en local.

### 1. Infrastructure

```bash
./start-docker.sh
# = docker compose -f docker-compose.dev.yml up -d
#   postgres :5435 · hatchet-postgres :5436 · hatchet :8888 + gRPC :7077 · ollama :11434
```

### 2. Environnement Python

```bash
# Création (une seule fois) — Python 3.12 requis
cd backend
python3.12 -m venv .venv
source .venv/bin/activate
pip install uv
uv pip install -r pyproject.toml          # stack complète (Docling, EasyOCR, torch…)
# ou, plus rapide, sans OCR lourd (le reranker ne fonctionnera pas) :
# uv pip install -r requirements-dev.txt
```

**À chaque nouveau terminal, activer l'environnement :**

```bash
source "/home/abdoul/Desktop/Projects/Legrand GeoAI/backend/.venv/bin/activate"
# ou, depuis la racine du projet :
source backend/.venv/bin/activate
```

### 3. Variables d'environnement locales

`backend/app/config.py` lit le `.env` **de la racine**, qui pointe vers les noms
d'hôtes Docker (`postgres`, `ollama`, `hatchet`) et les chemins conteneur
(`/data/...`). En local il faut donc **surcharger** ces valeurs — les variables
d'environnement du shell ont priorité sur le `.env` (Pydantic Settings) :

```bash
export POSTGRES_HOST=localhost
export POSTGRES_PORT=5435
export OLLAMA_BASE_URL=http://localhost:11434
export HATCHET_CLIENT_HOST_PORT=localhost:7077
export CHROMA_PERSIST_DIR="$PWD/backend/data/chromadb"
export UPLOAD_DIR="$PWD/backend/data/uploads"
```

Puis les migrations et l'admin :

```bash
cd backend && alembic upgrade head && python seed_admin.py
```

### 4. Lancement

```bash
./start-backend.sh    # uvicorn :8000 --reload            (active .venv lui-même)
./start-worker.sh     # worker Hatchet (ingestion)        (active .venv lui-même)
cd frontend && pnpm install && pnpm dev --port 3001

# ou tout d'un coup (logs dans /tmp/legrand-*.log) :
./start-all.sh
```

| Service (local) | URL |
|-----------------|-----|
| Backend | http://localhost:8000 · docs `/api/docs` |
| Frontend | http://localhost:3001 |
| Hatchet | http://localhost:8888 |

> En dev, `frontend/next.config.js` proxifie `/api/*` vers
> `http://localhost:8000`. En production c'est **Caddy** qui route `/api/*`.
> Dans les deux cas, **les appels front doivent rester relatifs** (`/api/...`) —
> une URL absolue casse le chat (« Failed to fetch »).

### 5. Test end-to-end rapide

```bash
source backend/.venv/bin/activate
pip install requests
python test_rag.py     # login → 1re collection → requête RAG en SSE
```

En Docker (TLS auto-signé → `-k`) :

```bash
TOKEN=$(curl -sk -X POST https://localhost:8443/api/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"email":"admin@legrand-geoai.fr","password":"Admin123!"}' | jq -r .access_token)

curl -sk -N -X POST https://localhost:8443/api/chat/query \
  -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
  -d '{"message":"Quelle est la procédure ?","collection_id":"<uuid>"}'
```

## 🪓 Hatchet — orchestration du pipeline

Hatchet est **responsable de tout le cycle de vie d'un document** : dès
l'upload, le backend déclenche le workflow `document-ingestion` (DAG durable)
au lieu d'un simple job de file d'attente.

**Pipeline (DAG) — `backend/app/hatchet/workflows.py` :**

```
validate ──► parse ──────────────────► vectorize_store ──► finalize
  60 s        30 min                       10 min            30 s
  retry 1     retry 2                      retry 3           —
              concurrence « parse » ≤ 2    concurrence « ollama » ≤ 2
                 │                          + rate limit embeddings
                 ├─ Docling : layout + tables + OCR EasyOCR
                 ├─ repli VLM (qwen2.5vl) sur les pages pauvres en texte
                 └─ HybridChunker (~512 tokens, tokenizer BGE-M3)
```

**Apports performance / résilience :**
- **Retries par étape** : un échec d'embedding ne relance pas l'extraction ;
  reprise au dernier point validé.
- **Backpressure GPU** : clés de concurrence globales (parsing ≤ 2, Ollama ≤ 2)
  + rate limit sur les appels d'embedding → le GPU ne sature jamais.
- **Idempotence** : `vectorize_store` purge les chunks du document avant
  réécriture → retries et ré-indexation sans doublon.
- **Temps réel** : la progression est streamée jusqu'à l'UI
  (`GET /api/documents/{id}/progress`, SSE) **et** persistée en base
  (`status`, `sub_status`, `progress`) pour survivre à un rechargement de page.
- **Échec propre** : `on_failure_task` écrit le message d'erreur sur le document.
- **Maintenance automatique** : cron `*/15 * * * *` relance les documents
  bloqués en `processing` > 20 min ; cron `0 3 * * *` purge les documents
  `failed` de plus de 7 jours (fichier + chunks + ligne BDD).
- **Ré-indexation** : workflow `reindex-collection` (fan-out par document).

>  Le repli VLM n'est **pas** un fan-out Hatchet par page : il est exécuté
> *dans* la tâche `parse`, page par page, borné par le sémaphore
> `VLM_CONCURRENCY` (=1 sur GPU 8 Go — voir *Réglages GPU* plus bas).

**Dashboard d'observabilité :** http://localhost:8899
Login initial : `admin@example.com` / `Admin123!!` (**à changer en production**).

**Jeton worker :** généré automatiquement par `setup.sh` au 1er démarrage.
Pour (re)générer manuellement :

```bash
make hatchet-token       # prod  → affiche un jeton ; coller dans .env
make hatchet-token-dev   # dev   → idem sur docker-compose.dev.yml
make up                  # redémarre backend + hatchet-worker
```

**Ré-indexer une collection** (après changement de modèle ou de chunking) :

```bash
curl -sk -X POST https://localhost:8443/api/collections/<uuid>/reindex \
  -H "Authorization: Bearer <admin_token>"
```

> Il n'existe **pas** d'endpoint de ré-ingestion d'un document seul : pour
> re-traiter un fichier, le supprimer puis le ré-uploader (ou ré-indexer la
> collection entière).

## 🔌 API

Base : `/api` — documentation interactive sur `/api/docs`.

| Groupe | Endpoints |
|--------|-----------|
| **Santé** | `GET /api/health` · `/health/live` · `/health/ready` (Postgres, Hatchet, Ollama, ChromaDB) |
| **Auth** | `POST /api/auth/login` · `/register` · `/refresh` · `GET /api/auth/me` |
| **Utilisateurs** | `GET/POST /api/users` · `GET/PATCH/DELETE /api/users/{id}` (admin) |
| **Collections** | `GET/POST /api/collections` · `GET/PATCH/DELETE /api/collections/{id}` · `POST /api/collections/{id}/reindex` |
| **Documents** | `POST /api/documents` (multipart `file` + `collection_id`) · `GET /api/documents` · `GET /api/documents/{id}` · `GET /api/documents/{id}/progress` (SSE) · `DELETE /api/documents/{id}` |
| **Chat** | `POST /api/chat/query` (SSE) · `GET /api/chat/sessions` · `GET/DELETE /api/chat/sessions/{id}` |
| **Clés API** | `GET/POST /api/api-keys` · `DELETE /api/api-keys/{id}` (révocation) · `DELETE /api/api-keys/{id}/permanent` |

**Authentification** : `Authorization: Bearer <access_token>` **ou**
`X-Api-Key: <clé>` (utile pour l'intégration machine-à-machine).

**Formats acceptés à l'upload** : PDF, PNG, JPEG, TIFF, BMP, WEBP —
`MAX_UPLOAD_SIZE_MB=50` par défaut.

**Événements SSE de `POST /api/chat/query`** :

```
event: sources → data: {"sources":[{filename, page_numbers, score, ...}]}
event: token   → data: {"content":"..."}          (token par token)
event: done    → data: {"tokens_used":N,"session_id":"..."}
event: error   → data: {"detail":"..."}
: keepalive                                        (toutes les 5 s)
```

Le battement `: keepalive` est indispensable : le reranking CPU retarde le
premier token de plusieurs secondes et un navigateur/proxy fermerait une
connexion restée inactive.

##  Réglages RAG (`.env`)

La stratégie de récupération est **générique** (aucune règle par document) :

```
embed question
  → recherche vectorielle top RAG_N_RETRIEVE
  → reranking CrossEncoder top RAG_N_RERANK
  → gate de pertinence   (score ≥ top − RERANK_SCORE_GAP ET ≥ RERANK_SCORE_FLOOR)
  → sélection de document(s)  (≤ MAX_SELECTED_DOCS, à DOC_SELECT_MARGIN du meilleur)
  → expansion « parent-document » (TOUT le document, dans l'ordre de lecture)
  → plafond MAX_CONTEXT_CHUNKS → prompt → LLM (SSE)
```

| Variable | Défaut | Effet |
|----------|--------|-------|
| `RAG_N_RETRIEVE` | `16` | profondeur vectorielle. **Principal levier de latence** : le reranker CPU coûte ~0,75 s/candidat |
| `RAG_N_RERANK` | `10` | passages conservés après reranking |
| `RERANK_SCORE_GAP` | `0.15` | écart de score toléré sous le meilleur passage |
| `RERANK_SCORE_FLOOR` | `0.02` | plancher absolu de pertinence |
| `DOC_SELECT_MARGIN` | `0.10` | marge de sélection multi-documents |
| `MAX_SELECTED_DOCS` | `3` | nombre max de documents injectés |
| `MAX_DOC_CHUNKS` | `16` | au-delà, on retombe sur passages retenus + voisins |
| `NEIGHBOR_WINDOW` | `2` | taille de la fenêtre de voisinage (repli) |
| `MAX_CONTEXT_CHUNKS` | `16` | plafond total de passages dans le prompt |
| `LLM_NUM_CTX` | `12288` | fenêtre de contexte Ollama. **Trop petite = prompt tronqué silencieusement** (étapes perdues) |
| `LLM_MAX_TOKENS` | `1536` | budget de génération (tokens de sortie) |

Journaux à surveiller : `rag_doc_selection`, `rag_parent_expansion`
(`make logs-backend`).

## 🖥️ Réglages GPU / OCR (`.env`)

Mesuré sur **RTX 4060 Laptop 8 Go** :

| Variable | Valeur | Pourquoi |
|----------|--------|----------|
| `VLM_MODEL` | `qwen2.5vl:7b` | ~5,5 Go de VRAM en pic, ~120 s/page. `qwen2.5vl:3b` = ~90 s/page si la qualité suffit |
| `VLM_CONCURRENCY` | `1` | le VLM est **limité par le calcul**, pas par la VRAM : paralléliser dépasse le timeout de 300 s et perd des pages |
| `OLLAMA_NUM_PARALLEL` | `1` | idem, côté serveur Ollama (`docker-compose.yml`) |
| `VLM_MIN_CHARS_PER_PAGE` | `40` | seuil d'escalade vers le VLM |
| `OLLAMA_KV_CACHE_TYPE` | `q8_0` | cache KV quantifié : ~2× moins de VRAM → permet `num_ctx=12288` sur 8 Go |
| `OLLAMA_FLASH_ATTENTION` | `1` | attention plus rapide et moins gourmande |
| `OLLAMA_KEEP_ALIVE` | `30m` | garde le modèle en VRAM entre deux documents |

**Testé et écarté** : `qwen3-vl:8b` (~10 Go → débordement CPU, ~5 min/page,
timeouts) ; `OLLAMA_NUM_PARALLEL=2` avec le 7B (dépasse la VRAM) ;
`qwen2.5vl:3b` à concurrence 3 (~50 % de pages perdues).
**Sur 8 Go, augmenter le parallélisme ne fait que perdre des pages.**

##  Structure du projet

```
Legrand GeoAI/
├── backend/
│   ├── app/
│   │   ├── config.py                 # Pydantic Settings (lit ../.env)
│   │   ├── database.py               # engine async SQLAlchemy
│   │   ├── dependencies.py           # get_current_user (JWT ou X-Api-Key)
│   │   ├── main.py                   # application FastAPI
│   │   ├── middleware.py             # rate limiting mémoire + headers sécurité
│   │   ├── models/                   # user, collection, document, chat, api_key, audit
│   │   ├── routes/                   # health, auth, users, collections, documents, chat, api_keys
│   │   ├── schemas/                  # schémas Pydantic (I/O)
│   │   ├── security/                 # jwt.py, passwords.py, rbac.py
│   │   ├── services/
│   │   │   ├── prompts/              # prompts système français
│   │   │   ├── docling_extraction.py # Docling + repli VLM (Ollama)
│   │   │   ├── docling_chunking.py   # HybridChunker + chunks VLM par page
│   │   │   ├── document_storage.py   # validation MIME/taille, écriture disque
│   │   │   ├── embedding_service.py  # BGE-M3 via Ollama (batch + retry)
│   │   │   ├── vector_store.py       # ChromaDB (CRUD + parent-document)
│   │   │   ├── reranker_service.py   # CrossEncoder (thread, CPU)
│   │   │   ├── llm_service.py        # Ollama chat + streaming
│   │   │   ├── rag_service.py        # gate → sélection → expansion → prompt
│   │   │   ├── chat_service.py       # sessions & messages
│   │   │   ├── user_service.py
│   │   │   └── audit_service.py      # journal RGPD
│   │   └── hatchet/                  # client.py, workflows.py (DAG), worker.py
│   ├── alembic/versions/             # 001_initial, 002_document_progress
│   ├── seed_admin.py
│   ├── pyproject.toml                # dépendances de référence
│   ├── requirements-dev.txt          # variante légère (sans OCR lourd)
│   └── Dockerfile                    # bake Docling/EasyOCR/BGE-M3/reranker
├── frontend/
│   ├── src/
│   │   ├── app/
│   │   │   ├── page.tsx              # login
│   │   │   └── dashboard/            # chat, collections, documents, users, stats, api, settings
│   │   ├── components/               # dashboard/, ui/ (shadcn-style)
│   │   ├── lib/                      # api.ts (fetch + refresh JWT), types.ts
│   │   └── stores/                   # auth-store.ts, chat-store.ts (Zustand)
│   ├── next.config.js                # standalone + proxy /api en dev
│   └── Dockerfile                    # build pnpm → runtime standalone non-root
├── docker-compose.yml                # stack complète (production locale)
├── docker-compose.dev.yml            # infra seule (Postgres, Hatchet, Ollama)
├── Caddyfile                         # TLS interne, headers, routage /api + SSE
├── Makefile                          # raccourcis d'exploitation
├── setup.sh · setup-gpu.sh           # installation ; activation GPU Docker
├── start-*.sh · test-backend.sh      # lancement en dev local
├── test_rag.py                       # test end-to-end du chat (SSE)
├── PRESENTATION_TECHNIQUE.md         # dossier technique / support de présentation
└── HOSTING_COST_COMPARISON_10_20_USERS.md
```

##  Sécurité

- **Données** : 100% on-premise. Aucun appel sortant à l'exécution — les modèles
  d'extraction et le reranker sont bakés dans l'image et forcés hors-ligne
  (`HF_HUB_OFFLINE=1`, `TRANSFORMERS_OFFLINE=1`) ; le LLM tourne dans Ollama.
- **Réseau** : 4 réseaux Docker, dont 3 `internal: true` (aucune route vers
  l'extérieur). Seul `caddy` publie des ports.
- **Auth** : JWT (access 30 min / refresh 7 j) + RBAC 3 niveaux
  (admin / user / viewer) ; clés API hachées en SHA-256, révocables, avec
  expiration et `last_used_at`.
- **Mots de passe** : bcrypt (passlib).
- **Proxy** : Caddy — TLS interne, HSTS, `X-Frame-Options: DENY`, `nosniff`,
  `Referrer-Policy`, `Permissions-Policy`, suppression de l'en-tête `Server`.
- **Rate limiting** : middleware FastAPI en mémoire (120 req/min, burst 20 ;
  les `/api/health` sont exemptés).
- **Audit RGPD** : `audit_logs` (qui, quoi, quand, sur quelle ressource, IP) —
  login, upload, suppression, requête de chat.
- **Docker** : utilisateurs non-root dans les images backend et frontend,
  `no-new-privileges: true`, limites mémoire par service.

**À durcir avant production** (voir aussi PRESENTATION_TECHNIQUE.md § Limites) :
`CORS allow_origins=["*"]` dans `main.py` → restreindre au domaine Caddy ;
changer tous les secrets de `.env.example` et les identifiants du dashboard
Hatchet ; `SERVER_AUTH_COOKIE_SECRETS` de `docker-compose.yml` est en clair ;
le rate limiting mémoire ne survit pas à un redémarrage et n'est pas partagé
entre workers uvicorn.

##  Commandes Make

```bash
# --- Cycle de vie ---
make up                 # build + démarrer tous les services
make down               # arrêter
make restart            # redémarrer
make build              # rebuild sans cache

# --- Logs ---
make logs               # tous les services
make logs-backend       # backend + worker
make logs-worker        # worker d'ingestion Hatchet
make logs-frontend

# --- Hatchet ---
make hatchet-token      # jeton worker (prod)   → .env HATCHET_CLIENT_TOKEN
make hatchet-token-dev  # jeton worker (dev)
make hatchet-dash       # rappelle l'URL + les identifiants du dashboard

# --- Base de données ---
make migrate                    # alembic upgrade head
make migration msg="ma_migration"   # alembic revision --autogenerate
make seed                       # créer l'administrateur
make shell-db                   # psql
make reset-db                   # ⚠ down -v + up + migrate + seed (perte de données)

# --- Modèles Ollama ---
make pull-models        # qwen3:32b + bge-m3 + qwen3-vl:8b
make pull-models-light  # qwen3:8b  + bge-m3 + qwen3-vl:8b

# --- Setup complet ---
make setup / make setup-light   # up + migrate + seed + pull-models[-light]

# --- Exploitation ---
make status             # état des conteneurs
make health             # health check de l'API
make shell              # bash dans le conteneur backend
make format             # ruff format + ruff check --fix
make test               # pytest  ⚠ aucune suite de tests n'existe encore
```

> `make pull-models*` télécharge `qwen3-vl:8b`, alors que le `.env` utilise
> `qwen2.5vl:7b` (le 8B ne tient pas sur 8 Go). Adapter le Makefile ou tirer le
> modèle voulu à la main :
> `docker compose exec ollama ollama pull qwen2.5vl:7b`.

## Dépannage

| Symptôme | Cause probable | Correctif |
|----------|----------------|-----------|
| Chat : « Désolé, une erreur est survenue » | premier token trop lent → le navigateur a coupé le SSE | baisser `RAG_N_RETRIEVE` ; vérifier que le battement `: keepalive` sort bien ; regarder la latence avant d'incriminer une erreur backend |
| Chat en 500 avant même le LLM | reranker absent / non chargé | vérifier `reranker_loaded` dans les logs ; le modèle doit être baké dans l'image (rebuild) |
| Front : « Failed to fetch » | appel API en URL absolue | tous les appels doivent être relatifs (`/api/...`) |
| Upload accepté mais document bloqué en `pending` | jeton Hatchet absent/expiré | `make hatchet-token` → coller dans `.env` → `make up` ; vérifier `make logs-worker` |
| Réponse qui saute des étapes d'une procédure | `LLM_NUM_CTX` trop petit (troncature silencieuse) ou document non sélectionné | augmenter `LLM_NUM_CTX` ; inspecter `rag_doc_selection` / `rag_parent_expansion` |
| Pages OCR manquantes sur un PDF scanné | parallélisme VLM trop élevé | `VLM_CONCURRENCY=1` **et** `OLLAMA_NUM_PARALLEL=1` |
| Ollama tourne en CPU | NVIDIA Container Toolkit absent | `bash setup-gpu.sh`, puis `docker compose up -d ollama` |
| Modifications backend sans effet sur l'ingestion | seul `backend` a été rebuild | `make up` (reconstruit aussi `hatchet-worker`) |
| `/api/health/ready` en 503 | un service dépendant est en erreur | la réponse détaille `postgres` / `hatchet` / `ollama` / `chromadb` |

---

*Legrand GeoAI — Développé pour une utilisation 100% interne et sécurisée.*
