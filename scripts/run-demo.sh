#!/usr/bin/env bash
set -euo pipefail
cd /workspace/flip-the-switch/goalworld-ops-switch
source .venv/bin/activate
MODE="${1:-local}"
python -m agents.runner --mode "$MODE"
