#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
VAULT="${OBSIDIAN_VAULT_PATH:-$ROOT/obsidian}"
BACKUP_DIR="${OBSIDIAN_BACKUP_DIR:-$ROOT/backups/obsidian}"
STAMP="$(date +%Y%m%d-%H%M%S)"

if [[ ! -d "$VAULT" ]]; then
  echo "Vault-ul Obsidian nu există: $VAULT" >&2
  exit 1
fi
mkdir -p "$BACKUP_DIR"
ARCHIVE="$BACKUP_DIR/obsidian-$STAMP.tar.gz.enc"
VAULT_PARENT="$(cd "$(dirname "$VAULT")" && pwd)"
VAULT_NAME="$(basename "$VAULT")"

printf "Parola pentru backup-ul criptat: " >&2
read -r -s PASSWORD
printf "\n" >&2
if [[ -z "$PASSWORD" ]]; then
  echo "Parola nu poate fi goală." >&2
  exit 1
fi

tar -C "$VAULT_PARENT" \
  --exclude="$VAULT_NAME/.obsidian/workspace.json" \
  --exclude="$VAULT_NAME/.obsidian/workspace-mobile.json" \
  --exclude="$VAULT_NAME/.trash" \
  --exclude="$VAULT_NAME/.lora" \
  -czf - "$VAULT_NAME" \
  | openssl enc -aes-256-cbc -pbkdf2 -salt -pass "pass:$PASSWORD" -out "$ARCHIVE"
chmod 600 "$ARCHIVE"
echo "Backup criptat creat: $ARCHIVE"
