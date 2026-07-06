#!/usr/bin/env python3
import argparse
import csv
from collections import Counter
from pathlib import Path

def main():
    parser = argparse.ArgumentParser(description="Verify deduplicated master build against manifest.")
    parser.add_argument("--base", default=str(Path.home() / "backups-4TB" / "Photos"))
    args = parser.parse_args()

    base = Path(args.base).expanduser().resolve()
    master = base / "3.master"
    manifest = base / "reports" / "master-build-manifest.csv"

    rows = []
    with manifest.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    missing_master = []
    size_mismatch = []
    missing_source = []

    sha_counts = Counter(row["sha256"] for row in rows)
    repeated_sha = [sha for sha, count in sha_counts.items() if count > 1]

    manifest_master_paths = set()

    for row in rows:
        master_path = base / row["master_path"]
        source_path = base / row["source_path"]
        manifest_master_paths.add(master_path)

        expected_size = int(row["size_bytes"] or 0)

        if not master_path.exists():
            missing_master.append(str(master_path))
        elif master_path.stat().st_size != expected_size:
            size_mismatch.append((str(master_path), expected_size, master_path.stat().st_size))

        if not source_path.exists():
            missing_source.append(str(source_path))

    actual_master_files = [p for p in master.rglob("*") if p.is_file()]

    extra_master_files = sorted(
        str(p) for p in actual_master_files
        if p not in manifest_master_paths
    )

    print("Master Verification")
    print(f"Base: {base}")
    print(f"Manifest rows: {len(rows)}")
    print(f"Actual master files: {len(actual_master_files)}")
    print(f"Unique SHA entries in manifest: {len(sha_counts)}")
    print()
    print(f"Missing master files: {len(missing_master)}")
    print(f"Size mismatches: {len(size_mismatch)}")
    print(f"Missing source files: {len(missing_source)}")
    print(f"Repeated SHA in manifest: {len(repeated_sha)}")
    print(f"Extra files in master: {len(extra_master_files)}")

    problems = missing_master or size_mismatch or missing_source or repeated_sha or extra_master_files

    if problems:
        print()
        print("First problems:")
        for item in missing_master[:10]:
            print("MISSING MASTER:", item)
        for item in size_mismatch[:10]:
            print("SIZE MISMATCH:", item)
        for item in missing_source[:10]:
            print("MISSING SOURCE:", item)
        for item in repeated_sha[:10]:
            print("REPEATED SHA:", item)
        for item in extra_master_files[:10]:
            print("EXTRA MASTER:", item)
        raise SystemExit(1)

    print()
    print("Verification passed.")

if __name__ == "__main__":
    main()
