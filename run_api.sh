#!/bin/bash
set -e
cd "$(dirname "$0")"

# Detect Python: prefer .venv, fall back to system python3
PYTHON="python3"
if [ -f ".venv/bin/python" ]; then
    PYTHON=".venv/bin/python"
fi

# Auto-build dashboard if dist is missing
if [ ! -f "dashboard/dist/index.html" ]; then
    echo "📦 Building dashboard..."
    cd dashboard && npx vite build && cd ..
fi

echo "🚀 Starting Lora API (no LLM required)..."
exec $PYTHON -m lora_api.main "$@"
