#!/usr/bin/env python3
import argparse
import csv
import subprocess
from collections import defaultdict
from pathlib import Path

BASE = Path("/home/jacques/backups-4TB/Photos")
TARGET = BASE / "4.compressed"
REPORT = BASE / "reports" / "prefix-duplicate-prune.csv"

MEDIA_EXTS = {".jpg", ".jpeg", ".png", ".gif", ".heic", ".heif", ".mp4", ".mov", ".3gp", ".m4v"}

def probe_dims(path):
    cmd = [
        "ffprobe", "-v", "error",
        "-select_streams", "v:0",
        "-show_entries", "stream=width,height",
        "-of", "csv=p=0:s=x",
        str(path),
    ]
    r = subprocess.run(cmd, text=True, capture_output=True)
    return r.stdout.strip()

def main():
    p = argparse.ArgumentParser(description="Prune generated suffix duplicates by filename prefix.")
    p.add_argument("--year", required=True, help="Year folder, e.g. 2006")
    p.add_argument("--chars", type=int, default=9, help="Prefix length to compare")
    p.add_argument("--apply", action="store_true", help="Actually delete duplicates")
    args = p.parse_args()

    folder = TARGET / args.year
    if not folder.is_dir():
        raise SystemExit(f"Missing folder: {folder}")

    files = [x for x in folder.iterdir() if x.is_file() and x.suffix.lower() in MEDIA_EXTS]
    by_prefix = defaultdict(list)

    for f in files:
        by_prefix[f.stem[:args.chars]].append(f)

    rows = []
    delete_count = 0
    delete_bytes = 0

    for prefix, group in sorted(by_prefix.items()):
        keeper = None

        for f in group:
            if len(f.stem) == args.chars:
                keeper = f
                break

        if not keeper:
            continue

        keeper_dims = probe_dims(keeper)

        for f in group:
            if f == keeper:
                continue

            if not f.stem.startswith(prefix + "-"):
                continue

            if f.suffix.lower() != keeper.suffix.lower():
                continue

            dims = probe_dims(f)
            if dims != keeper_dims:
                action = "skip-dimensions-differ"
            else:
                action = "delete" if args.apply else "would-delete"
                delete_count += 1
                delete_bytes += f.stat().st_size
                if args.apply:
                    f.unlink()

            rows.append({
                "action": action,
                "prefix": prefix,
                "keeper": str(keeper),
                "duplicate": str(f),
                "keeper_dims": keeper_dims,
                "duplicate_dims": dims,
                "duplicate_bytes": f.stat().st_size if f.exists() else "",
            })

    REPORT.parent.mkdir(parents=True, exist_ok=True)
    with REPORT.open("w", newline="", encoding="utf-8") as out:
        writer = csv.DictWriter(out, fieldnames=[
            "action", "prefix", "keeper", "duplicate",
            "keeper_dims", "duplicate_dims", "duplicate_bytes"
        ])
        writer.writeheader()
        writer.writerows(rows)

    print(f"Folder: {folder}")
    print(f"Mode: {'APPLY' if args.apply else 'DRY RUN'}")
    print(f"Duplicates matched: {delete_count}")
    print(f"Space removable: {delete_bytes / 1024 / 1024:.2f} MB")
    print(f"Report: {REPORT}")

if __name__ == "__main__":
    main()
