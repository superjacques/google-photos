#!/usr/bin/env python3
import argparse
import csv
import hashlib
import json
import sqlite3
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

MEDIA_EXTS = {
    ".jpg", ".jpeg", ".png", ".gif", ".heic", ".heif", ".webp",
    ".mp4", ".mov", ".avi", ".mkv", ".3gp", ".m4v"
}

def human_bytes(n):
    units = ["B", "KB", "MB", "GB", "TB"]
    size = float(n or 0)
    for u in units:
        if size < 1024 or u == units[-1]:
            return f"{size:.2f} {u}"
        size /= 1024

def sha256_file(path, chunk_size=1024 * 1024):
    h = hashlib.sha256()
    with path.open("rb") as f:
        while True:
            b = f.read(chunk_size)
            if not b:
                break
            h.update(b)
    return h.hexdigest()

def is_media(path):
    return path.is_file() and path.suffix.lower() in MEDIA_EXTS

def is_json(path):
    return path.is_file() and path.suffix.lower() == ".json"

def read_json(path):
    try:
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}

def jget(data, *keys):
    cur = data
    for k in keys:
        if not isinstance(cur, dict):
            return ""
        cur = cur.get(k, "")
    return "" if cur is None else cur

def init_db(db):
    db.execute("""
        CREATE TABLE IF NOT EXISTS files (
            rel_path TEXT PRIMARY KEY,
            abs_path TEXT,
            filename TEXT,
            extension TEXT,
            size_bytes INTEGER,
            mtime_ns INTEGER,
            sha256 TEXT,
            sidecar_rel_path TEXT,
            json_title TEXT,
            json_description TEXT,
            creation_timestamp TEXT,
            creation_formatted TEXT,
            photo_taken_timestamp TEXT,
            photo_taken_formatted TEXT,
            latitude TEXT,
            longitude TEXT,
            altitude TEXT,
            last_seen_run TEXT,
            updated_at TEXT
        )
    """)
    db.execute("""
        CREATE TABLE IF NOT EXISTS runs (
            run_id TEXT PRIMARY KEY,
            started_at TEXT,
            base_path TEXT,
            media_count INTEGER,
            json_count INTEGER,
            total_media_bytes INTEGER,
            hashed_now INTEGER,
            hash_cache_hits INTEGER,
            matched_json INTEGER,
            missing_json INTEGER,
            duplicate_groups INTEGER,
            duplicate_files INTEGER,
            duplicate_wasted_bytes INTEGER
        )
    """)
    db.commit()

def build_json_indexes(json_files):
    by_exact_path = set(json_files)
    by_folder_name = defaultdict(dict)
    by_folder_title = defaultdict(lambda: defaultdict(list))

    for jp in json_files:
        by_folder_name[str(jp.parent)][jp.name] = jp
        data = read_json(jp)
        title = data.get("title") if isinstance(data, dict) else None
        if isinstance(title, str) and title.strip():
            by_folder_title[str(jp.parent)][title].append(jp)

    return by_exact_path, by_folder_name, by_folder_title

def possible_sidecars(media_path):
    parent = media_path.parent
    name = media_path.name
    stem = media_path.stem
    return [
        parent / f"{name}.supplemental-metadata.json",
        parent / f"{name}.json",
        parent / f"{stem}.supplemental-metadata.json",
        parent / f"{stem}.json",
    ]

def find_sidecar(media_path, json_exact, by_folder_name, by_folder_title):
    for candidate in possible_sidecars(media_path):
        if candidate in json_exact:
            return candidate

    folder = str(media_path.parent)
    names = by_folder_name.get(folder, {})

    for name in [
        f"{media_path.name}.supplemental-metadata.json",
        f"{media_path.name}.json",
        f"{media_path.stem}.supplemental-metadata.json",
        f"{media_path.stem}.json",
    ]:
        if name in names:
            return names[name]

    # Strong fallback: JSON title points back to exact media filename
    title_matches = by_folder_title.get(folder, {}).get(media_path.name, [])
    if len(title_matches) == 1:
        return title_matches[0]

    return None

def existing_cache(db, rel_path):
    cur = db.execute(
        "SELECT size_bytes, mtime_ns, sha256 FROM files WHERE rel_path = ?",
        (rel_path,)
    )
    return cur.fetchone()

def main():
    parser = argparse.ArgumentParser(description="Cached Google Takeout inventory scanner.")
    parser.add_argument("--base", default=str(Path.home() / "backups-4TB" / "Photos"))
    parser.add_argument("--hash", action="store_true", help="Calculate SHA-256 hashes. Cached if unchanged.")
    parser.add_argument("--rehash", action="store_true", help="Force rehash even if cached.")
    args = parser.parse_args()

    base = Path(args.base).expanduser().resolve()
    extracted = base / "2.extracted"
    reports = base / "reports"
    reports.mkdir(parents=True, exist_ok=True)

    db_path = reports / "photo-index.sqlite"
    db = sqlite3.connect(db_path)
    init_db(db)

    run_id = datetime.now().strftime("%Y%m%d-%H%M%S")
    inventory_csv = reports / f"inventory-{run_id}.csv"
    duplicates_csv = reports / f"duplicates-exact-{run_id}.csv"
    summary_txt = reports / f"inventory-summary-{run_id}.txt"

    all_files = [p for p in extracted.rglob("*") if p.is_file()]
    media_files = [p for p in all_files if is_media(p)]
    json_files = [p for p in all_files if is_json(p)]

    json_exact, by_folder_name, by_folder_title = build_json_indexes(json_files)

    ext_counts = Counter()
    hashes = defaultdict(list)
    rows = []

    total_media_bytes = 0
    hashed_now = 0
    hash_cache_hits = 0
    matched_json = 0
    missing_json = 0

    print(f"Run: {run_id}")
    print(f"Base: {base}")
    print(f"Media files: {len(media_files)}")
    print(f"JSON sidecars: {len(json_files)}")
    print(f"Hashing enabled: {args.hash}")
    print()

    for idx, media in enumerate(media_files, 1):
        rel = str(media.relative_to(base))
        st = media.stat()
        size = st.st_size
        mtime_ns = st.st_mtime_ns
        ext = media.suffix.lower()
        ext_counts[ext] += 1
        total_media_bytes += size

        sidecar = find_sidecar(media, json_exact, by_folder_name, by_folder_title)
        data = read_json(sidecar) if sidecar else {}

        if sidecar:
            matched_json += 1
        else:
            missing_json += 1

        file_hash = ""
        if args.hash:
            cached = existing_cache(db, rel)
            if cached and not args.rehash and cached[0] == size and cached[1] == mtime_ns and cached[2]:
                file_hash = cached[2]
                hash_cache_hits += 1
            else:
                file_hash = sha256_file(media)
                hashed_now += 1
            hashes[file_hash].append(media)

        sidecar_rel = str(sidecar.relative_to(base)) if sidecar else ""

        row = {
            "relative_path": rel,
            "filename": media.name,
            "extension": ext,
            "size_bytes": size,
            "size_human": human_bytes(size),
            "sha256": file_hash,
            "sidecar_found": "yes" if sidecar else "no",
            "sidecar_path": sidecar_rel,
            "json_title": jget(data, "title"),
            "json_description": jget(data, "description"),
            "creation_timestamp": jget(data, "creationTime", "timestamp"),
            "creation_formatted": jget(data, "creationTime", "formatted"),
            "photo_taken_timestamp": jget(data, "photoTakenTime", "timestamp"),
            "photo_taken_formatted": jget(data, "photoTakenTime", "formatted"),
            "latitude": jget(data, "geoData", "latitude"),
            "longitude": jget(data, "geoData", "longitude"),
            "altitude": jget(data, "geoData", "altitude"),
        }
        rows.append(row)

        db.execute("""
            INSERT INTO files (
                rel_path, abs_path, filename, extension, size_bytes, mtime_ns, sha256,
                sidecar_rel_path, json_title, json_description,
                creation_timestamp, creation_formatted,
                photo_taken_timestamp, photo_taken_formatted,
                latitude, longitude, altitude,
                last_seen_run, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(rel_path) DO UPDATE SET
                abs_path=excluded.abs_path,
                filename=excluded.filename,
                extension=excluded.extension,
                size_bytes=excluded.size_bytes,
                mtime_ns=excluded.mtime_ns,
                sha256=excluded.sha256,
                sidecar_rel_path=excluded.sidecar_rel_path,
                json_title=excluded.json_title,
                json_description=excluded.json_description,
                creation_timestamp=excluded.creation_timestamp,
                creation_formatted=excluded.creation_formatted,
                photo_taken_timestamp=excluded.photo_taken_timestamp,
                photo_taken_formatted=excluded.photo_taken_formatted,
                latitude=excluded.latitude,
                longitude=excluded.longitude,
                altitude=excluded.altitude,
                last_seen_run=excluded.last_seen_run,
                updated_at=excluded.updated_at
        """, (
            rel, str(media), media.name, ext, size, mtime_ns, file_hash,
            sidecar_rel,
            row["json_title"], row["json_description"],
            row["creation_timestamp"], row["creation_formatted"],
            row["photo_taken_timestamp"], row["photo_taken_formatted"],
            row["latitude"], row["longitude"], row["altitude"],
            run_id, datetime.now().isoformat(timespec="seconds")
        ))

        if idx % 1000 == 0:
            db.commit()
            print(f"Processed {idx}/{len(media_files)}")

    db.commit()

    duplicate_groups = {h: paths for h, paths in hashes.items() if h and len(paths) > 1}
    duplicate_file_count = sum(len(v) for v in duplicate_groups.values())
    duplicate_wasted_bytes = sum(
        sum(p.stat().st_size for p in paths[1:])
        for paths in duplicate_groups.values()
    )

    with inventory_csv.open("w", newline="", encoding="utf-8") as f:
        fieldnames = list(rows[0].keys()) if rows else []
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    with duplicates_csv.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["sha256", "group_size", "size_bytes_each", "path"])
        for h, paths in sorted(duplicate_groups.items(), key=lambda x: len(x[1]), reverse=True):
            size_each = paths[0].stat().st_size
            for p in paths:
                writer.writerow([h, len(paths), size_each, str(p.relative_to(base))])

    db.execute("""
        INSERT INTO runs (
            run_id, started_at, base_path, media_count, json_count, total_media_bytes,
            hashed_now, hash_cache_hits, matched_json, missing_json,
            duplicate_groups, duplicate_files, duplicate_wasted_bytes
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        run_id, datetime.now().isoformat(timespec="seconds"), str(base),
        len(media_files), len(json_files), total_media_bytes,
        hashed_now, hash_cache_hits, matched_json, missing_json,
        len(duplicate_groups), duplicate_file_count, duplicate_wasted_bytes
    ))
    db.commit()
    db.close()

    summary = f"""Google Photos Cached Inventory Summary
Generated: {datetime.now()}
Base: {base}

Total files scanned: {len(all_files)}
Media files: {len(media_files)}
JSON sidecars: {len(json_files)}
Total media size: {human_bytes(total_media_bytes)}

Media by extension:
""" + "\n".join(f"  {ext}: {count}" for ext, count in sorted(ext_counts.items())) + f"""

Media with matched JSON: {matched_json}
Media missing JSON: {missing_json}

Hashing:
  Hashed now: {hashed_now}
  Hash cache hits: {hash_cache_hits}
  SQLite cache: {db_path}

Exact duplicate groups: {len(duplicate_groups)}
Files inside duplicate groups: {duplicate_file_count}
Estimated duplicate bytes removable: {human_bytes(duplicate_wasted_bytes)}

Inventory CSV: {inventory_csv}
Duplicates CSV: {duplicates_csv}
Summary TXT: {summary_txt}
"""

    summary_txt.write_text(summary, encoding="utf-8")
    print()
    print(summary)

if __name__ == "__main__":
    main()
