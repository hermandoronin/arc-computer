#!/usr/bin/env python3
"""
Hackaday.io scraper - downloads DIY project data from hackaday.io/projects listings.
Uses BeautifulSoup for HTML parsing.
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
BASE_URL = "https://hackaday.io"
LISTING_URL = "https://hackaday.io/projects"
MAX_PROJECTS = 300
RATE_LIMIT = 0.2
OUTPUT_DIR = Path("/home/user/aisurvive/kb/output/raw/hackaday")

# Rotating User-Agents
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/121.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Safari/605.1.15",
]

# ── Helpers ────────────────────────────────────────────────────────
def project_id_from_url(url: str) -> str:
    """Extract project ID from URL for filename."""
    # URL like /project/195725-control-arcade-all-in-one-360
    m = re.search(r"/project/(\d+)", url)
    return m.group(1) if m else "unknown"


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
    """Fetch with retries and exponential backoff."""
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


def extract_project_links_from_listing(html: str) -> list:
    """Extract unique project URLs from a Hackaday listing page."""
    soup = BeautifulSoup(html, "html.parser")
    links = []
    seen = set()

    # Look for project links: /project/{id}-{slug}
    for a in soup.find_all("a", href=True):
        href = a["href"]
        m = re.match(r"/project/(\d+)(?:-[^/]+)?/?$", href)
        if m:
            pid = m.group(1)
            full = urljoin(BASE_URL, href)
            if pid not in seen:
                seen.add(pid)
                links.append(full)

    return links


def parse_project_page(html: str, url: str) -> dict:
    """Parse a Hackaday project detail page."""
    soup = BeautifulSoup(html, "html.parser")
    pid = project_id_from_url(url)

    # Title
    title = ""
    h1 = soup.find("h1")
    if h1:
        title = h1.get_text(strip=True)
    if not title:
        title_tag = soup.find("title")
        if title_tag:
            title = title_tag.get_text(strip=True).replace(" | Hackaday.io", "")

    # Summary (subtitle / meta description)
    summary = ""
    meta = soup.find("meta", attrs={"name": "description"})
    if meta:
        summary = meta.get("content", "")
    # Try to find subtitle near h1
    if not summary:
        subtitle = soup.find(class_=re.compile(r"subtitle|summary|tagline"))
        if subtitle:
            summary = subtitle.get_text(strip=True)

    # Author
    author = ""
    author_link = soup.find("a", href=re.compile(r"/hacker/\d+"))
    if author_link:
        author = author_link.get_text(strip=True)

    # Tags
    tags = []
    for a in soup.find_all("a", href=re.compile(r"/projects\?tag=")):
        tag_text = a.get_text(strip=True)
        if tag_text and tag_text not in tags and tag_text != "MISC":
            tags.append(tag_text)

    # Description
    description = ""
    # Look for the Description section content
    desc_header = None
    for header in soup.find_all(["h2", "h3", "h4", "div"]):
        txt = header.get_text(strip=True)
        if txt == "Description":
            desc_header = header
            break
    if desc_header:
        # The description text usually follows the header
        # It may be in a sibling div or p
        next_el = desc_header.find_next_sibling()
        if next_el:
            description = next_el.get_text("\n", strip=True)
        else:
            # Try parent's next sibling
            parent = desc_header.find_parent()
            if parent:
                ps = parent.find_all("p")
                for p in ps:
                    ptxt = p.get_text(strip=True)
                    if ptxt and ptxt != "Description":
                        description = ptxt
                        break

    # Fallback: try to find a div with description-like content near the top
    if not description:
        for div in soup.find_all("div"):
            cls = " ".join(div.get("class", []))
            if "description" in cls.lower() or "summary" in cls.lower():
                txt = div.get_text("\n", strip=True)
                if len(txt) > 30 and len(txt) < 5000:
                    description = txt
                    break

    # Details
    details = ""
    details_header = None
    for header in soup.find_all(["h2", "h3", "h4", "div"]):
        txt = header.get_text(strip=True)
        if txt == "Details":
            details_header = header
            break
    if details_header:
        next_el = details_header.find_next_sibling()
        if next_el:
            details = next_el.get_text("\n", strip=True)

    # Project Logs
    logs = []
    # Look for "Project Logs" header
    logs_header = None
    for header in soup.find_all(["h2", "h3", "h4", "div", "span"]):
        txt = header.get_text(strip=True)
        if "Project Logs" in txt or "project log" in txt.lower():
            logs_header = header
            break

    if logs_header:
        # Logs are usually in a container after the header
        # Each log has a title and body
        log_container = logs_header.find_parent()
        if log_container:
            # Try to find individual log entries
            for log_el in log_container.find_all(["div", "article"], recursive=False):
                log_title_el = log_el.find(["h2", "h3", "h4", "strong", "a"])
                if log_title_el:
                    log_title = log_title_el.get_text(strip=True)
                    log_body = log_el.get_text("\n", strip=True)
                    # Remove title from body
                    if log_title in log_body:
                        log_body = log_body.replace(log_title, "", 1).strip()
                    if log_body and len(log_body) > 10:
                        logs.append({
                            "title": log_title,
                            "body": log_body[:2000],  # limit size
                        })

    # Also try a broader search for logs
    if not logs:
        for el in soup.find_all("div", class_=re.compile(r"log|entry|post|journal")):
            title_el = el.find(["h2", "h3", "h4", "strong"])
            title_txt = title_el.get_text(strip=True) if title_el else ""
            body_txt = el.get_text("\n", strip=True)
            if title_txt:
                body_txt = body_txt.replace(title_txt, "", 1).strip()
            if body_txt and len(body_txt) > 20:
                logs.append({
                    "title": title_txt or "Log entry",
                    "body": body_txt[:2000],
                })

    # Components (BOM)
    components = []
    comp_header = None
    for header in soup.find_all(["h2", "h3", "h4", "div"]):
        txt = header.get_text(strip=True)
        if txt == "Components" or txt == "BOM":
            comp_header = header
            break
    if comp_header:
        ul = comp_header.find_next("ul")
        if ul:
            for li in ul.find_all("li"):
                txt = li.get_text(strip=True)
                if txt:
                    components.append(txt)
        else:
            # Components may be in a table or div list
            comp_container = comp_header.find_parent()
            if comp_container:
                for row in comp_container.find_all("div", class_=re.compile(r"component|item|part")):
                    txt = row.get_text(strip=True)
                    if txt:
                        components.append(txt)

    # Files
    files = []
    files_header = None
    for header in soup.find_all(["h2", "h3", "h4", "div"]):
        txt = header.get_text(strip=True)
        if txt == "Files":
            files_header = header
            break
    if files_header:
        ul = files_header.find_next("ul")
        if ul:
            for li in ul.find_all("li"):
                txt = li.get_text(strip=True)
                if txt:
                    files.append(txt)
        else:
            for a in soup.find_all("a", href=re.compile(r"/files/|cdn\.hackaday\.io/files")):
                fname = a.get_text(strip=True)
                if fname and fname not in files:
                    files.append(fname)

    # Instructions
    instructions = []
    instr_header = None
    for header in soup.find_all(["h2", "h3", "h4", "div"]):
        txt = header.get_text(strip=True)
        if txt == "Instructions":
            instr_header = header
            break
    if instr_header:
        next_el = instr_header.find_next_sibling()
        while next_el and next_el.name in ["div", "p", "ul", "ol"]:
            txt = next_el.get_text("\n", strip=True)
            if txt:
                instructions.append(txt)
            next_el = next_el.find_next_sibling()

    # Images
    images = []
    for img in soup.find_all("img"):
        src = img.get("src", "")
        if src and "hackaday.io" in src and "logo" not in src and "icon" not in src:
            images.append(src)
    for meta_img in soup.find_all("meta", property="og:image"):
        src = meta_img.get("content", "")
        if src and src not in images:
            images.insert(0, src)

    return {
        "project_id": pid,
        "url": url,
        "title": title,
        "summary": summary,
        "author": author,
        "description": description,
        "details": details,
        "tags": tags,
        "logs": logs,
        "components": components,
        "files": files,
        "instructions": instructions,
        "images": images[:15],
        "log_count": len(logs),
        "component_count": len(components),
        "scraped_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }


async def scrape_listing_pages(client: httpx.AsyncClient, semaphore: asyncio.Semaphore) -> list:
    """Scrape multiple listing pages to gather project URLs."""
    all_links = []
    page = 1
    seen = set()

    while len(all_links) < MAX_PROJECTS:
        url = f"{LISTING_URL}?page={page}"
        print(f"[LIST] Fetching page {page}: {url}")
        html = await fetch(client, url)
        if not html:
            break

        links = extract_project_links_from_listing(html)
        new_links = [u for u in links if u not in seen]
        if not new_links:
            print(f"  [INFO] No new projects on page {page}, stopping")
            break

        for u in new_links:
            seen.add(u)
            all_links.append(u)
            if len(all_links) >= MAX_PROJECTS:
                break

        print(f"  [INFO] Found {len(new_links)} new projects (total: {len(all_links)})")
        page += 1
        await asyncio.sleep(RATE_LIMIT)

    return all_links[:MAX_PROJECTS]


async def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    print(f"Output directory: {OUTPUT_DIR}")

    semaphore = asyncio.Semaphore(5)
    limits = httpx.Limits(max_connections=15, max_keepalive_connections=5)
    timeout = httpx.Timeout(30.0, connect=10.0)

    async with httpx.AsyncClient(limits=limits, timeout=timeout, follow_redirects=True) as client:
        # Step 1: Gather project URLs from listing pages
        project_urls = await scrape_listing_pages(client, semaphore)
        print(f"\n[INFO] Total projects to fetch: {len(project_urls)}")

        # Step 2: Fetch each project detail page (skip existing)
        results = []
        for i, url in enumerate(project_urls, 1):
            pid = project_id_from_url(url)
            out_path = OUTPUT_DIR / f"{pid}.json"
            if out_path.exists():
                results.append(json.loads(out_path.read_text()))
                print(f"[{i}/{len(project_urls)}] SKIP {pid} (exists)")
                continue

            async with semaphore:
                print(f"[{i}/{len(project_urls)}] Fetching {url} ...")
                html = await fetch(client, url)
                if not html:
                    continue
                try:
                    data = parse_project_page(html, url)
                    if not data.get("title"):
                        print(f"  [WARN] No title extracted, skipping")
                        continue
                    results.append(data)

                    out_path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
                    print(f"  [OK] Saved {out_path.name}")

                except Exception as exc:
                    print(f"  [ERR] Parse error: {exc}")
                    import traceback
                    traceback.print_exc()

                await asyncio.sleep(RATE_LIMIT)

    total = len(results)
    print(f"\n{'='*60}")
    print(f"Total Hackaday projects downloaded: {total}")
    print(f"{'='*60}")

    # Write manifest
    manifest = {
        "source": "hackaday",
        "total_projects": total,
        "projects": [{"id": r["project_id"], "title": r["title"], "url": r["url"]} for r in results],
    }
    manifest_path = OUTPUT_DIR / "manifest.json"
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)
    print(f"Manifest saved to {manifest_path}")

    return total


if __name__ == "__main__":
    total = asyncio.run(main())
    sys.exit(0)
