#!/usr/bin/env bash
# Minga-Greens ERP — Production Deploy Script
# Run on VPS: ./scripts/deploy.sh
set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

COMPOSE_FILES="-f docker-compose.yml -f docker-compose.prod.yml"

echo "======================================"
echo " Minga-Greens ERP — Deploy"
echo "======================================"
echo ""

# --- Pre-flight checks ---
if ! command -v docker &>/dev/null; then
    echo -e "${RED}Docker is not installed. Install it first:${NC}"
    echo "  curl -fsSL https://get.docker.com | sh"
    exit 1
fi

if [ ! -f .env ]; then
    echo -e "${RED}.env file not found!${NC}"
    echo "Copy .env.example → .env and set real values:"
    echo "  cp .env.example .env && nano .env"
    exit 1
fi

# Source .env for validation
set -a; source .env; set +a

if [ "${POSTGRES_PASSWORD:-}" = "minga_secret_change_me" ] || [ -z "${POSTGRES_PASSWORD:-}" ]; then
    echo -e "${RED}ERROR: Set a real POSTGRES_PASSWORD in .env${NC}"
    exit 1
fi

if [ "${SECRET_KEY:-}" = "your-secret-key-change-in-production-min-32-chars" ] || [ -z "${SECRET_KEY:-}" ]; then
    echo -e "${RED}ERROR: Set a real SECRET_KEY in .env (min 32 chars)${NC}"
    exit 1
fi

if [ "${KEYCLOAK_ADMIN_PASSWORD:-}" = "admin_change_me" ] || [ -z "${KEYCLOAK_ADMIN_PASSWORD:-}" ]; then
    echo -e "${RED}ERROR: Set a real KEYCLOAK_ADMIN_PASSWORD in .env${NC}"
    exit 1
fi

if [ -z "${DOMAIN:-}" ]; then
    echo -e "${YELLOW}WARNING: DOMAIN not set in .env — Caddy will use localhost (no HTTPS)${NC}"
fi

echo -e "${GREEN}Pre-flight checks passed.${NC}"
echo ""

# --- Pull latest code ---
if [ -d .git ]; then
    echo "Pulling latest code..."
    git pull --ff-only
    echo ""
fi

# --- Build and deploy ---
echo "Building and starting containers..."
docker compose $COMPOSE_FILES up -d --build --remove-orphans

echo ""
echo "Waiting for services to be healthy..."
sleep 10

# --- Run database migrations ---
echo "Running database migrations..."
docker compose $COMPOSE_FILES exec -T backend alembic upgrade head || echo -e "${YELLOW}Migration warning — check logs${NC}"

echo ""

# --- Seed data (only if database is empty) ---
echo "Seeding initial data (if needed)..."
docker compose $COMPOSE_FILES exec -T backend python seed_data.py || echo -e "${YELLOW}Seed skipped or already done${NC}"

echo ""

# --- Health check ---
echo "Checking service health..."
SERVICES=("postgres" "redis" "backend" "frontend" "keycloak" "celery-worker" "celery-beat" "forecasting" "caddy")
for svc in "${SERVICES[@]}"; do
    STATUS=$(docker compose $COMPOSE_FILES ps --format json "$svc" 2>/dev/null | head -1 | grep -o '"State":"[^"]*"' | cut -d'"' -f4 || echo "not found")
    if [ "$STATUS" = "running" ]; then
        echo -e "  ${GREEN}✓${NC} $svc"
    else
        echo -e "  ${RED}✗${NC} $svc ($STATUS)"
    fi
done

echo ""
echo "======================================"
if [ -n "${DOMAIN:-}" ]; then
    echo -e "${GREEN}Deployed!${NC}"
    echo "  App:      https://${DOMAIN}"
    echo "  Keycloak: https://auth.${DOMAIN}"
    echo "  API Docs: https://${DOMAIN}/api/docs"
else
    echo -e "${GREEN}Deployed (local)!${NC}"
    echo "  App:      http://localhost:3002"
    echo "  Keycloak: http://localhost:8080"
    echo "  API Docs: http://localhost:8000/docs"
fi
echo "======================================"
