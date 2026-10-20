#!/bin/zsh
set -euo pipefail
PROJECT_DIR="/Users/robu/Lora"
cd "$PROJECT_DIR"
exec "$PROJECT_DIR/.venv/bin/python" -m lora_v2.backup
