#!/usr/bin/env python3
"""
YouTube Transcript Downloader for Electronics Reverse-Engineering Channels.

Downloads auto-generated or manual captions using yt-dlp and saves metadata.
Skips already-downloaded videos. Limits to ~20 videos per channel.

Usage:
    python download_youtube_transcripts.py [--max-per-channel N] [--channels channel1,channel2,...]

Channels supported:
    eevblog      -> @EEVblog
    bigclive     -> @bigclivedotcom
    mrcarlson    -> @MrCarlsonsLab
"""

import argparse
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

# ── Configuration ────────────────────────────────────────────────────────────

DEFAULT_MAX_PER_CHANNEL = 20

CHANNEL_MAP: Dict[str, str] = {
    "eevblog": "https://www.youtube.com/@EEVblog/videos",
    "bigclive": "https://www.youtube.com/@bigclivedotcom/videos",
    "mrcarlson": "https://www.youtube.com/@MrCarlsonsLab/videos",
}

CHANNEL_SLUGS = list(CHANNEL_MAP.keys())

# yt-dlp binary (may need PATH adjustment)
YT_DLP = os.environ.get("YT_DLP_BIN", "yt-dlp")

# Subtitle language preference
SUB_LANGS = "en,en-US,en-GB"

# Sleep between videos to be polite
SLEEP_SECONDS = 1.5


# ── Downloader class (avoids globals) ───────────────────────────────────────

class Downloader:
    def __init__(self, output_root: Path):
        self.staging_root = Path(output_root)
        self._ensure_dirs()

    def _ensure_dirs(self) -> None:
        for slug in CHANNEL_SLUGS:
            (self.staging_root / slug).mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _run_yt_dlp(args: List[str], timeout: int = 120) -> Tuple[int, str, str]:
        cmd = [YT_DLP] + args
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return proc.returncode, proc.stdout, proc.stderr

    def get_video_list(self, channel_url: str, max_videos: int) -> List[Dict[str, str]]:
        args = [
            "--flat-playlist",
            "--playlist-end", str(max_videos),
            "--print", "%(id)s\t%(title)s",
            channel_url,
        ]
        code, stdout, stderr = self._run_yt_dlp(args, timeout=180)
        videos = []
        for line in stdout.strip().splitlines():
            if "\t" in line:
                vid, title = line.split("\t", 1)
                videos.append({
                    "id": vid.strip(),
                    "title": title.strip(),
                    "url": f"https://www.youtube.com/watch?v={vid.strip()}",
                })
        return videos

    def video_exists(self, slug: str, video_id: str) -> bool:
        out_dir = self.staging_root / slug
        for ext in (".srt", ".vtt", ".json"):
            if (out_dir / f"{video_id}{ext}").exists():
                return True
        return False

    def download_subtitles(self, video_url: str, out_dir: Path, video_id: str) -> Tuple[bool, Optional[Path], str]:
        # Strategy 1: auto-generated subtitles
        auto_args = [
            "--write-auto-subs",
            "--skip-download",
            "--sub-langs", SUB_LANGS,
            "--sub-format", "srt/best",
            "--output", str(out_dir / f"{video_id}.%(ext)s"),
            video_url,
        ]
        code, stdout, stderr = self._run_yt_dlp(auto_args, timeout=120)

        written = list(out_dir.glob(f"{video_id}.*"))
        sub_file = None
        for f in written:
            if f.suffix in (".srt", ".vtt"):
                sub_file = f
                break

        if sub_file:
            final_path = out_dir / f"{video_id}{sub_file.suffix}"
            if final_path != sub_file:
                if final_path.exists():
                    final_path.unlink()
                sub_file.rename(final_path)
                sub_file = final_path
            return True, sub_file, "auto-subs"

        # Strategy 2: manual / uploaded captions
        manual_args = [
            "--write-subs",
            "--skip-download",
            "--sub-langs", SUB_LANGS,
            "--sub-format", "srt/best",
            "--output", str(out_dir / f"{video_id}.%(ext)s"),
            video_url,
        ]
        code, stdout, stderr = self._run_yt_dlp(manual_args, timeout=120)

        written = list(out_dir.glob(f"{video_id}.*"))
        for f in written:
            if f.suffix in (".srt", ".vtt"):
                sub_file = f
                break

        if sub_file:
            final_path = out_dir / f"{video_id}{sub_file.suffix}"
            if final_path != sub_file:
                if final_path.exists():
                    final_path.unlink()
                sub_file.rename(final_path)
                sub_file = final_path
            return True, sub_file, "manual-subs"

        # Clean up partial files
        for f in out_dir.glob(f"{video_id}.*"):
            if f.suffix not in (".json", ".srt", ".vtt"):
                f.unlink(missing_ok=True)

        return False, None, "no-captions"

    def download_metadata(self, video_url: str, out_dir: Path, video_id: str) -> bool:
        meta_path = out_dir / f"{video_id}.json"
        if meta_path.exists():
            return True

        args = ["--dump-single-json", "--skip-download", video_url]
        code, stdout, stderr = self._run_yt_dlp(args, timeout=120)
        if code != 0 or not stdout.strip():
            return False

        try:
            info = json.loads(stdout.strip().splitlines()[0])
        except (json.JSONDecodeError, IndexError):
            return False

        meta = {
            "video_id": video_id,
            "title": info.get("title"),
            "channel": info.get("channel"),
            "channel_id": info.get("channel_id"),
            "uploader": info.get("uploader"),
            "url": video_url,
            "duration": info.get("duration"),
            "duration_string": info.get("duration_string"),
            "description": info.get("description"),
            "upload_date": info.get("upload_date"),
            "view_count": info.get("view_count"),
            "like_count": info.get("like_count"),
            "tags": info.get("tags", []),
            "categories": info.get("categories", []),
            "subtitle_status": None,
        }
        meta_path.write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")
        return True

    def update_metadata_status(self, slug: str, video_id: str, status: str) -> None:
        meta_path = self.staging_root / slug / f"{video_id}.json"
        if not meta_path.exists():
            return
        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
            meta["subtitle_status"] = status
            meta_path.write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")
        except Exception:
            pass

    def process_channel(self, slug: str, max_videos: int, dry_run: bool = False) -> Dict:
        url = CHANNEL_MAP[slug]
        out_dir = self.staging_root / slug
        out_dir.mkdir(parents=True, exist_ok=True)

        print(f"\n{'='*60}")
        print(f"Channel: {slug.upper()}  ->  {url}")
        print(f"{'='*60}")

        print("Fetching video list ...")
        videos = self.get_video_list(url, max_videos)
        print(f"Found {len(videos)} videos.")

        results = {
            "slug": slug,
            "total": len(videos),
            "downloaded": 0,
            "skipped": 0,
            "no_captions": [],
            "errors": [],
        }

        for idx, vid in enumerate(videos, 1):
            video_id = vid["id"]
            video_url = vid["url"]
            title = vid["title"]

            print(f"\n[{idx}/{len(videos)}] {video_id} -- {title[:70]}...")

            if self.video_exists(slug, video_id):
                print("   SKIP (already downloaded)")
                results["skipped"] += 1
                continue

            if dry_run:
                print("   DRY RUN -- would download")
                continue

            meta_ok = self.download_metadata(video_url, out_dir, video_id)
            if not meta_ok:
                print("   WARN: metadata fetch failed")
                results["errors"].append(video_id)

            ok, sub_path, status = self.download_subtitles(video_url, out_dir, video_id)
            if ok:
                print(f"   OK  -> {sub_path.name} ({status})")
                results["downloaded"] += 1
                self.update_metadata_status(slug, video_id, status)
            else:
                print(f"   NO CAPTIONS ({status})")
                results["no_captions"].append(video_id)
                self.update_metadata_status(slug, video_id, status)

            time.sleep(SLEEP_SECONDS)

        return results


def main() -> int:
    parser = argparse.ArgumentParser(description="Download YouTube transcripts for EE channels")
    parser.add_argument(
        "--max-per-channel",
        type=int,
        default=DEFAULT_MAX_PER_CHANNEL,
        help=f"Max videos per channel (default {DEFAULT_MAX_PER_CHANNEL})",
    )
    parser.add_argument(
        "--channels",
        type=str,
        default=",".join(CHANNEL_SLUGS),
        help=f"Comma-separated channel slugs (default: {','.join(CHANNEL_SLUGS)})",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="List videos but do not download",
    )
    parser.add_argument(
        "--output-root",
        type=str,
        default="/home/user/aisurvive/kb/output/raw/youtube",
        help="Root output directory (default: /home/user/aisurvive/kb/output/raw/youtube)",
    )
    args = parser.parse_args()

    wanted = [s.strip().lower() for s in args.channels.split(",")]
    for s in wanted:
        if s not in CHANNEL_MAP:
            print(f"ERROR: Unknown channel slug '{s}'. Valid: {', '.join(CHANNEL_SLUGS)}")
            return 1

    dl = Downloader(Path(args.output_root))

    all_results = []
    for slug in wanted:
        res = dl.process_channel(slug, args.max_per_channel, dry_run=args.dry_run)
        all_results.append(res)

    # Summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    total_down = 0
    total_skip = 0
    total_nocap = []
    for r in all_results:
        print(f"\n{r['slug'].upper()}:")
        print(f"  Videos found : {r['total']}")
        print(f"  Downloaded   : {r['downloaded']}")
        print(f"  Skipped      : {r['skipped']}")
        print(f"  No captions  : {len(r['no_captions'])}")
        if r["no_captions"]:
            print(f"  No-caps list : {', '.join(r['no_captions'])}")
        total_down += r["downloaded"]
        total_skip += r["skipped"]
        total_nocap.extend(r["no_captions"])

    print(f"\nGRAND TOTALS:")
    print(f"  Downloaded   : {total_down}")
    print(f"  Skipped      : {total_skip}")
    print(f"  No captions  : {len(total_nocap)}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
