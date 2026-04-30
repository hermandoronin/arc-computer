#!/usr/bin/env python3
"""
Instructables detail page fetcher - reads URLs from seed file and downloads project data.
Uses JSON-LD structured data (schema.org HowTo) + BeautifulSoup fallback.
"""

import asyncio
import json
import os
import random
import re
import sys
import time
from pathlib import Path
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup

# ── Config ─────────────────────────────────────────────────────────
SEED_FILE = Path("/mnt/agents/output/ark-kb-pipeline/scripts/instructables_urls.json")
OUTPUT_DIR = Path("/mnt/staging/ark-kb/raw/instructables")
RATE_LIMIT = 1.0  # seconds between requests

# Rotating User-Agents
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/121.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Safari/605.1.15",
]


def slugify(url: str) -> str:
    parsed = urlparse(url)
    path = parsed.path.strip("/")
    return path.split("/")[-1] if path else "unknown"


def get_headers():
    return {
        "User-Agent": random.choice(USER_AGENTS),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
        "Accept-Encoding": "gzip, deflate, br",
        "DNT": "1",
        "Connection": "keep-alive",
    }


async def fetch(client: httpx.AsyncClient, url: str, retries: int = 3) -> str:
    for attempt in range(retries):
        try:
            resp = await client.get(url, headers=get_headers(), follow_redirects=True, timeout=30.0)
            resp.raise_for_status()
            return resp.text
        except Exception as exc:
            wait = 2 ** attempt
            print(f"  [WARN] Fetch failed ({attempt + 1}/{retries}): {url} — {exc}")
            if attempt < retries - 1:
                await asyncio.sleep(wait)
    return ""


def extract_json_ld(html: str):
    soup = BeautifulSoup(html, "html.parser")
    data = {"HowTo": None, "Article": None}
    for script in soup.find_all("script", type="application/ld+json"):
        try:
            obj = json.loads(script.string or "{}")
            if isinstance(obj, dict):
                if obj.get("@type") == "HowTo":
                    data["HowTo"] = obj
                elif obj.get("@type") == "Article":
                    data["Article"] = obj
        except json.JSONDecodeError:
            continue
    return data, soup


def parse_detail_page(html: str, url: str) -> dict:
    ld_data, soup = extract_json_ld(html)
    howto = ld_data.get("HowTo") or {}
    article = ld_data.get("Article") or {}
    slug = slugify(url)

    # Title
    title = howto.get("name") or article.get("headline") or ""
    if not title:
        h1 = soup.find("h1")
        if h1:
            title = h1.get_text(strip=True)

    # Description / Intro
    description = howto.get("description") or article.get("description") or ""
    if not description:
        meta = soup.find("meta", attrs={"name": "description"})
        if meta:
            description = meta.get("content", "")

    # Author
    author = ""
    contributor = article.get("contributor") or {}
    if isinstance(contributor, dict):
        author = contributor.get("name", "")
    if not author:
        author_el = soup.find("a", href=re.compile(r"/member/"))
        if author_el:
            author = author_el.get_text(strip=True)

    # Steps from HowTo JSON-LD
    steps = []
    for step in howto.get("step", []):
        step_text = step.get("text", "")
        step_name = step.get("name", "")
        step_image = ""
        img_obj = step.get("image", {})
        if isinstance(img_obj, dict):
            step_image = img_obj.get("url", "")
        elif isinstance(img_obj, str):
            step_image = img_obj
        steps.append({
            "name": step_name,
            "text": step_text,
            "image": step_image,
        })

    # Fallback: parse steps from DOM
    if not steps:
        step_els = soup.find_all("div", class_=re.compile(r"step"))
        for i, el in enumerate(step_els):
            step_title_el = el.find(["h2", "h3", "h4", "strong"])
            step_title = step_title_el.get_text(strip=True) if step_title_el else f"Step {i+1}"
            body = el.get_text("\n", strip=True)
            if step_title in body:
                body = body.replace(step_title, "", 1).strip()
            steps.append({
                "name": step_title,
                "text": body,
                "image": "",
            })

    # Supplies / Materials / Tools
    materials = []
    tools = []
    supplies = []
    for header in soup.find_all(["h2", "h3", "h4", "strong"]):
        txt = header.get_text(strip=True).lower()
        if "supply" in txt or "material" in txt or "part" in txt or "component" in txt:
            ul = header.find_next("ul")
            if ul:
                for li in ul.find_all("li"):
                    item_text = li.get_text(strip=True)
                    if item_text:
                        supplies.append(item_text)
        if "tool" in txt:
            ul = header.find_next("ul")
            if ul:
                for li in ul.find_all("li"):
                    item_text = li.get_text(strip=True)
                    if item_text:
                        tools.append(item_text)

    supplies_div = soup.find("div", class_=re.compile(r"supplies"))
    if supplies_div:
        for li in supplies_div.find_all("li"):
            txt = li.get_text(strip=True)
            if txt and txt not in supplies:
                supplies.append(txt)

    # Images
    images = []
    for img in soup.find_all("img"):
        src = img.get("src", "")
        if src and "content.instructables.com" in src:
            images.append(src)
    main_img = howto.get("image", {}).get("url", "") if isinstance(howto.get("image"), dict) else ""
    if main_img and main_img not in images:
        images.insert(0, main_img)

    return {
        "slug": slug,
        "url": url,
        "title": title,
        "author": author,
        "description": description,
        "steps": steps,
        "supplies": supplies,
        "tools": tools,
        "images": images[:20],
        "step_count": len(steps),
        "scraped_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }


async def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    print(f"Output directory: {OUTPUT_DIR}")

    # Load seed URLs
    with open(SEED_FILE, "r", encoding="utf-8") as f:
        seed_data = json.load(f)

    all_urls = []
    for cat, urls in seed_data.items():
        all_urls.extend(urls)

    print(f"Total URLs to fetch: {len(all_urls)}")

    semaphore = asyncio.Semaphore(2)
    limits = httpx.Limits(max_connections=10, max_keepalive_connections=5)
    timeout = httpx.Timeout(30.0, connect=10.0)

    results = []
    async with httpx.AsyncClient(limits=limits, timeout=timeout, follow_redirects=True) as client:
        for i, url in enumerate(all_urls, 1):
            async with semaphore:
                print(f"[{i}/{len(all_urls)}] Fetching {url} ...")
                html = await fetch(client, url)
                if not html:
                    continue
                try:
                    data = parse_detail_page(html, url)
                    if not data.get("title"):
                        print(f"  [WARN] No title extracted, skipping")
                        continue
                    results.append(data)

                    out_path = OUTPUT_DIR / f"{data['slug']}.json"
                    with open(out_path, "w", encoding="utf-8") as f:
                        json.dump(data, f, indent=2, ensure_ascii=False)
                    print(f"  [OK] Saved {out_path.name}")

                except Exception as exc:
                    print(f"  [ERR] Parse error: {exc}")
                    import traceback
                    traceback.print_exc()

                await asyncio.sleep(RATE_LIMIT)

    total = len(results)
    print(f"\n{'='*60}")
    print(f"Total Instructables projects downloaded: {total}")
    print(f"{'='*60}")

    manifest = {
        "source": "instructables",
        "categories": list(seed_data.keys()),
        "total_projects": total,
        "projects": [{"slug": r["slug"], "title": r["title"], "url": r["url"]} for r in results],
    }
    manifest_path = OUTPUT_DIR / "manifest.json"
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)
    print(f"Manifest saved to {manifest_path}")

    return total


if __name__ == "__main__":
    total = asyncio.run(main())
    sys.exit(0)
