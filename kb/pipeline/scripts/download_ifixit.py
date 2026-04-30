#!/usr/bin/env python3
"""
iFixit Guide Downloader
Fetches teardown/repair guides via the iFixit API v2.0.
Uses asyncio + httpx for parallel requests with exponential backoff.
Resume-safe via file existence checks.
"""

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path
from typing import Any

import httpx

BASE_LIST_URL = "https://www.ifixit.com/api/2.0/guides"
BASE_DETAIL_URL = "https://www.ifixit.com/api/2.0/guides"
LIMIT = 200
CONCURRENCY = 10
RAW_DIR = Path("/home/user/aisurvive/kb/output/raw/ifixit")


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def already_downloaded(guideid: int) -> bool:
    return (RAW_DIR / f"{guideid}.json").is_file()


def save_guide(guideid: int, data: dict[str, Any]) -> None:
    path = RAW_DIR / f"{guideid}.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


async def fetch_with_backoff(
    client: httpx.AsyncClient,
    url: str,
    max_retries: int = 5,
    base_delay: float = 1.0,
) -> Any:
    """Fetch JSON with exponential backoff on 429 / network errors."""
    for attempt in range(max_retries + 1):
        try:
            resp = await client.get(url, timeout=30)
            if resp.status_code == 429:
                delay = base_delay * (2 ** attempt)
                print(f"  [429] Rate limited. Backing off {delay:.1f}s... (attempt {attempt + 1})")
                await asyncio.sleep(delay)
                continue
            resp.raise_for_status()
            return resp.json()
        except (httpx.HTTPStatusError, httpx.RequestError) as exc:
            if attempt == max_retries:
                raise
            delay = base_delay * (2 ** attempt)
            print(f"  [ERR] {exc}. Retry in {delay:.1f}s... (attempt {attempt + 1})")
            await asyncio.sleep(delay)
    return None


async def fetch_guide_list(client: httpx.AsyncClient, offset: int) -> list[dict[str, Any]]:
    url = f"{BASE_LIST_URL}?limit={LIMIT}&offset={offset}"
    data = await fetch_with_backoff(client, url)
    if isinstance(data, list):
        return data
    # Fallback in case API ever returns dict
    return data.get("guides", []) if isinstance(data, dict) else []


async def fetch_guide_detail(client: httpx.AsyncClient, guideid: int) -> dict[str, Any]:
    url = f"{BASE_DETAIL_URL}/{guideid}"
    data = await fetch_with_backoff(client, url)
    if isinstance(data, dict):
        return data
    return {}


async def download_one(
    client: httpx.AsyncClient,
    sem: asyncio.Semaphore,
    guide_summary: dict[str, Any],
    counter: dict[str, int],
    total: int,
) -> bool:
    guideid = guide_summary.get("guideid")
    if guideid is None:
        return False

    if already_downloaded(guideid):
        counter["existing"] += 1
        return True

    async with sem:
        try:
            detail = await fetch_guide_detail(client, guideid)
        except Exception as exc:
            print(f"  [FAIL] Guide {guideid}: {exc}")
            return False

    if not detail:
        print(f"  [FAIL] Guide {guideid}: empty response")
        return False

    # Merge summary fields into detail if missing
    for key in ("title", "category", "url", "image", "summary", "difficulty", "time_required_max"):
        if key not in detail and key in guide_summary:
            detail[key] = guide_summary[key]

    save_guide(guideid, detail)
    counter["downloaded"] += 1
    print(f"Downloaded {counter['downloaded']}/{total} guides... (guideid={guideid})")
    return True


async def main(max_guides: int) -> None:
    ensure_dir(RAW_DIR)
    counter = {"downloaded": 0, "existing": 0, "failed": 0}

    async with httpx.AsyncClient() as client:
        # Collect guide summaries across pages
        all_summaries: list[dict[str, Any]] = []
        offset = 0
        while len(all_summaries) < max_guides:
            page = await fetch_guide_list(client, offset)
            if not page:
                break
            all_summaries.extend(page)
            offset += LIMIT
            if len(page) < LIMIT:
                break

        all_summaries = all_summaries[:max_guides]
        total = len(all_summaries)
        print(f"Collected {total} guide summaries. Starting download...")

        sem = asyncio.Semaphore(CONCURRENCY)
        tasks = [
            asyncio.create_task(download_one(client, sem, s, counter, total))
            for s in all_summaries
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        for r in results:
            if isinstance(r, Exception):
                counter["failed"] += 1

    print(
        f"Done. Downloaded: {counter['downloaded']}, Already had: {counter['existing']}, Failed: {counter['failed']}"
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Download iFixit guides via API v2.0")
    parser.add_argument(
        "--max-guides",
        type=int,
        default=500,
        help="Maximum number of guides to download (default: 500)",
    )
    args = parser.parse_args()
    asyncio.run(main(args.max_guides))
