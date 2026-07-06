#!/usr/bin/env python3
import csv
import hashlib
import shutil
import subprocess
from pathlib import Path

BASE = Path("/home/jacques/backups-4TB/Photos")
MASTER = BASE / "3.master"
OUT = BASE / "4.compressed"
REPORT = BASE / "reports" / "compressed-build-manifest.csv"

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".heic", ".heif"}
VIDEO_EXTS = {".mp4", ".mov", ".3gp", ".m4v", ".avi", ".mkv"}

IMAGE_COPY_BELOW = 500 * 1024
VIDEO_COPY_BELOW = 50 * 1024 * 1024

def run(cmd):
    subprocess.run(cmd, check=True)

def year_for(src):
    rel = src.relative_to(MASTER)
    first = rel.parts[0]
    return first if len(first) == 4 and first.isdigit() else "unknown-year"

def unique_dest(dest, rel):
    if not dest.exists():
        return dest

    suffix = hashlib.sha1(str(rel).encode("utf-8")).hexdigest()[:10]
    candidate = dest.with_name(f"{dest.stem}-{suffix}{dest.suffix}")

    n = 2
    while candidate.exists():
        candidate = dest.with_name(f"{dest.stem}-{suffix}-{n}{dest.suffix}")
        n += 1

    return candidate

def copy_times(src, dest):
    st = src.stat()
    dest.chmod(st.st_mode)
    os_times = (st.st_atime, st.st_mtime)
    import os
    os.utime(dest, os_times)

def compress_image(src, dest):
    run([
        "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
        "-i", str(src),
        "-map_metadata", "0",
        "-vf", "scale='min(1920,iw)':-2",
        "-q:v", "18",
        str(dest),
    ])

def compress_video(src, dest):
    run([
        "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
        "-i", str(src),
        "-map_metadata", "0",
        "-vf", "scale='if(gt(iw,ih),min(1280,iw),-2)':'if(gt(iw,ih),-2,min(1280,ih))'",
        "-c:v", "libx264",
        "-preset", "medium",
        "-crf", "32",
        "-c:a", "aac",
        "-b:a", "96k",
        "-movflags", "+faststart",
        str(dest),
    ])

def main():
    if OUT.exists() and any(OUT.rglob("*")):
        raise SystemExit(f"Refusing to build: {OUT} is not empty.")

    OUT.mkdir(parents=True, exist_ok=True)
    REPORT.parent.mkdir(parents=True, exist_ok=True)

    files = sorted(p for p in MASTER.rglob("*") if p.is_file())
    media = [p for p in files if p.suffix.lower() in IMAGE_EXTS | VIDEO_EXTS]

    print(f"Source media: {len(media)}")
    print(f"Output: {OUT}")
    print()

    total_orig = 0
    total_comp = 0

    with REPORT.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["action", "type", "original_bytes", "output_bytes", "saving_percent", "source", "output"])

        for i, src in enumerate(media, 1):
            rel = src.relative_to(MASTER)
            ext = src.suffix.lower()
            orig_size = src.stat().st_size
            total_orig += orig_size

            folder = OUT / year_for(src)

            if ext in IMAGE_EXTS:
                media_type = "image"
                if orig_size <= IMAGE_COPY_BELOW and ext in {".jpg", ".jpeg"}:
                    dest = unique_dest(folder / src.name, rel)
                    action = "copy"
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(src, dest)
                else:
                    dest = unique_dest(folder / src.with_suffix(".jpg").name, rel)
                    action = "compress"
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    compress_image(src, dest)
                    copy_times(src, dest)

            elif ext in VIDEO_EXTS:
                media_type = "video"
                if orig_size <= VIDEO_COPY_BELOW:
                    dest = unique_dest(folder / src.name, rel)
                    action = "copy"
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(src, dest)
                else:
                    dest = unique_dest(folder / src.with_suffix(".mp4").name, rel)
                    action = "compress"
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    compress_video(src, dest)
                    copy_times(src, dest)

            out_size = dest.stat().st_size
            total_comp += out_size
            saving = (1 - out_size / orig_size) * 100 if orig_size else 0

            writer.writerow([action, media_type, orig_size, out_size, f"{saving:.1f}", src, dest])

            if i % 500 == 0:
                print(f"Processed {i}/{len(media)} | {total_comp/1024/1024/1024:.2f} GB output")

    print()
    print("Compressed build complete.")
    print(f"Original: {total_orig/1024/1024/1024:.2f} GB")
    print(f"Output:   {total_comp/1024/1024/1024:.2f} GB")
    print(f"Saving:   {(1 - total_comp / total_orig) * 100:.1f}%")
    print(f"Report:   {REPORT}")

if __name__ == "__main__":
    main()
