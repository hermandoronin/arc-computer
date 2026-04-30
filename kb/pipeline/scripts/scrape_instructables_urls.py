#!/usr/bin/env python3
"""Scrape Instructables project URLs via Typesense API (no browser needed)."""

import asyncio
import json
import re
import sys
from pathlib import Path

import httpx

SEED_FILE = Path("/home/user/aisurvive/kb/pipeline/scripts/instructables_urls.json")
TARGET_PER_CATEGORY = 400
SEARCH_URL = "https://www.instructables.com/api_proxy/search/collections/projects/documents/search"

CATEGORY_FILTERS = {
    "electronics": "status:=PUBLISHED && featureFlag:=true && category:=Circuits && channel: [Electronics] && indexTags:!=external",
    "workshop": "status:=PUBLISHED && featureFlag:=true && category:=Workshop && indexTags:!=external",
    "homestead": "status:=PUBLISHED && featureFlag:=true && category:=Living && indexTags:!=external",
}

BASE_PARAMS = {
    "q": "*",
    "query_by": "title,stepBody,screenName",
    "sort_by": "views:desc",
    "include_fields": "title,urlString,views,favorites",
    "per_page": 50,
}


def extract_api_key() -> str:
    resp = httpx.get(
        "https://www.instructables.com/",
        headers={"User-Agent": "Mozilla/5.0"},
        follow_redirects=True,
        timeout=15,
    )
    m = re.search(r'typesenseApiKey":"([^"]+)"', resp.text)
    if not m:
        raise RuntimeError("Could not extract Typesense API key")
    return m.group(1)


async def main():
    api_key = extract_api_key()
    print(f"API key: {api_key[:20]}...")

    seed = {}
    if SEED_FILE.exists():
        seed = json.loads(SEED_FILE.read_text())
        print(f"Existing seed: {sum(len(v) for v in seed.values())} URLs")

    async with httpx.AsyncClient() as client:
        for category, filter_by in CATEGORY_FILTERS.items():
            existing = seed.get(category, [])
            needed = TARGET_PER_CATEGORY - len(existing)
            if needed <= 0:
                print(f"[{category}] Already have {len(existing)} URLs, skipping")
                continue

            urls = list(dict.fromkeys(existing))  # dedupe existing
            page = 1

            print(f"\n[{category}] Collecting up to {TARGET_PER_CATEGORY} URLs...")

            while len(urls) < TARGET_PER_CATEGORY:
                params = dict(BASE_PARAMS)
                params["page"] = page
                params["filter_by"] = filter_by

                resp = await client.get(
                    SEARCH_URL,
                    params=params,
                    headers={
                        "User-Agent": "Mozilla/5.0",
                        "x-typesense-api-key": api_key,
                    },
                    timeout=15,
                )
                resp.raise_for_status()
                data = resp.json()
                hits = data.get("hits", [])
                found = data.get("found", 0)

                if not hits:
                    break

                for hit in hits:
                    doc = hit.get("document", {})
                    url_string = doc.get("urlString", "")
                    if url_string:
                        url = f"https://www.instructables.com/{url_string}/"
                        if url not in urls:
                            urls.append(url)

                print(f"  [{category}] Page {page}: {len(urls)}/{TARGET_PER_CATEGORY} (total avail: {found})")
                page += 1

                if (page - 1) * 50 >= found:
                    break

            seed[category] = urls[:TARGET_PER_CATEGORY]
            print(f"  [{category}] Done: {len(seed[category])} URLs")

    SEED_FILE.parent.mkdir(parents=True, exist_ok=True)
    SEED_FILE.write_text(json.dumps(seed, indent=2, ensure_ascii=False) + "\n")
    total = sum(len(v) for v in seed.values())
    print(f"\n{'='*60}")
    print(f"Seed file saved: {SEED_FILE}")
    print(f"Total URLs: {total}")
    print(f"By category: { {k: len(v) for k, v in seed.items()} }")
    return total


if __name__ == "__main__":
    total = asyncio.run(main())
    sys.exit(0)
