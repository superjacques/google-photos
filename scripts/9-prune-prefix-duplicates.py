#!/usr/bin/env python3
import argparse
import csv
from collections import defaultdict
from pathlib import Path

BASE = Path("/home/jacques/backups-4TB/Photos")
TARGET = BASE / "4.compressed"
REPORT = BASE / "reports" / "prefix-duplicate-prune.csv"

MEDIA_EXTS = {".jpg", ".jpeg", ".png", ".gif", ".heic", ".heif", ".mp4", ".mov", ".3gp", ".m4v"}

def scan_folder(folder, chars, apply):
    files = [x for x in folder.iterdir() if x.is_file() and x.suffix.lower() in MEDIA_EXTS]
    by_prefix_ext = defaultdict(list)

    for f in files:
        if len(f.stem) >= chars:
            key = (f.stem[:chars], f.suffix.lower())
            by_prefix_ext[key].append(f)

    rows = []
    delete_count = 0
    delete_bytes = 0

    for (prefix, ext), group in sorted(by_prefix_ext.items()):
        keepers = sorted(f for f in group if len(f.stem) == chars)

        if not keepers:
            continue

        keeper = keepers[0]

        for f in sorted(group):
            if f == keeper:
                continue

            # User rule:
            # keeper has exactly n stem chars, meaning filename char n+1 is the dot.
            # duplicate has the same first n chars, same extension, and a longer stem.
            if len(f.stem) <= chars:
                continue

            duplicate_bytes = f.stat().st_size
            action = "delete" if apply else "would-delete"

            rows.append({
                "action": action,
                "year": folder.name,
                "chars": chars,
                "prefix": prefix,
                "extension": ext,
                "keeper": str(keeper),
                "duplicate": str(f),
                "duplicate_bytes": duplicate_bytes,
            })

            delete_count += 1
            delete_bytes += duplicate_bytes

            if apply:
                f.unlink()

    return rows, delete_count, delete_bytes

def main():
    p = argparse.ArgumentParser(description="Prune generated prefix duplicates.")
    p.add_argument("--year", help="Single year folder, e.g. 2006")
    p.add_argument("--all-years", action="store_true", help="Scan every folder under 4.compressed")
    p.add_argument("--chars", nargs="+", type=int, default=[9], help="Prefix lengths to compare")
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
            "action", "year", "chars", "prefix", "extension",
            "keeper", "duplicate", "duplicate_bytes"
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
