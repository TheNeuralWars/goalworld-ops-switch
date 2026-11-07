#!/usr/bin/env bash
set -euo pipefail
cd /workspace/flip-the-switch/goalworld-ops-switch
source .venv/bin/activate
python -m agents.runner --mode live --api http://127.0.0.1:18000
