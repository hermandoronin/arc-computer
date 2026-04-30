# KB Storage Strategy — Two-Zone Architecture

## Принцип

Работаем в двух зонах: **HOT** (на устройстве, 10-20GB после сжатия) и **COLD** (на внешнем диске).

### Реальный бюджет storage (проверено `lsblk`):
- **Internal Arch /**: 37 GB свободно — только код + текущие извлечения
- **External sda2 "External"** (NTFS): 347 GB — главный COLD raw archive
- **External sda3** (ext4, 96 GB): идеально для staging / DuckDB / Qdrant build
- **Total для COLD: ~440 GB** — не терабайты, **режем агрессивно** на этапе bootstrap

```
┌──────────────────────────────────┐    ┌─────────────────────────────────┐
│  COLD ZONE (external 2TB)        │    │  HOT ZONE (device NVMe 1TB)     │
│  Dev workstation                 │───▶│  Production ARK device          │
│                                  │    │                                  │
│  - iFixit RAW dump (~50GB)       │    │  - Compressed KB (~15GB):        │
│  - Survivor Library (~100GB)     │    │    - structured graph (kuzu)    │
│  - Datasheets PDFs (~500GB)      │    │    - vector index (Qdrant)      │
│  - YouTube videos+transcripts    │    │    - BM25 index (Tantivy)       │
│  - Wikipedia full dump (~100GB)  │    │  - LLM weights (Qwen 14B Q4 ~9GB)│
│  - Instructables HTML (~200GB)   │    │  - Vision model (Qwen VL Q4 ~5GB)│
│  - Working files / staging       │    │  - OS + runtime (~5GB)          │
│  - Extraction outputs            │    │  - User data + logs             │
│                                  │    │                                  │
│  Total ~1-2TB                    │    │  Total ~35-40GB / 1TB           │
└──────────────────────────────────┘    └─────────────────────────────────┘
        ▲                                          ▲
        │                                          │
   ┌──────────┐                              ┌──────────┐
   │ scrapers │                              │  user    │
   │+ batch   │                              │  queries │
   │ extract  │                              │          │
   └──────────┘                              └──────────┘
```

## HOT zone (что реально едет с устройством)

### 1. Knowledge Graph — kuzu (~3GB)
- **Devices**: ~5000 entries (top-popularity)
- **Components**: ~50 000 canonical entries (KiCad lib + Wikidata subset)
- **Projects**: ~5000 curated recipes
- **Edges**: CONTAINS / REQUIRES / SUBSTITUTES / PRODUCES — 5-10 миллионов

### 2. Vector index — Qdrant (~2GB)
- bge-m3 embeddings (1024 dim) для всех узлов графа
- Ровно 1 эмбеддинг на узел, никакой дубликации

### 3. BM25 index — Tantivy (~1GB)
- Полнотекстовый поиск по описаниям, названиям, синонимам

### 4. Critical PDFs (~3GB)
- Топ-100 Army FM (только relevant: signal corps, engineering, medical)
- Hesperian Where There Is No Doctor + Dentist
- Top-50 datasheets (TL431, 555, LM358, ATmega328, ESP32, типовые MOSFETы)
- 20-30 советских справочников (хранятся как **DjVu**, не PDF — в 5x меньше)

### 5. Project recipes как Markdown (~1GB)
- 5000 проектов в чистом MD с YAML frontmatter
- Сжимаются zstd ~5x → ~200MB на диске

### 6. Firmware templates (~500MB)
- Готовые .ino / .c / Rust шаблоны под типовые задачи
- Pre-compiled .hex для самых типовых MCU

### 7. Models — самое тяжёлое (~14GB)
- Qwen 2.5 14B Q4_K_M GGUF: ~9GB
- Qwen 2.5 VL 7B Q4: ~5GB

**Total HOT: ~25GB** — комфортно влезает в 1TB NVMe с запасом для логов/обновлений/юзер-данных.

---

## COLD zone (что у тебя на внешнем диске)

### Raw archives (~250-300GB target — fits в 347GB sda2)

| Источник | Объём | Приоритет | Решение |
|---|---|---|---|
| iFixit guides+teardowns (только JSON, без фото) | ~10-15GB | 🔴 must | API |
| Survivor Library (electronics+health+farming sections, не всё) | ~30-40GB | 🔴 must | wget targeted |
| KiCad libraries (canonical components) | ~5GB | 🔴 must | git clone |
| Wikidata electronic_component subset | ~500MB | 🔴 must | SPARQL |
| US Army FM (curated top-100) | ~5GB | 🔴 must | armypubs |
| Hesperian medical | ~500MB | 🔴 must | direct |
| Appropedia + WikEM | ~3GB | 🟡 high | Special:Export + ZIM |
| Open Repair Data (CSV) | ~1GB | 🟡 high | direct |
| Hackaday.io API (electronics-only) | ~5GB | 🟡 high | API |
| Datasheets — top-2000 critical (not full) | ~30GB | 🟡 high | targeted scrape |
| Instructables — electronics+homestead categories ONLY | ~30-40GB | 🟡 high | Scrapy filtered |
| YouTube teardown — **только Whisper transcripts**, без видео | ~5GB | 🟡 high | yt-dlp `--write-auto-subs --skip-download` |
| OSE / GVCS docs | ~5GB | 🟢 nice | git |
| Kiwix `wikipedia_en_all_nopic` (compact) | ~50GB | 🟢 nice | kiwix.org |
| Soviet/RU журналы (только электроника) | ~10-20GB | 🟢 nice | RuTracker через VPN |
| Civil Defense vintage manuals | ~3GB | 🟢 nice | archive.org |

**Что РЕЖЕМ из изначального плана** (не лезет в 440GB):
- ❌ Wikipedia EN+RU full dumps (100GB) → берём только `_nopic` ZIM 50GB
- ❌ Instructables full crawl (200GB) → только electronics/homestead категории
- ❌ Datasheets полный aggregation (500GB) → только top-2000
- ❌ YouTube видео raw (300GB) → только subtitles/transcripts (5GB)
- ❌ Полный Hackaday.io archive → только tagged electronics

**На раннем этапе можно отложить** до Kickstarter funding:
- ZIM Wikipedia (тащим только если есть свободные 50GB)
- Soviet журналы (require VPN, нудно — оставим на «после видео»)

### Extraction outputs (~10-30GB)
- LLM-extracted structured JSONL
- Промежуточные файлы для построения HOT zone

### Staging / working
- DuckDB Parquet таблицы для нормализации
- Embedding cache
- Test outputs

---

## Smart Storage Tricks (смекалка по экономии)

### Trick #1 — Text descriptors вместо изображений в KB
**Проблема:** хранить фото каждого компонента = терабайты.
**Решение:** в KB только **текстовые descriptors**:
```yaml
component: TL431
package: TO-92
appearance: "трёхвыводный, плоская сторона с маркировкой 'TL431' чёрным шрифтом, корпус ~5×4×2 мм"
visual_aliases: ["похож на BC547, отличается маркировкой", "может быть в SOT-23 SMD варианте"]
```
Vision LLM в runtime сравнивает фото юзера с descriptor'ом. Никаких raw фото в HOT.

**Экономия: ~99% места** для visual recognition.

### Trick #2 — LLM-summary вместо raw text
**Проблема:** хранить полные iFixit guides (по 200KB HTML каждый × 90k = ~18GB).
**Решение:** сжать до structured summary через LLM:
```yaml
guide: ifixit-12345
device: HP DeskJet F2280
summary: "3-в-1 струйник 2008. Разборка через 4 винта снизу + клипсы крышки. Полезное: соленоид захвата, шаговик каретки, БП 32V/0.4A. FFC-шлейфы хрупкие."
extracted_components: [...]
```
**Экономия: ~99x** (200KB → 2KB).

### Trick #3 — DjVu вместо PDF для книг
Старые сканированные книги (Survivor Library, советские справочники) в DjVu занимают **в 5-10 раз меньше** при сопоставимой читаемости.

**Экономия:** Survivor Library 100GB PDF → ~15-20GB DjVu.

### Trick #4 — Indexed PDFs с lazy load
Не парсим все datasheets заранее. Храним PDF + metadata index. При запросе — извлекаем нужный PDF и прогоняем через LLM в runtime.

```
hot/datasheets-index.parquet  ← только метаданные (~10MB)
hot/datasheets-most-used.tar.zst  ← топ-200 datasheets (~100MB)
cold/datasheets-full/  ← остальные 500K на внешнем диске для dev
```

### Trick #5 — Embedding deduplication
Одна каноническая запись = один embedding. Не дублируем для разных языков — кладём translation table в graph, embedding общий через bge-m3 (он мультиязычный).

**Экономия:** 4-language KB = 1-language storage + ~5MB translations.

### Trick #6 — Quantized vision dataset
Если когда-то соберём custom vision dataset:
- Хранить **embeddings** компонентов, не raw фото
- 1 embedding (768 floats × fp16) = ~1.5KB вместо ~500KB raw фото
- 100k компонентов × 1.5KB = 150MB вместо 50GB

### Trick #7 — Shared model для всех NLP задач
Не отдельная модель для extraction, отдельная для retrieval, отдельная для generation. Одна Qwen 14B Q4 + разные prompts. Экономия 20+ GB.

### Trick #8 — Compressed graph (kuzu native)
kuzu хранит property graph эффективнее чем общие БД (Neo4j на тех же данных весит в 3-5 раз больше).

### Trick #9 — On-device updates через diff
Обновления KB передаются через mesh **только diff'ами** (CRDT-стиль). Полная KB не пересылается. Размер update в килобайтах.

### Trick #10 — Hot/Cold tiering на самом устройстве
NVMe 1TB разбит:
- /hot — 25GB ходовой части (постоянно в RAM mmap'd)
- /warm — 100GB extended (вытаскиваем по запросу)
- /cold — оставшееся свободное (юзер сам грузит дополнительные пакеты, например regional)

---

## Pipeline: COLD → HOT (один раз перед заливкой устройства)

```
[external disk: raw sources]
        ↓
[Stage 1: ingest]
        ↓
[external disk: normalized JSONL staging]
        ↓
[Stage 2-6: dedupe + LLM-extract + validate]
        ↓
[external disk: full KB]
        ↓
[Stage 7: COMPACT — отбираем top-N, summarize, compress]
        ↓
[device NVMe: HOT zone ~25GB]
```

Stage 7 — наша **«lossy compression» of knowledge**. Пишем отдельный compactor который:
1. Ранжирует devices/components/projects по popularity + utility score
2. Для top-5000 берёт полные записи
3. Для tail (5000-50000) — только canonical id + key params
4. Долгие проекты сжимает в LLM-summary
5. Datasheets — только index + top-200 PDFs

---

## Update strategy после Kickstarter

| Тип update | Как доставляется |
|---|---|
| KB delta (новые проекты, fixes) | через mesh / SD-card / USB-кабель раз в месяц |
| Model update | редко, через USB / SD (~10GB файл) |
| Software update | A/B partitions, USB или WiFi-AP режим |
| User-contributed projects | local commit, sync через mesh при наличии |

---

## Decisions to confirm

- [ ] Внешний диск: **2TB достаточно**? (если 1TB — режем YouTube часть, datasheets оставляем top-100GB)
- [ ] Финальный target HOT zone: **25GB** ✅ (даёт запас 975GB на NVMe для юзера)
- [ ] Trick #1 (text descriptors) — принимаем как baseline для vision? Это ключевая экономия.
- [ ] Trick #4 (lazy datasheet load) — ОК что в офлайне юзер не видит редкие datasheets если их нет в hot? Или тащим все в warm?
