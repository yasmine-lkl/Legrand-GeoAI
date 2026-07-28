#!/bin/bash
cd "$(dirname "$0")/backend"
source .venv/bin/activate
exec python -m app.hatchet.worker
