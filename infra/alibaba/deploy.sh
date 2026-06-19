#!/usr/bin/env bash
# Ayin — Alibaba Cloud ECS deploy (Qwen hackathon, Workstream C2/C6).
#
# Idempotent: run once to provision, re-run to update. Generates production
# secrets ON THE SERVER on first run (server-only .env, chmod 600 — never
# committed; CLAUDE.md hard rule). Expects: Ubuntu 22.04+ ECS instance,
# security group allowing 22/80/443 only.
#
# Usage:
#   PUBLIC_HOST=ayin.example.com QWEN_API_KEY=sk-... ./deploy.sh
#   (PUBLIC_HOST may be the ECS public IP while no domain exists)

set -euo pipefail
cd "$(dirname "$0")"

PUBLIC_HOST="${PUBLIC_HOST:?set PUBLIC_HOST to your domain or ECS public IP}"
ENV_FILE=".env"

# ── 1. Docker (idempotent) ───────────────────────────────────────────
if ! command -v docker >/dev/null 2>&1; then
  echo ">> installing docker"
  curl -fsSL https://get.docker.com | sh
fi

# ── 2. Server-only secrets, generated once ───────────────────────────
if [ ! -f "$ENV_FILE" ]; then
  echo ">> first run: generating production secrets into $ENV_FILE (server-only)"
  umask 177
  cat > "$ENV_FILE" <<EOF
# Generated $(date -u +%Y-%m-%dT%H:%M:%SZ) on this server. NEVER commit.
APP_SECRET=$(openssl rand -hex 32)
POSTGRES_PASSWORD=$(openssl rand -hex 24)
VAULT_MASTER_KEY=$(openssl rand -hex 32)
PUBLIC_HOST=${PUBLIC_HOST}
PUBLIC_BASE_URL=https://${PUBLIC_HOST}
WEB_BASE_URL=https://${PUBLIC_HOST}
API_BASE_URL=https://${PUBLIC_HOST}/api

# ── Qwen Cloud (the judged integration) ──────────────────────────────
LLM_ENABLED=true
QWEN_BASE_URL=${QWEN_BASE_URL:-https://dashscope-intl.aliyuncs.com/compatible-mode/v1}
QWEN_API_KEY=${QWEN_API_KEY:?pass QWEN_API_KEY on first run}
QWEN_MODEL=${QWEN_MODEL:-qwen-plus}

# ── Data sources (empty = connector disabled, scan still completes) ──
BREACH_API_KEY=${BREACH_API_KEY:-}
SEARCH_API_KEY=${SEARCH_API_KEY:-}

# ── Email (judges use the pre-seeded demo account; SMTP optional) ────
SMTP_HOST=${SMTP_HOST:-localhost}
SMTP_PORT=${SMTP_PORT:-25}
EMAIL_CONSOLE_FALLBACK=${EMAIL_CONSOLE_FALLBACK:-true}
EOF
  echo ">> secrets written (chmod 600). Back up VAULT_MASTER_KEY somewhere safe —"
  echo ">> losing it crypto-shreds every vault payload on this box."
else
  echo ">> $ENV_FILE exists — keeping existing secrets"
fi

# ── 3. Up ────────────────────────────────────────────────────────────
echo ">> starting the stack (api runs alembic upgrade head on boot)"
docker compose -f docker-compose.prod.yml --env-file "$ENV_FILE" up -d --remove-orphans

echo ">> done. verify:"
echo "   curl -s https://${PUBLIC_HOST}/api/health"
echo "   docker compose -f docker-compose.prod.yml logs -f api"
echo ">> for the Devpost proof clip (C5): show this instance in the Alibaba"
echo ">> console + the curl above succeeding, in one recording."
