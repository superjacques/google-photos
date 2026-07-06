#!/usr/bin/env bash
set -euo pipefail

BASE="${1:-/home/jacques/backups-4TB/Photos}"
MASTER="$BASE/3.master"
OUT="$BASE/4.compressed-sample"
REPORT="$BASE/reports/compression-sample.csv"

rm -rf "$OUT"
mkdir -p "$OUT/images" "$OUT/videos" "$BASE/reports"

echo "type,original_size,compressed_size,saving_percent,original,compressed" > "$REPORT"

compress_image() {
  src="$1"
  rel="${src#$MASTER/}"
  stem="$(basename "$src")"
  name="${stem%.*}"
  dest="$OUT/images/${name}.jpg"

  ffmpeg -y -hide_banner -loglevel error \
    -i "$src" \
    -vf "scale='min(1920,iw)':-2" \
    -q:v 12 \
    "$dest"

  orig_size=$(stat -c%s "$src")
  comp_size=$(stat -c%s "$dest")
  saving=$(awk -v o="$orig_size" -v c="$comp_size" 'BEGIN { if (o>0) printf "%.1f", (1-c/o)*100; else print "0" }')

  echo "image,$orig_size,$comp_size,$saving,$rel,$dest" >> "$REPORT"
  printf "IMAGE  %.2f MB -> %.2f MB  %s\n" \
    "$(awk -v n="$orig_size" 'BEGIN{print n/1024/1024}')" \
    "$(awk -v n="$comp_size" 'BEGIN{print n/1024/1024}')" \
    "$rel"
}

compress_video() {
  src="$1"
  rel="${src#$MASTER/}"
  stem="$(basename "$src")"
  name="${stem%.*}"
  dest="$OUT/videos/${name}.mp4"

  ffmpeg -y -hide_banner -loglevel error \
    -i "$src" \
    -vf "scale='if(gt(iw,ih),min(1280,iw),-2)':'if(gt(iw,ih),-2,min(1280,ih))'" \
    -c:v libx264 -preset medium -crf 30 \
    -c:a aac -b:a 96k \
    -movflags +faststart \
    "$dest"

  orig_size=$(stat -c%s "$src")
  comp_size=$(stat -c%s "$dest")
  saving=$(awk -v o="$orig_size" -v c="$comp_size" 'BEGIN { if (o>0) printf "%.1f", (1-c/o)*100; else print "0" }')

  echo "video,$orig_size,$comp_size,$saving,$rel,$dest" >> "$REPORT"
  printf "VIDEO  %.2f MB -> %.2f MB  %s\n" \
    "$(awk -v n="$orig_size" 'BEGIN{print n/1024/1024}')" \
    "$(awk -v n="$comp_size" 'BEGIN{print n/1024/1024}')" \
    "$rel"
}

echo "===== Compressing sample images ====="
find "$MASTER" -type f \( -iname '*.jpg' -o -iname '*.jpeg' -o -iname '*.png' -o -iname '*.heic' -o -iname '*.heif' \) \
  -printf '%s\t%p\n' | sort -nr | head -10 | cut -f2- | while read -r f; do
    compress_image "$f"
  done

echo
echo "===== Compressing sample videos ====="
find "$MASTER" -type f \( -iname '*.mp4' -o -iname '*.mov' -o -iname '*.3gp' -o -iname '*.m4v' -o -iname '*.avi' -o -iname '*.mkv' \) \
  -printf '%s\t%p\n' | sort -nr | head -5 | cut -f2- | while read -r f; do
    compress_video "$f"
  done

echo
echo "Sample output:"
du -sh "$OUT"
echo
echo "Report:"
echo "$REPORT"
