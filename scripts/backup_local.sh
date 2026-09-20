#!/bin/zsh
set -euo pipefail

PROJECT_DIR="/Users/robu/Lora"
BACKUP_DIR="$PROJECT_DIR/backups"
RETENTION_DAYS="${LORA_BACKUP_RETENTION_DAYS:-30}"

if [[ -f "$PROJECT_DIR/.env" ]]; then
  set -a
  source "$PROJECT_DIR/.env"
  set +a
fi

if [[ -z "${DATABASE_URL:-}" ]]; then
  print -u2 "DATABASE_URL is not configured"
  exit 1
fi

mkdir -p "$BACKUP_DIR"
timestamp=$(date +%Y%m%d_%H%M%S)
target="$BACKUP_DIR/lora_${timestamp}.dump"
temporary="$target.tmp"

cleanup() { rm -f "$temporary"; }
trap cleanup EXIT

/opt/homebrew/bin/pg_dump "$DATABASE_URL" \
  --format=custom --no-owner --no-acl --file="$temporary"

test -s "$temporary"
mv "$temporary" "$target"

find "$BACKUP_DIR" -type f -name 'lora_*.dump' -mtime "+$RETENTION_DAYS" -delete
print "Backup created: $target"
