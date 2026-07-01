#!/bin/bash
set -e
cd "$(dirname "$0")"

PYTHON="python3"
if [ -f ".venv/bin/python" ]; then
    PYTHON=".venv/bin/python"
fi

PORT="${1:-8088}"

# Kill anything on that port
kill $(lsof -ti:$PORT) 2>/dev/null || true
sleep 1

# Auto-build dashboard if dist is missing
if [ ! -f "dashboard/dist/index.html" ]; then
  echo "📦 Building dashboard..."
  cd dashboard && npx vite build && cd ..
fi

echo "🚀 Starting Lora API on port $PORT (background)..."
echo "   Kiosk: http://$(ifconfig | grep "inet " | grep -v 127.0.0.1 | awk '{print $2; exit}'):$PORT/kiosk"
echo ""

# Run in background, log to api.log
export API_PORT=$PORT
nohup $PYTHON -m lora_api.main > api.log 2>&1 &

PID=$!
echo "   PID: $PID"
echo "   Logs: tail -f api.log"
echo ""
echo "   To stop: kill $PID"
