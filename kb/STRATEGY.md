# KB Storage Strategy — Two-Zone Architecture

## Principle

Work in two zones: **HOT** (on-device, 10–20 GB compressed) and **COLD** (on the external disk).

### Storage budget (verified via `lsblk`):
- **Internal `/`** — 37 GB free → code + current extractions only
- **External NTFS partition** — 347 GB → primary COLD raw archive
- **External ext4 partition** (96 GB) → ideal for staging / DuckDB / Qdrant build
- **Total COLD space: ~440 GB** — not terabytes; **trim aggressively** at bootstrap

```
┌──────────────────────────────────┐    ┌──────────────────────────────────┐
│  COLD ZONE (external ~440 GB)    │    │  HOT ZONE (device NVMe 1 TB)     │
│  Dev workstation                 │───▶│  Production ARC device           │
│                                  │    │                                  │
│  - iFixit RAW dump (~15 GB)      │    │  - Compressed KB (~15 GB):       │
│  - Survivor Library (~30 GB)     │    │    - structured graph (kuzu)     │
│  - Datasheets PDFs (~30 GB)      │    │    - vector index (Qdrant)       │
│  - YouTube transcripts only      │    │    - BM25 index (Tantivy)        │
│  - Wikipedia ZIM no-pic (~50 GB) │    │  - LLM weights (Qwen 14B Q4 ~9GB)│
│  - Instructables electronics     │    │  - Vision model (Qwen VL Q4 ~5GB)│
│  - Working files / staging       │    │  - OS + runtime (~5 GB)          │
│  - Extraction outputs            │    │  - User data + logs              │
│                                  │    │                                  │
│  Total ~250–300 GB               │    │  Total ~35–40 GB / 1 TB          │
└──────────────────────────────────┘    └──────────────────────────────────┘
        ▲                                          ▲
        │                                          │
   ┌──────────┐                              ┌──────────┐
   │ scrapers │                              │  user    │
   │ + batch  │                              │  queries │
   │ extract  │                              │          │
   └──────────┘                              └──────────┘
```

## HOT zone (what actually ships on the device)

### 1. Knowledge graph — kuzu (~3 GB)
- **Devices** — ~5,000 entries (top-popularity)
- **Components** — ~50,000 canonical entries (KiCad lib + Wikidata subset)
- **Projects** — ~5,000 curated recipes
- **Edges** — `CONTAINS` / `REQUIRES` / `SUBSTITUTES` / `PRODUCES` — 5–10 million

### 2. Vector index — Qdrant (~2 GB)
- bge-m3 embeddings (1,024-dim) for every node in the graph
- Exactly one embedding per node — no duplication

### 3. BM25 index — Tantivy (~1 GB)
- Full-text search over descriptions, names, synonyms

### 4. Critical PDFs (~3 GB)
- Top-100 US Army FMs (signal corps, engineering, medical only)
- Hesperian *Where There Is No Doctor* + *Where There Is No Dentist*
- Top-50 datasheets (TL431, NE555, LM358, ATmega328, ESP32, common MOSFETs)
- 20–30 reference handbooks (stored as **DjVu**, not PDF — 5× smaller)

### 5. Project recipes as Markdown (~1 GB)
- 5,000 projects in plain Markdown with YAML front-matter
- Compresses ~5× under zstd → ~200 MB on disk

### 6. Firmware templates (~500 MB)
- Ready `.ino` / `.c` / Rust skeletons for common tasks
- Pre-compiled `.hex` for the most common MCUs

### 7. Models — heaviest on disk (~14 GB)
- Qwen 2.5 14B Q4_K_M GGUF — ~9 GB
- Qwen 2.5 VL 7B Q4 — ~5 GB

**Total HOT: ~25 GB** — comfortable on a 1 TB NVMe with headroom for logs / updates / user data.

---

## COLD zone (everything on the external disk)

### Raw archives (~250–300 GB target)

| Source | Size | Priority | Method |
|---|---|---|---|
| iFixit guides + teardowns (JSON only, no photos) | ~10–15 GB | 🔴 must | API |
| Survivor Library (electronics + health + farming sections, not full) | ~30–40 GB | 🔴 must | targeted `wget` |
| KiCad libraries (canonical components) | ~5 GB | 🔴 must | `git clone` |
| Wikidata electronic-component subset | ~500 MB | 🔴 must | SPARQL |
| US Army FMs (top-100 curated) | ~5 GB | 🔴 must | `armypubs` |
| Hesperian medical | ~500 MB | 🔴 must | direct |
| Appropedia + WikEM | ~3 GB | 🟡 high | Special:Export + ZIM |
| Open Repair Data (CSV) | ~1 GB | 🟡 high | direct |
| Hackaday.io API (electronics-only) | ~5 GB | 🟡 high | API |
| Datasheets — top-2,000 critical (not full) | ~30 GB | 🟡 high | targeted scrape |
| Instructables — electronics + homestead categories only | ~30–40 GB | 🟡 high | filtered Scrapy |
| YouTube teardowns — **Whisper transcripts only**, no video | ~5 GB | 🟡 high | `yt-dlp --write-auto-subs --skip-download` |
| OSE / GVCS docs | ~5 GB | 🟢 nice | git |
| Kiwix `wikipedia_en_all_nopic` (compact) | ~50 GB | 🟢 nice | kiwix.org |
| Civil Defence vintage manuals | ~3 GB | 🟢 nice | archive.org |

**What we cut from the original plan** (doesn't fit in 440 GB):
- ❌ Wikipedia EN full dumps (100 GB) → keep only `_nopic` ZIM (50 GB)
- ❌ Instructables full crawl (200 GB) → only electronics / homestead categories
- ❌ Datasheets full aggregation (500 GB) → top-2,000 only
- ❌ YouTube raw video (300 GB) → subtitles only (5 GB)
- ❌ Full Hackaday.io archive → tagged-electronics only

### Extraction outputs (~10–30 GB)
- LLM-extracted structured JSONL
- Intermediate files used to build the HOT zone

### Staging / working
- DuckDB Parquet tables for normalisation
- Embedding cache
- Test outputs

---

## Smart storage tricks (compression heuristics)

### Trick #1 — Text descriptors instead of images in KB
**Problem:** storing a photo of every component → terabytes.
**Solution:** in KB, store only **textual descriptors**:
```yaml
component: TL431
package: TO-92
appearance: "three-lead, flat side bears 'TL431' in black ink, ~5×4×2 mm"
visual_aliases: ["resembles BC547, distinguished by the marking", "may also be SOT-23 SMD"]
```
The vision LLM compares the user's photo against the descriptor at runtime. No raw photos in HOT.
**Savings: ~99 % on visual recognition.**

### Trick #2 — LLM summary instead of raw text
**Problem:** storing full iFixit guides (200 KB HTML × 90k = ~18 GB).
**Solution:** compress to a structured summary via LLM:
```yaml
guide: ifixit-12345
device: HP DeskJet F2280
summary: "3-in-1 inkjet, 2008. Disassembly via 4 bottom screws + lid clips. Useful: pickup solenoid, carriage stepper, 32 V/0.4 A PSU. Fragile FFC ribbons."
extracted_components: [...]
```
**Savings: ~99×** (200 KB → 2 KB).

### Trick #3 — DjVu instead of PDF for scanned books
Old scanned books in DjVu take **5–10× less space** at comparable readability.
**Savings:** Survivor Library 100 GB PDF → ~15–20 GB DjVu.

### Trick #4 — Indexed PDFs with lazy load
Don't parse every datasheet up-front. Store the PDF + metadata index. On request, pull the relevant PDF and run it through the LLM at runtime.

```
hot/datasheets-index.parquet         (metadata only, ~10 MB)
hot/datasheets-most-used.tar.zst     (top-200 datasheets, ~100 MB)
cold/datasheets-full/                (the remaining 500 K on the dev disk)
```

### Trick #5 — Embedding deduplication
One canonical record = one embedding. No language duplication — store a translation table in the graph; the embedding is shared via the multilingual bge-m3.
**Savings:** 4-language KB at 1-language storage cost + ~5 MB of translations.

### Trick #6 — Quantised vision dataset
If we ever assemble a custom vision dataset:
- Store **embeddings** of components, not raw photos
- 1 embedding (768 floats × fp16) ≈ 1.5 KB vs ~500 KB raw photo
- 100 K components × 1.5 KB = 150 MB vs 50 GB

### Trick #7 — Shared model across NLP tasks
Not separate models for extraction / retrieval / generation. One Qwen 14B Q4 plus task-specific prompts. Saves 20+ GB.

### Trick #8 — Compressed graph (kuzu native)
kuzu stores property graphs more efficiently than general-purpose DBs (Neo4j on the same data is 3–5× larger).

### Trick #9 — On-device updates via diff
KB updates ship over mesh as **diffs only** (CRDT-style). The full KB never travels. Update payloads are kilobytes.

### Trick #10 — Hot/Warm/Cold tiering on-device
NVMe 1 TB layout:
- `/hot` — 25 GB always-resident (mmap'd in RAM)
- `/warm` — 100 GB extended (fetched on demand)
- `/cold` — remaining free space (user-loaded extras like regional packs)

---

## Pipeline: COLD → HOT (one-time pre-flash)

```
[external disk: raw sources]
        ↓
[Stage 1: ingest]
        ↓
[external disk: normalised JSONL staging]
        ↓
[Stage 2-6: dedupe + LLM extract + validate]
        ↓
[external disk: full KB]
        ↓
[Stage 7: COMPACT — pick top-N, summarise, compress]
        ↓
[device NVMe: HOT zone, ~25 GB]
```

Stage 7 is our **lossy compression of knowledge**. A dedicated compactor:
1. Ranks devices/components/projects by popularity + utility score
2. Keeps full records for the top 5,000
3. Keeps only canonical id + key params for the long tail (5,000–50,000)
4. Compresses long projects into LLM summaries
5. Datasheets — index + top-200 PDFs only

---

## Update strategy

| Update type | Delivery |
|---|---|
| KB delta (new projects, fixes) | mesh / SD card / USB cable, monthly |
| Model update | rare, via USB / SD (~10 GB file) |
| Software update | A/B partitions, USB or Wi-Fi-AP mode |
| User-contributed projects | local commit, mesh-sync when available |

---

## Decisions to confirm

- [ ] External disk: **2 TB sufficient?** (if 1 TB — drop YouTube transcripts; keep only top-100 GB of datasheets)
- [ ] Final target HOT zone: **25 GB** ✅ (leaves 975 GB on NVMe for the user)
- [ ] Trick #1 (text descriptors) — accept as the baseline for vision? It's the single biggest space saving.
- [ ] Trick #4 (lazy datasheet load) — acceptable that offline users can't see uncached datasheets, or pre-stage everything in `warm`?
