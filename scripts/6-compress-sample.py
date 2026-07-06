#!/usr/bin/env python3
import csv
import subprocess
from pathlib import Path

BASE = Path("/home/jacques/backups-4TB/Photos")
MASTER = BASE / "3.master"
OUT = BASE / "4.compressed-sample"
REPORT = BASE / "reports" / "compression-sample.csv"

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".heic", ".heif"}
VIDEO_EXTS = {".mp4", ".mov", ".3gp", ".m4v", ".avi", ".mkv"}

def size(path):
    return path.stat().st_size

def mb(n):
    return n / 1024 / 1024

def run(cmd):
    subprocess.run(cmd, check=True)

def compress_image(src):
    rel = src.relative_to(MASTER)
    dest = OUT / "images" / rel.with_suffix(".jpg")
    dest.parent.mkdir(parents=True, exist_ok=True)

    run([
        "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
        "-i", str(src),
        "-vf", "scale='min(1920,iw)':-2",
        "-q:v", "18",
        str(dest),
    ])

    return dest

def compress_video(src):
    rel = src.relative_to(MASTER)
    dest = OUT / "videos" / rel.with_suffix(".mp4")
    dest.parent.mkdir(parents=True, exist_ok=True)

    run([
        "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
        "-i", str(src),
        "-vf", "scale='if(gt(iw,ih),min(1280,iw),-2)':'if(gt(iw,ih),-2,min(1280,ih))'",
        "-c:v", "libx264",
        "-preset", "medium",
        "-crf", "32",
        "-c:a", "aac",
        "-b:a", "96k",
        "-movflags", "+faststart",
        str(dest),
    ])

    return dest

def media_files(exts):
    return sorted(
        (p for p in MASTER.rglob("*") if p.is_file() and p.suffix.lower() in exts),
        key=size,
        reverse=True,
    )

def main():
    if OUT.exists():
        subprocess.run(["rm", "-rf", str(OUT)], check=True)

    (OUT / "images").mkdir(parents=True, exist_ok=True)
    (OUT / "videos").mkdir(parents=True, exist_ok=True)
    REPORT.parent.mkdir(parents=True, exist_ok=True)

    images = media_files(IMAGE_EXTS)[:10]
    videos = media_files(VIDEO_EXTS)[:5]

    with REPORT.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["type", "original_mb", "compressed_mb", "saving_percent", "original", "compressed", "status"])

        print("===== Compressing sample images =====")
        for src in images:
            try:
                dest = compress_image(src)
                orig = size(src)
                comp = size(dest)
                saving = (1 - comp / orig) * 100
                print(f"IMAGE {mb(orig):.2f} MB -> {mb(comp):.2f} MB  {src.relative_to(MASTER)}")
                writer.writerow(["image", f"{mb(orig):.2f}", f"{mb(comp):.2f}", f"{saving:.1f}", src, dest, "ok"])
            except Exception as e:
                print(f"IMAGE FAILED {src.relative_to(MASTER)}: {e}")
                writer.writerow(["image", "", "", "", src, "", f"failed: {e}"])

        print()
        print("===== Compressing sample videos =====")
        for src in videos:
            try:
                dest = compress_video(src)
                orig = size(src)
                comp = size(dest)
                saving = (1 - comp / orig) * 100
                print(f"VIDEO {mb(orig):.2f} MB -> {mb(comp):.2f} MB  {src.relative_to(MASTER)}")
                writer.writerow(["video", f"{mb(orig):.2f}", f"{mb(comp):.2f}", f"{saving:.1f}", src, dest, "ok"])
            except Exception as e:
                print(f"VIDEO FAILED {src.relative_to(MASTER)}: {e}")
                writer.writerow(["video", "", "", "", src, "", f"failed: {e}"])

    print()
    print("Sample output:")
    subprocess.run(["du", "-sh", str(OUT)], check=False)
    print()
    print(f"Report: {REPORT}")

if __name__ == "__main__":
    main()
