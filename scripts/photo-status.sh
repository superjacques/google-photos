#!/usr/bin/env bash
set -euo pipefail

BASE="${1:-$HOME/backups-4TB/Photos}"
REPORT_DIR="$BASE/reports"
REPORT="$REPORT_DIR/status-$(date +%Y%m%d-%H%M%S).txt"

mkdir -p "$REPORT_DIR"

{
  echo "Google Photos Migration Status"
  echo "Generated: $(date)"
  echo "Base: $BASE"
  echo

  echo "===== Folder layout ====="
  if command -v tree >/dev/null 2>&1; then
    tree -d -L 7 "$BASE"
  else
    find "$BASE" -type d | sed "s|$BASE|.|" | sort
  fi
  echo

  echo "===== Top-level sizes ====="
  du -sh "$BASE"/1.zips "$BASE"/2.extracted "$BASE"/3.master "$BASE"/reports "$BASE"/scripts 2>/dev/null || true
  echo

  echo "===== ZIP files ====="
  if compgen -G "$BASE/1.zips/*.zip" >/dev/null; then
    du -h "$BASE"/1.zips/*.zip
  else
    echo "No ZIP files found yet."
  fi
  echo

  echo "===== Extracted folders ====="
  du -sh "$BASE"/2.extracted/* 2>/dev/null || echo "No extracted folders found yet."
  echo

  echo "===== Master size ====="
  du -sh "$BASE"/3.master 2>/dev/null || true
  echo

  echo "===== Media counts in extracted ====="
  find "$BASE/2.extracted" -type f 2>/dev/null | awk '
    BEGIN { IGNORECASE=1 }
    /\.(jpg|jpeg)$/ { jpg++ }
    /\.png$/ { png++ }
    /\.gif$/ { gif++ }
    /\.(heic|heif)$/ { heic++ }
    /\.(mp4|mov|avi|mkv|3gp|m4v)$/ { video++ }
    /\.json$/ { json++ }
    END {
      print "jpg/jpeg:", jpg+0
      print "png:", png+0
      print "gif:", gif+0
      print "heic/heif:", heic+0
      print "videos:", video+0
      print "json:", json+0
    }'
  echo

  echo "===== Largest files in extracted ====="
  find "$BASE/2.extracted" -type f -printf "%s\t%p\n" 2>/dev/null \
    | sort -nr \
    | head -30 \
    | awk '{ size=$1; $1=""; printf "%.2f MB%s\n", size/1024/1024, $0 }'

} | tee "$REPORT"

echo
echo "Saved report:"
echo "$REPORT"
