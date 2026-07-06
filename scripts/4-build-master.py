#!/usr/bin/env python3
import argparse
import csv
import shutil
import sqlite3
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

def score(row):
    path = row["rel_path"] or ""
    score = 0
    if row["sidecar_rel_path"]:
        score += 1000
    if "/Photos from " in path:
        score += 500
    if "/Takeout/Google Photos/" in path:
        score += 100
    score -= path.count("/") * 5
    score -= len(path) / 1000
    return score

def date_folder(row):
    ts = row["photo_taken_timestamp"] or row["creation_timestamp"] or ""
    try:
        dt = datetime.fromtimestamp(int(ts), tz=timezone.utc)
        return f"{dt.year}/{dt.strftime('%Y-%m-%d')}"
    except Exception:
        return "unknown-date"

def unique_dest(master, folder, filename, sha):
    dest_dir = master / folder
    p = Path(filename)
    dest = dest_dir / filename

    if not dest.exists():
        return dest

    candidate = dest_dir / f"{p.stem}-{sha[:12]}{p.suffix}"
    if not candidate.exists():
        return candidate

    n = 2
    while True:
        candidate = dest_dir / f"{p.stem}-{sha[:12]}-{n}{p.suffix}"
        if not candidate.exists():
            return candidate
        n += 1

def main():
    parser = argparse.ArgumentParser(description="Build deduplicated master photo library.")
    parser.add_argument("--base", default=str(Path.home() / "backups-4TB" / "Photos"))
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    base = Path(args.base).expanduser().resolve()
    master = base / "3.master"
    db_path = base / "reports" / "photo-index.sqlite"
    manifest = base / "reports" / "master-build-manifest.csv"

    master.mkdir(parents=True, exist_ok=True)

    if any(master.rglob("*")) and not args.dry_run:
        raise SystemExit(f"Refusing to build: {master} is not empty.")

    db = sqlite3.connect(db_path)
    db.row_factory = sqlite3.Row

    rows = db.execute("""
        SELECT rel_path, filename, size_bytes, sha256, sidecar_rel_path,
               creation_timestamp, photo_taken_timestamp, photo_taken_formatted
        FROM files
        WHERE sha256 IS NOT NULL AND sha256 != ''
        ORDER BY sha256, rel_path
    """).fetchall()

    groups = defaultdict(list)
    for row in rows:
        groups[row["sha256"]].append(dict(row))

    chosen = []
    for sha, items in groups.items():
        chosen.append(sorted(items, key=score, reverse=True)[0])

    total_bytes = sum((r["size_bytes"] or 0) for r in chosen)

    print(f"Source media files: {len(rows)}")
    print(f"Unique master files: {len(chosen)}")
    print(f"Approx master size: {total_bytes / 1024 / 1024 / 1024:.2f} GB")
    print(f"Dry run: {args.dry_run}")
    print()

    copied = 0
    copied_bytes = 0

    with manifest.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=[
            "master_path", "source_path", "sha256", "size_bytes",
            "photo_taken_formatted", "sidecar_rel_path"
        ])
        writer.writeheader()

        for row in sorted(chosen, key=lambda r: (date_folder(r), r["filename"], r["sha256"])):
            src = base / row["rel_path"]
            dest = unique_dest(master, date_folder(row), row["filename"], row["sha256"])

            writer.writerow({
                "master_path": str(dest.relative_to(base)),
                "source_path": row["rel_path"],
                "sha256": row["sha256"],
                "size_bytes": row["size_bytes"],
                "photo_taken_formatted": row["photo_taken_formatted"],
                "sidecar_rel_path": row["sidecar_rel_path"],
            })

            if not args.dry_run:
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src, dest)

            copied += 1
            copied_bytes += row["size_bytes"] or 0

            if copied % 1000 == 0:
                print(f"Processed {copied}/{len(chosen)} | {copied_bytes / 1024 / 1024 / 1024:.2f} GB")

    print()
    print("Dry run complete." if args.dry_run else "Master build complete.")
    print(f"Manifest: {manifest}")
    print(f"Master: {master}")

if __name__ == "__main__":
    main()
