#!/usr/bin/env python3
import argparse
import csv
import sqlite3
from collections import defaultdict
from pathlib import Path

def file_score(row):
    path = row["rel_path"] or ""
    score = 0

    # Keep the copy with metadata if possible.
    if row["sidecar_rel_path"]:
        score += 1000

    # Prefer the normal chronological Google Photos folders over album duplicates.
    if "/Photos from " in path:
        score += 500

    # Prefer cleaner/shorter paths as a final tie-breaker.
    score -= path.count("/") * 5
    score -= len(path) / 1000

    return score

def main():
    parser = argparse.ArgumentParser(description="Create exact duplicate keep-plan from cached inventory.")
    parser.add_argument("--base", default=str(Path.home() / "backups-4TB" / "Photos"))
    args = parser.parse_args()

    base = Path(args.base).expanduser().resolve()
    db_path = base / "reports" / "photo-index.sqlite"
    out_path = base / "reports" / "dedupe-plan-exact.csv"

    db = sqlite3.connect(db_path)
    db.row_factory = sqlite3.Row

    rows = db.execute("""
        SELECT rel_path, filename, extension, size_bytes, sha256, sidecar_rel_path,
               json_title, photo_taken_timestamp, photo_taken_formatted, last_seen_run
        FROM files
        WHERE sha256 IS NOT NULL AND sha256 != ''
        ORDER BY sha256, rel_path
    """).fetchall()

    groups = defaultdict(list)
    for row in rows:
        groups[row["sha256"]].append(dict(row))

    duplicate_groups = {h: items for h, items in groups.items() if len(items) > 1}

    keep_count = 0
    duplicate_count = 0
    removable_bytes = 0

    with out_path.open("w", newline="", encoding="utf-8") as f:
        fieldnames = [
            "action", "duplicate_group_size", "sha256", "size_bytes",
            "rel_path", "sidecar_rel_path", "photo_taken_formatted", "json_title"
        ]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()

        for h, items in sorted(duplicate_groups.items(), key=lambda x: len(x[1]), reverse=True):
            chosen = sorted(items, key=file_score, reverse=True)[0]["rel_path"]

            for item in sorted(items, key=lambda x: x["rel_path"]):
                action = "keep" if item["rel_path"] == chosen else "duplicate"
                if action == "keep":
                    keep_count += 1
                else:
                    duplicate_count += 1
                    removable_bytes += item["size_bytes"] or 0

                writer.writerow({
                    "action": action,
                    "duplicate_group_size": len(items),
                    "sha256": h,
                    "size_bytes": item["size_bytes"],
                    "rel_path": item["rel_path"],
                    "sidecar_rel_path": item["sidecar_rel_path"],
                    "photo_taken_formatted": item["photo_taken_formatted"],
                    "json_title": item["json_title"],
                })

    print("Dedupe plan created:")
    print(out_path)
    print()
    print(f"Duplicate groups: {len(duplicate_groups)}")
    print(f"Keep files: {keep_count}")
    print(f"Duplicate files: {duplicate_count}")
    print(f"Estimated removable GB: {removable_bytes / 1024 / 1024 / 1024:.2f}")

if __name__ == "__main__":
    main()
