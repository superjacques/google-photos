# Google Photos Migration Toolkit

Repeatable toolkit for processing Google Takeout photo exports into a clean, deduplicated, metadata-restored, compressed photo library.

## Local working layout

Photos/
├── 1.zips/       raw Google Takeout ZIPs, never edited
├── 2.extracted/  raw extracted Takeout folders, read-only
├── 3.master/     cleaned final media library
├── reports/      generated local reports
└── scripts/      helper scripts

## Rules

- Never edit `1.zips` or `2.extracted`.
- Build clean output into `3.master`.
- Deduplicate before final output.
- Restore metadata from Google Takeout JSON sidecars where possible.
- Compress photos only when above the configured size target.
- Do not commit photos, ZIPs, extracted Takeout data, or private reports.
