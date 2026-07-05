#!/usr/bin/env python3
import argparse
import csv
import hashlib
import json
import os
from collections import defaultdict, Counter
from datetime import datetime
from pathlib import Path

MEDIA_EXTS = {
    ".jpg", ".jpeg", ".png", ".gif", ".heic", ".heif", ".webp",
    ".mp4", ".mov", ".avi", ".mkv", ".3gp", ".m4v"
}

def sha256_file(path: Path, chunk_size: int = 1024 * 1024) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        while True:
            b = f.read(chunk_size)
            if not b:
                break
            h.update(b)
    return h.hexdigest()

def is_media(path: Path) -> bool:
    return path.is_file() and path.suffix.lower() in MEDIA_EXTS

def is_json(path: Path) -> bool:
    return path.is_file() and path.suffix.lower() == ".json"

def possible_sidecars(media_path: Path):
    name = media_path.name
    stem = media_path.stem
    parent = media_path.parent

    return [
        parent / f"{name}.supplemental-metadata.json",
        parent / f"{name}.json",
        parent / f"{stem}.supplemental-metadata.json",
        parent / f"{stem}.json",
    ]

def find_sidecar(media_path: Path, json_by_folder_name: dict):
    for candidate in possible_sidecars(media_path):
        if candidate.exists():
            return candidate

    folder_map = json_by_folder_name.get(str(media_path.parent), {})
    media_name = media_path.name
    media_stem = media_path.stem

    candidates = [
        f"{media_name}.supplemental-metadata.json",
        f"{media_name}.json",
        f"{media_stem}.supplemental-metadata.json",
        f"{media_stem}.json",
    ]

    for c in candidates:
        if c in folder_map:
            return folder_map[c]

    # Google sometimes truncates long JSON sidecar names.
    # Fallback: same folder, JSON title inside points to this media filename.
    return None

def read_json(path: Path):
    if not path:
        return {}
    try:
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}

def get_json_value(data, *keys):
    cur = data
    for k in keys:
        if not isinstance(cur, dict):
            return ""
        cur = cur.get(k, "")
    return cur if cur is not None else ""

def human_bytes(n: int) -> str:
    units = ["B", "KB", "MB", "GB", "TB"]
    size = float(n)
    for u in units:
        if size < 1024 or u == units[-1]:
            return f"{size:.2f} {u}"
        size /= 1024

def main():
    parser = argparse.ArgumentParser(description="Inventory Google Takeout photo exports.")
    parser.add_argument("--base", default=str(Path.home() / "backups-4TB" / "Photos"))
    parser.add_argument("--hash", action="store_true", help="Calculate SHA-256 hashes and exact duplicates.")
    args = parser.parse_args()

    base = Path(args.base).expanduser().resolve()
    extracted = base / "2.extracted"
    reports = base / "reports"
    reports.mkdir(parents=True, exist_ok=True)

    if not extracted.exists():
        raise SystemExit(f"Missing extracted folder: {extracted}")

    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    inventory_csv = reports / f"inventory-{ts}.csv"
    duplicates_csv = reports / f"duplicates-exact-{ts}.csv"
    summary_txt = reports / f"inventory-summary-{ts}.txt"

    all_files = [p for p in extracted.rglob("*") if p.is_file()]
    media_files = [p for p in all_files if is_media(p)]
    json_files = [p for p in all_files if is_json(p)]

    json_by_folder_name = defaultdict(dict)
    for jp in json_files:
        json_by_folder_name[str(jp.parent)][jp.name] = jp

    rows = []
    hashes = defaultdict(list)
    ext_counts = Counter()
    total_media_bytes = 0
    matched_json = 0
    missing_json = 0
    json_parse_ok = 0

    print(f"Scanning media files: {len(media_files)}")
    print(f"Hashing enabled: {args.hash}")
    print()

    for i, media in enumerate(media_files, 1):
        rel = media.relative_to(base)
        st = media.stat()
        ext = media.suffix.lower()
        ext_counts[ext] += 1
        total_media_bytes += st.st_size

        sidecar = find_sidecar(media, json_by_folder_name)
        data = read_json(sidecar) if sidecar else {}

        if sidecar:
            matched_json += 1
            if data:
                json_parse_ok += 1
        else:
            missing_json += 1

        file_hash = ""
        if args.hash:
            file_hash = sha256_file(media)
            hashes[file_hash].append(media)

        title = get_json_value(data, "title")
        description = get_json_value(data, "description")
        creation_ts = get_json_value(data, "creationTime", "timestamp")
        creation_fmt = get_json_value(data, "creationTime", "formatted")
        taken_ts = get_json_value(data, "photoTakenTime", "timestamp")
        taken_fmt = get_json_value(data, "photoTakenTime", "formatted")
        lat = get_json_value(data, "geoData", "latitude")
        lon = get_json_value(data, "geoData", "longitude")
        alt = get_json_value(data, "geoData", "altitude")

        rows.append({
            "relative_path": str(rel),
            "filename": media.name,
            "extension": ext,
            "size_bytes": st.st_size,
            "size_human": human_bytes(st.st_size),
            "sha256": file_hash,
            "sidecar_found": "yes" if sidecar else "no",
            "sidecar_path": str(sidecar.relative_to(base)) if sidecar else "",
            "json_title": title,
            "json_description": description,
            "creation_timestamp": creation_ts,
            "creation_formatted": creation_fmt,
            "photo_taken_timestamp": taken_ts,
            "photo_taken_formatted": taken_fmt,
            "latitude": lat,
            "longitude": lon,
            "altitude": alt,
        })

        if i % 1000 == 0:
            print(f"Processed {i}/{len(media_files)}")

    with inventory_csv.open("w", newline="", encoding="utf-8") as f:
        fieldnames = list(rows[0].keys()) if rows else [
            "relative_path", "filename", "extension", "size_bytes", "size_human",
            "sha256", "sidecar_found", "sidecar_path"
        ]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    duplicate_groups = {h: paths for h, paths in hashes.items() if h and len(paths) > 1}
    duplicate_file_count = sum(len(v) for v in duplicate_groups.values())
    duplicate_wasted_bytes = sum(
        sum(p.stat().st_size for p in paths[1:])
        for paths in duplicate_groups.values()
    )

    with duplicates_csv.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["sha256", "group_size", "size_bytes_each", "path"])
        for h, paths in sorted(duplicate_groups.items(), key=lambda x: len(x[1]), reverse=True):
            size_each = paths[0].stat().st_size
            for p in paths:
                writer.writerow([h, len(paths), size_each, str(p.relative_to(base))])

    summary = []
    summary.append("Google Photos Inventory Summary")
    summary.append(f"Generated: {datetime.now()}")
    summary.append(f"Base: {base}")
    summary.append("")
    summary.append(f"Total files scanned: {len(all_files)}")
    summary.append(f"Media files: {len(media_files)}")
    summary.append(f"JSON sidecars: {len(json_files)}")
    summary.append(f"Total media size: {human_bytes(total_media_bytes)}")
    summary.append("")
    summary.append("Media by extension:")
    for ext, count in sorted(ext_counts.items()):
        summary.append(f"  {ext}: {count}")
    summary.append("")
    summary.append(f"Media with matched JSON: {matched_json}")
    summary.append(f"Media missing JSON: {missing_json}")
    summary.append(f"Matched JSON parsed OK: {json_parse_ok}")
    summary.append("")
    if args.hash:
        summary.append(f"Exact duplicate groups: {len(duplicate_groups)}")
        summary.append(f"Files inside duplicate groups: {duplicate_file_count}")
        summary.append(f"Estimated duplicate bytes removable: {human_bytes(duplicate_wasted_bytes)}")
    else:
        summary.append("Exact duplicate scan: not run. Use --hash.")
    summary.append("")
    summary.append(f"Inventory CSV: {inventory_csv}")
    summary.append(f"Duplicates CSV: {duplicates_csv}")
    summary.append("")

    summary_text = "\n".join(summary)
    summary_txt.write_text(summary_text, encoding="utf-8")

    print()
    print(summary_text)

if __name__ == "__main__":
    main()
