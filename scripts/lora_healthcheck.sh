#!/bin/zsh
set -euo pipefail

STATE_FILE="/tmp/lora-health.state"
LOG_FILE="/tmp/lora-health.log"

check() {
  local name="$1" url="$2"
  if curl -fsS --max-time 5 "$url" >/dev/null 2>&1; then
    print "$name=ok"
  else
    print "$name=down"
  fi
}

check_service() {
  local name="$1" label="$2"
  if launchctl print "gui/$(id -u)/$label" 2>/dev/null | /usr/bin/grep -q "state = running"; then
    print "$name=ok"
  else
    print "$name=down"
  fi
}

current="$(check ollama http://127.0.0.1:11434/api/tags)
$(check api http://127.0.0.1:8092/health)
$(check gateway http://127.0.0.1:8093/health)
$(check_service bot com.lora.v2.bot)
$(check_service worker com.lora.v2.worker)
$(check_service integrations com.lora.v2.integrations)
$(check_service obsidian com.lora.v2.obsidian-processor)
$(check bridge http://127.0.0.1:8788/health)
$(check n8n http://127.0.0.1:5678/healthz)
$(cd /Users/robu/Lora && .venv/bin/python -m lora_v2.health)"
previous="$(cat "$STATE_FILE" 2>/dev/null || true)"
timestamp="$(date '+%Y-%m-%d %H:%M:%S %z')"

if [[ "$current" != "$previous" ]]; then
  print "$timestamp $current" >> "$LOG_FILE"
  failed=$(print "$current" | awk -F= '$2 != "ok" {print $1}' | paste -sd, -)
  if [[ -n "$failed" ]]; then
    /usr/bin/osascript -e "display notification \"Servicii indisponibile: $failed\" with title \"Lora health check\"" 2>/dev/null || true
  else
    /usr/bin/osascript -e 'display notification "Toate serviciile sunt operaționale" with title "Lora health check"' 2>/dev/null || true
  fi
  print -r -- "$current" > "$STATE_FILE"
fi
