# Google Photos Migration Toolkit

Repeatable toolkit for processing Google Takeout photo exports into a clean, deduplicated, metadata-restored, compressed photo library.

The goal is to make Google Photos replaceable: exports can be processed locally, cleaned, compressed, and re-uploaded without trusting Google Photos as the permanent source of truth.

## Local working layout

Local photo data stays outside this repo.

Expected local path:

    ~/backups-4TB/Photos/
    ├── 1.zips/       raw Google Takeout ZIPs, never edited
    ├── 2.extracted/  raw extracted Takeout folders, read-only
    ├── 3.master/     cleaned final media library
    ├── reports/      generated local reports and SQLite index
    └── scripts/      operational copies of scripts

## Safety rules

- Never edit `1.zips`.
- Never edit `2.extracted`.
- Build clean output into `3.master`.
- Deduplicate before final output.
- Restore metadata from Google Takeout JSON sidecars where possible.
- Compress photos only when above the configured size target.
- Do not commit photos, ZIPs, extracted Takeout data, private reports, CSVs, databases, or logs.

## Scripts

### scripts/photo-status.sh

Quick workspace status report.

Reports:

- folder layout
- top-level folder sizes
- ZIP file sizes
- extracted folder sizes
- master folder size
- media counts
- largest extracted files

Run:

    scripts/photo-status.sh ~/backups-4TB/Photos

### scripts/1-ingest-takeout-zip.sh

Reusable Takeout ingest script.

It expects exactly one `takeout-*.zip` file in `~/Downloads`.

It:

- tests the ZIP
- moves it into `1.zips`
- renames it to the supplied destination name
- extracts it into the supplied account folder under `2.extracted`
- runs status
- runs cached inventory
- removes any old one-time `move-bigzip.sh` cron entry

Run:

    BASE=/home/jacques/backups-4TB/Photos scripts/1-ingest-takeout-zip.sh jacquesbezuidenhout1980-02.zip jacquesbezuidenhout1980

### scripts/2-inventory-cache.py

Cached inventory scanner.

It:

- scans all media under `2.extracted`
- matches media files to Google Takeout JSON sidecars
- improves matching using JSON `title` fields when filenames are weird/truncated
- extracts Google metadata fields
- calculates SHA-256 hashes
- stores hash results in SQLite
- skips rehashing unchanged files on future runs
- writes inventory CSV, duplicate CSV, summary TXT, and `photo-index.sqlite`

Run:

    scripts/2-inventory-cache.py --base /home/jacques/backups-4TB/Photos --hash

Force complete rehash:

    scripts/2-inventory-cache.py --base /home/jacques/backups-4TB/Photos --hash --rehash

## Current workflow

1. Put raw Takeout ZIPs in `1.zips` or ingest from `~/Downloads/takeout-*.zip`.
2. Extract into `2.extracted`.
3. Run `photo-status.sh`.
4. Run `2-inventory-cache.py --hash`.
5. Review reports before creating anything in `3.master`.
6. Later scripts will build the deduplicated, metadata-restored, compressed master library.

## Current target

Photos larger than the configured limit should later be compressed toward approximately 1 MB.

Files already smaller than the limit should be copied unchanged.

Videos are currently inventoried and deduplicated, but compression policy is still undecided.
