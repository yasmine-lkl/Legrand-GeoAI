#!/usr/bin/env bash
# ============================================================
# Legrand GeoAI — Script d'installation
# ============================================================
set -euo pipefail

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}"
echo "╔══════════════════════════════════════════════════════╗"
echo "║           Legrand GeoAI — Installation              ║"
echo "║      Agent IA Interne pour la Géomatique            ║"
echo "╚══════════════════════════════════════════════════════╝"
echo -e "${NC}"

# --- Check Docker ---
if ! command -v docker &> /dev/null; then
    echo -e "${RED}❌ Docker n'est pas installé.${NC}"
    echo "   Installez Docker : https://docs.docker.com/get-docker/"
    exit 1
fi
echo -e "${GREEN}✅ Docker trouvé${NC}"

if ! command -v docker compose &> /dev/null; then
    echo -e "${RED}❌ Docker Compose n'est pas installé.${NC}"
    exit 1
fi
echo -e "${GREEN}✅ Docker Compose trouvé${NC}"

# --- Check .env ---
if [ ! -f .env ]; then
    echo -e "${YELLOW}📋 Création du fichier .env depuis .env.example...${NC}"
    cp .env.example .env
    echo -e "${YELLOW}⚠️  Modifiez les valeurs dans .env avant la mise en production !${NC}"
    echo ""
fi

# --- Validate .env ---
REQUIRED_VARS=("POSTGRES_USER" "POSTGRES_PASSWORD" "POSTGRES_DB" "JWT_SECRET_KEY" "ADMIN_EMAIL" "ADMIN_PASSWORD")
MISSING=()
for var in "${REQUIRED_VARS[@]}"; do
    if ! grep -q "^${var}=" .env; then
        MISSING+=("$var")
    fi
done

if [ ${#MISSING[@]} -gt 0 ]; then
    echo -e "${RED}❌ Variables manquantes dans .env :${NC}"
    for var in "${MISSING[@]}"; do
        echo "   - $var"
    done
    exit 1
fi
echo -e "${GREEN}✅ Fichier .env validé${NC}"

# --- Build and start ---
echo ""
echo -e "${BLUE}🚀 Construction et démarrage des services...${NC}"
make up

# --- Wait for services ---
echo ""
echo -e "${BLUE}⏳ Attente des services (30s max)...${NC}"
for i in $(seq 1 30); do
    if docker compose exec -T postgres pg_isready -U geoai -d legrand_geoai &>/dev/null; then
        echo -e "${GREEN}✅ PostgreSQL prêt${NC}"
        break
    fi
    sleep 1
done

sleep 5

# --- Hatchet : génération du jeton worker (si absent) ---
echo ""
echo -e "${BLUE}🪓 Configuration de Hatchet (orchestrateur)...${NC}"
if grep -q '^HATCHET_CLIENT_TOKEN=$' .env; then
    echo -e "${YELLOW}   Attente du moteur Hatchet...${NC}"
    for i in $(seq 1 40); do
        if docker compose exec -T hatchet /hatchet-admin --help &>/dev/null; then
            break
        fi
        sleep 3
    done
    HATCHET_TENANT="707d0855-80ab-4e1f-a156-f1c4546cbf52"
    TOKEN=$(docker compose exec -T hatchet /hatchet-admin token create \
        --config /config --tenant-id "$HATCHET_TENANT" 2>/dev/null \
        | tr -d '\r' | grep -E '^[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.' | tail -1)
    if [ -n "$TOKEN" ]; then
        # Remplace la ligne vide par le jeton généré
        sed -i.bak "s|^HATCHET_CLIENT_TOKEN=$|HATCHET_CLIENT_TOKEN=${TOKEN}|" .env && rm -f .env.bak
        echo -e "${GREEN}✅ Jeton Hatchet généré et enregistré dans .env${NC}"
        echo -e "${BLUE}   Redémarrage du backend et du worker...${NC}"
        docker compose up -d backend hatchet-worker
    else
        echo -e "${YELLOW}⚠️  Génération du jeton échouée. Lancez 'make hatchet-token' puis collez la valeur dans .env (HATCHET_CLIENT_TOKEN) et 'make up'.${NC}"
    fi
else
    echo -e "${GREEN}✅ HATCHET_CLIENT_TOKEN déjà présent${NC}"
fi

# --- Migrate ---
echo -e "${BLUE}📦 Exécution des migrations...${NC}"
make migrate
echo -e "${GREEN}✅ Migrations appliquées${NC}"

# --- Seed admin ---
echo -e "${BLUE}👤 Création de l'administrateur...${NC}"
make seed
echo -e "${GREEN}✅ Administrateur créé${NC}"

# --- Pull models ---
echo ""
echo -e "${YELLOW}🤖 Téléchargement des modèles IA...${NC}"
echo -e "${YELLOW}   Cela peut prendre 30-60 minutes selon votre connexion.${NC}"
echo ""

read -p "Voulez-vous télécharger les modèles maintenant ? (o/n) " -n 1 -r
echo
if [[ $REPLY =~ ^[Oo]$ ]]; then
    read -p "Modèle complet (32B, GPU 48GB) ou léger (8B, GPU 8GB) ? (c/l) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Cc]$ ]]; then
        make pull-models
    else
        make pull-models-light
    fi
    echo -e "${GREEN}✅ Modèles téléchargés${NC}"
else
    echo -e "${YELLOW}⚠️  Lancez 'make pull-models' ou 'make pull-models-light' plus tard.${NC}"
fi

# --- Done ---
echo ""
echo -e "${GREEN}╔══════════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║         ✅ Legrand GeoAI est prêt !                 ║${NC}"
echo -e "${GREEN}╠══════════════════════════════════════════════════════╣${NC}"
echo -e "${GREEN}║                                                      ║${NC}"
echo -e "${GREEN}║  🌐 Dashboard : https://localhost                    ║${NC}"
echo -e "${GREEN}║  📚 API Docs  : https://localhost/api/docs           ║${NC}"
echo -e "${GREEN}║  🪓 Hatchet   : http://localhost:8899                ║${NC}"
echo -e "${GREEN}║                                                      ║${NC}"
echo -e "${GREEN}║  📧 Admin     : Voir ADMIN_EMAIL dans .env           ║${NC}"
echo -e "${GREEN}║  🔑 Mot de passe : Voir ADMIN_PASSWORD dans .env     ║${NC}"
echo -e "${GREEN}║                                                      ║${NC}"
echo -e "${GREEN}╚══════════════════════════════════════════════════════╝${NC}"
