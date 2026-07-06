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

def scan_folder(folder, chars, apply):
    files = [x for x in folder.iterdir() if x.is_file() and x.suffix.lower() in MEDIA_EXTS]
    by_prefix = defaultdict(list)

    for f in files:
        if len(f.stem) >= chars:
            by_prefix[f.stem[:chars]].append(f)

    rows = []
    delete_count = 0
    delete_bytes = 0

    for prefix, group in sorted(by_prefix.items()):
        keeper = None

        for f in sorted(group):
            # Safety rule: prefix length n, then next filename character is dot.
            # Since suffix is removed in stem, this means stem length must equal n.
            if len(f.stem) == chars:
                keeper = f
                break

        if not keeper:
            continue

        keeper_dims = probe_dims(keeper)

        for f in sorted(group):
            if f == keeper:
                continue

            if not f.stem.startswith(prefix + "-"):
                continue

            if f.suffix.lower() != keeper.suffix.lower():
                continue

            dims = probe_dims(f)

            if dims != keeper_dims:
                action = "skip-dimensions-differ"
                duplicate_bytes = f.stat().st_size
            else:
                duplicate_bytes = f.stat().st_size
                action = "delete" if apply else "would-delete"
                delete_count += 1
                delete_bytes += duplicate_bytes
                if apply:
                    f.unlink()

            rows.append({
                "action": action,
                "year": folder.name,
                "chars": chars,
                "prefix": prefix,
                "keeper": str(keeper),
                "duplicate": str(f),
                "keeper_dims": keeper_dims,
                "duplicate_dims": dims,
                "duplicate_bytes": duplicate_bytes,
            })

    return rows, delete_count, delete_bytes

def main():
    p = argparse.ArgumentParser(description="Prune generated suffix duplicates by filename prefix.")
    p.add_argument("--year", help="Single year folder, e.g. 2006")
    p.add_argument("--all-years", action="store_true", help="Scan every folder under 4.compressed")
    p.add_argument("--chars", nargs="+", type=int, default=[9], help="Prefix lengths to compare, e.g. 9 15")
    p.add_argument("--apply", action="store_true", help="Actually delete duplicates")
    args = p.parse_args()

    if args.all_years:
        folders = sorted(x for x in TARGET.iterdir() if x.is_dir())
    elif args.year:
        folders = [TARGET / args.year]
    else:
        raise SystemExit("Use --year YEAR or --all-years")

    all_rows = []
    total_count = 0
    total_bytes = 0

    for folder in folders:
        if not folder.is_dir():
            continue

        for chars in args.chars:
            rows, count, bytes_removed = scan_folder(folder, chars, args.apply)
            all_rows.extend(rows)
            total_count += count
            total_bytes += bytes_removed
            print(f"{folder.name} chars={chars}: {count} matches, {bytes_removed / 1024 / 1024:.2f} MB")

    REPORT.parent.mkdir(parents=True, exist_ok=True)
    with REPORT.open("w", newline="", encoding="utf-8") as out:
        writer = csv.DictWriter(out, fieldnames=[
            "action", "year", "chars", "prefix", "keeper", "duplicate",
            "keeper_dims", "duplicate_dims", "duplicate_bytes"
        ])
        writer.writeheader()
        writer.writerows(all_rows)

    print()
    print(f"Mode: {'APPLY' if args.apply else 'DRY RUN'}")
    print(f"Total duplicates matched: {total_count}")
    print(f"Total space removable: {total_bytes / 1024 / 1024:.2f} MB")
    print(f"Report: {REPORT}")

if __name__ == "__main__":
    main()
