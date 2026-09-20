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

current="$(check ollama http://127.0.0.1:11434/api/tags)
$(check api http://127.0.0.1:8090/api/health)
$(check bot http://127.0.0.1:8083/health)"
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
