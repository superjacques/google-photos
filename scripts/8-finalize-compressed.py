#!/usr/bin/env python3
import csv
import hashlib
import shutil
import subprocess
from pathlib import Path

BASE = Path("/home/jacques/backups-4TB/Photos")
MASTER = BASE / "3.master"
OUT = BASE / "4.compressed"
MANIFEST = BASE / "reports" / "compressed-build-manifest.csv"
GIF_REPORT = BASE / "reports" / "compressed-gif-copy-report.csv"
VIDEO_AUDIT = BASE / "reports" / "copied-videos-over-25mb-resolution.csv"

def year_for(src):
    rel = src.relative_to(MASTER)
    first = rel.parts[0]
    return first if len(first) == 4 and first.isdigit() else "unknown-year"

def unique_dest(dest, rel):
    if not dest.exists():
        return dest
    suffix = hashlib.sha1(str(rel).encode("utf-8")).hexdigest()[:10]
    candidate = dest.with_name(f"{dest.stem}-{suffix}{dest.suffix}")
    n = 2
    while candidate.exists():
        candidate = dest.with_name(f"{dest.stem}-{suffix}-{n}{dest.suffix}")
        n += 1
    return candidate

def ffprobe(path):
    cmd = [
        "ffprobe", "-v", "error",
        "-select_streams", "v:0",
        "-show_entries", "stream=width,height,codec_name,bit_rate",
        "-of", "csv=p=0",
        str(path),
    ]
    result = subprocess.run(cmd, text=True, capture_output=True, check=False)
    return result.stdout.strip() or result.stderr.strip()

def copy_gifs():
    gifs = sorted(p for p in MASTER.rglob("*") if p.is_file() and p.suffix.lower() == ".gif")
    copied = []

    with GIF_REPORT.open("w", newline="", encoding="utf-8") as gf, MANIFEST.open("a", newline="", encoding="utf-8") as mf:
        gif_writer = csv.writer(gf)
        manifest_writer = csv.writer(mf)

        gif_writer.writerow(["source", "output", "bytes"])

        for src in gifs:
            rel = src.relative_to(MASTER)
            dest = unique_dest(OUT / year_for(src) / src.name, rel)
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dest)

            size = src.stat().st_size
            gif_writer.writerow([src, dest, size])
            manifest_writer.writerow(["copy", "gif", size, size, "0.0", src, dest])
            copied.append(dest)

    print(f"GIFs copied unchanged: {len(copied)}")
    print(f"GIF report: {GIF_REPORT}")

def audit_videos():
    rows = []
    with MANIFEST.open("r", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row.get("action") == "copy" and row.get("type") == "video":
                try:
                    out_bytes = int(row.get("output_bytes") or 0)
                except ValueError:
                    continue
                if out_bytes > 25 * 1024 * 1024:
                    path = Path(row["output"])
                    rows.append((out_bytes, path, ffprobe(path)))

    rows.sort(reverse=True, key=lambda x: x[0])

    with VIDEO_AUDIT.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["mb", "output", "ffprobe"])
        for out_bytes, path, probe in rows:
            writer.writerow([f"{out_bytes/1024/1024:.2f}", path, probe])

    print(f"Copied videos over 25 MB: {len(rows)}")
    print(f"Video audit: {VIDEO_AUDIT}")

def main():
    copy_gifs()
    audit_videos()

    master_count = sum(1 for _ in MASTER.rglob("*") if _.is_file())
    compressed_count = sum(1 for _ in OUT.rglob("*") if _.is_file())

    print()
    print(f"3.master files:     {master_count}")
    print(f"4.compressed files: {compressed_count}")
    subprocess.run(["du", "-sh", str(OUT)], check=False)

if __name__ == "__main__":
    main()
