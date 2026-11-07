#!/usr/bin/env bash
set -euo pipefail
export PATH="/home/box/.local/bin:$PATH"
export DOCKER_HOST="${DOCKER_HOST:-tcp://127.0.0.1:2375}"
ROOT=/workspace/flip-the-switch/goalworld-ops-switch
cd "$ROOT"
source .venv/bin/activate

EV="$ROOT/evidence"
mkdir -p "$EV"
SMOKE="$EV/SMOKE.md"
{
  echo "# Smoke — GoalWorld Ops Switch"
  echo
  echo "Generated: $(date '+%Y-%m-%d %H:%M %Z') (Europe/Rome box clock)"
  echo
  echo "## Switch health"
  echo '```'
  curl -sS http://127.0.0.1:18000/health
  echo
  echo '```'
  echo "## Gateway"
  echo "HTTP $(curl -sS -o /dev/null -w '%{http_code}' http://127.0.0.1:13000/)"
  echo "## Mattermost"
  echo "HTTP $(curl -sS -o /dev/null -w '%{http_code}' http://127.0.0.1:18065/)"
  echo "## Containers"
  echo '```'
  docker ps --filter name=gw-switch --format '{{.Names}} {{.Status}}'
  echo '```'
} > "$SMOKE"

pytest -q | tee "$EV/pytest.txt"
python -m agents.runner --mode local | tee "$EV/demo-local.txt"
python -m agents.runner --mode live --api http://127.0.0.1:18000 | tee "$EV/demo-live.txt"

# preview server smoke
python demo/server.py >/tmp/gw-preview.log 2>&1 &
PID=$!
sleep 1
CODE=$(curl -sS -o /tmp/gw-preview.html -w '%{http_code}' http://127.0.0.1:18765/ || true)
API=$(curl -sS http://127.0.0.1:18765/api/transcript | head -c 200 || true)
kill $PID 2>/dev/null || true
{
  echo
  echo "## Preview"
  echo "GET / → HTTP $CODE"
  echo "API snippet: \`$API\`"
  echo
  echo "## Notes"
  echo "- Secrets redacted; agent keys only in .secrets/ (gitignored)"
  echo "- Side effects: dry-run only"
  echo "- REVIEW: pending (October)"
} >> "$SMOKE"
echo "SMOKE written to $SMOKE"
