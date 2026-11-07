#!/usr/bin/env bash
# Idempotent start of the local Switch stack used by GoalWorld Ops.
set -euo pipefail
export PATH="/home/box/.local/bin:$PATH"
export DOCKER_HOST="${DOCKER_HOST:-tcp://127.0.0.1:2375}"
ROOT="/workspace/flip-the-switch/switch-upstream"
cd "$ROOT"
if [[ ! -f .env ]]; then
  cp .env.example .env
  bash deploy/local/generate-env-secrets.sh .env local
  sed -i 's/^SWITCH_VERSION=.*/SWITCH_VERSION=0.31.0/' .env
  sed -i 's/^GATEWAY_HOST_PORT=.*/GATEWAY_HOST_PORT=13000/' .env
  sed -i 's/^API_HOST_PORT=.*/API_HOST_PORT=18000/' .env
  sed -i 's/^MATTERMOST_HOST_PORT=.*/MATTERMOST_HOST_PORT=18065/' .env
  sed -i 's/^POSTGRES_HOST_PORT=.*/POSTGRES_HOST_PORT=15432/' .env
fi
COMPOSE_PROJECT_NAME=gw-switch docker compose \
  -f deploy/local/standalone-docker-compose.yml \
  --project-directory . \
  --profile collab --profile gateway up -d
echo "Waiting for health..."
for i in $(seq 1 40); do
  if curl -sf http://127.0.0.1:18000/health | grep -q ok; then
    echo "Switch API healthy on http://127.0.0.1:18000"
    exit 0
  fi
  sleep 2
done
echo "Switch did not become healthy in time" >&2
exit 1
