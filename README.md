# Google Photos Migration Toolkit

Repeatable toolkit for turning Google Takeout exports into a clean, deduplicated, compressed photo library.

The goal is simple: Google Photos can be replaced because the source exports, scripts, reports, and final library can all be rebuilt locally.

## Folder Layout

Local photo data stays outside this repo:

    /home/jacques/backups-4TB/Photos/
    ├── 1.zips/        raw Google Takeout ZIPs, never edited
    ├── 2.extracted/   raw extracted Takeout folders, never edited
    ├── 3.master/      verified deduplicated master library
    ├── 4.compressed/  future compressed upload-ready output
    ├── reports/       generated CSVs, SQLite DB, manifests, logs
    └── scripts/       operational copies of repo scripts

## Safety Rules

- Never edit `1.zips/`.
- Never edit `2.extracted/`.
- Do not mutate `3.master/` after it has passed verification.
- Build compressed output into `4.compressed/`.
- Do not commit photos, ZIPs, extracted data, reports, CSVs, SQLite databases, logs, or manifests.
- All repeatable logic belongs in `scripts/` and should be committed to GitHub.

## Current Verified Checkpoint

Date: 2026-07-06

- Source media scanned: 82,529 files
- Source media size: 55.25 GB
- Deduplicated master files: 49,897
- Master size: about 39 GB
- Exact duplicate groups: 26,900
- Duplicate files skipped from master: 32,632
- Duplicate media avoided: about 17.28 GB
- Master verification: passed

Verification result:

- Manifest rows: 49,897
- Actual master files: 49,897
- Unique SHA entries: 49,897
- Missing master files: 0
- Size mismatches: 0
- Missing source files: 0
- Repeated SHA entries: 0
- Extra master files: 0

## Script Order

Run order used so far:

    scripts/photo-status.sh
    scripts/1-ingest-takeout-zip.sh
    scripts/2-inventory-cache.py
    scripts/3-dedupe-plan.py
    scripts/4-build-master.py
    scripts/5-verify-master.py

## Scripts

### scripts/photo-status.sh

Creates a quick status report for the photo workspace.

### scripts/1-ingest-takeout-zip.sh

Moves one `takeout-*.zip` from Downloads into `1.zips/`, renames it, extracts it into the selected account folder, then runs status and inventory.

### scripts/2-inventory-cache.py

Scans all media under `2.extracted/`, matches JSON sidecars, calculates SHA-256 hashes, and stores the result in:

    reports/photo-index.sqlite

Future runs skip rehashing unchanged files.

### scripts/3-dedupe-plan.py

Creates:

    reports/dedupe-plan-exact.csv

It selects one keeper per exact duplicate group and marks the rest as duplicates.

### scripts/4-build-master.py

Builds `3.master/` from the deduplicated hash groups.

It writes:

    reports/master-build-manifest.csv

### scripts/5-verify-master.py

Verifies that `3.master/` exactly matches the manifest.

## Compression Policy Draft

The next output folder should be:

    /home/jacques/backups-4TB/Photos/4.compressed/

Images:

- Compress from `3.master/` into `4.compressed/`.
- Target image size: roughly 350 KB to 500 KB.
- Files already below target should be copied unchanged.
- JPG/JPEG should be compressed toward target size.
- PNG, HEIC, and HEIF can be converted only when it gives useful savings and keeps normal viewing compatibility.
- Preserve useful dates and metadata where practical.

Videos:

- Videos should also be considered for compression.
- Small videos should be copied unchanged.
- Large videos should be compressed when above a size, bitrate, or resolution threshold.
- Starting rule to test: compress videos above 25 MB, above 1080p, or with obviously high bitrate.
- Prefer compatible MP4 output.
- Video compression must start with a small sample before processing everything.

## Next Step

Create a sample compression script that processes a small set from `3.master/` into `4.compressed-sample/`.

Only after visual review should the full `4.compressed/` library be built.


### scripts/9-prune-prefix-duplicates.py

Optional aggressive duplicate cleanup for `4.compressed`.

This catches files where one clean keeper exists and generated/reworked variants share the same filename prefix.

Example:

    20211114_120049.jpg
    20211114_120049-ef5fe89e0737.jpg

The keeper is the file whose stem is exactly `n` characters. Any longer file with the same first `n` characters and same extension can be removed.

Typical run:

    scripts/9-prune-prefix-duplicates.py --all-years --chars $(seq 3 19) --apply

This is intentionally more aggressive than exact hash dedupe and should only be used on `4.compressed`, not on `1.zips`, `2.extracted`, or `3.master`.
