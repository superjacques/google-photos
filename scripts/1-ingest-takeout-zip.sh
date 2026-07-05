#!/usr/bin/env bash
set -euo pipefail
shopt -s nullglob

BASE="${BASE:-$HOME/backups-4TB/Photos}"
DOWNLOADS="${DOWNLOADS:-$HOME/Downloads}"
ZIP_NAME="${1:-}"
ACCOUNT_FOLDER="${2:-}"

if [ -z "$ZIP_NAME" ] || [ -z "$ACCOUNT_FOLDER" ]; then
  echo "Usage:"
  echo "  1-ingest-takeout-zip.sh <destination-zip-name> <account-folder>"
  echo
  echo "Example:"
  echo "  1-ingest-takeout-zip.sh jacquesbezuidenhout1980-02.zip jacquesbezuidenhout1980"
  exit 1
fi

DEST="$BASE/1.zips/$ZIP_NAME"
EXTRACT_DIR="$BASE/2.extracted/$ACCOUNT_FOLDER"
LOG="$BASE/reports/1-ingest-takeout-zip.log"
STATUS_SCRIPT="$BASE/scripts/photo-status.sh"
INVENTORY_SCRIPT="$BASE/scripts/2-inventory-cache.py"

{
  echo
  echo "===== $(date) START ingest ====="
  echo "Base: $BASE"
  echo "Downloads: $DOWNLOADS"
  echo "Destination ZIP: $DEST"
  echo "Extract dir: $EXTRACT_DIR"
  echo

  mkdir -p "$BASE/1.zips" "$EXTRACT_DIR" "$BASE/reports"

  zips=("$DOWNLOADS"/takeout-*.zip)

  if [ "${#zips[@]}" -ne 1 ]; then
    echo "ERROR: Expected exactly one takeout-*.zip in $DOWNLOADS, found ${#zips[@]}"
    printf 'Found: %s\n' "${zips[@]:-none}"
    exit 1
  fi

  SRC="${zips[0]}"

  echo "Source ZIP:"
  echo "$SRC"
  echo

  if [ -e "$DEST" ]; then
    echo "ERROR: Destination already exists:"
    echo "$DEST"
    echo "Refusing to overwrite."
    exit 1
  fi

  echo "Testing ZIP before moving..."
  unzip -t "$SRC" >/dev/null

  echo "Moving ZIP..."
  mv "$SRC" "$DEST"

  echo "Testing ZIP after moving..."
  unzip -t "$DEST" >/dev/null

  echo "Extracting..."
  unzip -q "$DEST" -d "$EXTRACT_DIR"

  echo
  echo "Running status..."
  if [ -x "$STATUS_SCRIPT" ]; then
    "$STATUS_SCRIPT" "$BASE"
  else
    echo "Status script not found/executable: $STATUS_SCRIPT"
  fi

  echo
  echo "Running cached inventory..."
  if [ -x "$INVENTORY_SCRIPT" ]; then
    "$INVENTORY_SCRIPT" --base "$BASE" --hash
  else
    echo "Inventory script not found/executable: $INVENTORY_SCRIPT"
  fi

  echo
  echo "Removing old one-time move-bigzip cron entry if present..."
  crontab -l 2>/dev/null | grep -v "move-bigzip.sh" | crontab - || true

  echo
  echo "Final sizes:"
  du -sh "$BASE"/1.zips "$BASE"/2.extracted "$BASE"/3.master "$BASE"/reports "$BASE"/scripts 2>/dev/null || true

  echo "===== $(date) END ingest ====="
} >> "$LOG" 2>&1

echo "Ingest complete. Log:"
echo "$LOG"
