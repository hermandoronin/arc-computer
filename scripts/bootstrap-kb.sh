#!/usr/bin/env bash
# bootstrap-kb.sh — initial KB download to external disk
# Target: ~150-300 GB raw on external, deduplicated and ready for extraction
# Usage: EXTERNAL=/mnt/external ./bootstrap-kb.sh [stage]
# Stages: all (default) | foundation | scrape | dedupe

set -euo pipefail

EXTERNAL="${EXTERNAL:-/mnt/external}"
KB_ROOT="$EXTERNAL/ark-kb"
LOG="$KB_ROOT/bootstrap.log"

# colors
R='\033[0;31m'; G='\033[0;32m'; Y='\033[1;33m'; B='\033[0;34m'; N='\033[0m'
log() { echo -e "${B}[$(date +%H:%M:%S)]${N} $*" | tee -a "$LOG"; }
warn() { echo -e "${Y}[WARN]${N} $*" | tee -a "$LOG"; }
err() { echo -e "${R}[ERR]${N} $*" | tee -a "$LOG"; exit 1; }
ok() { echo -e "${G}[OK]${N} $*" | tee -a "$LOG"; }

# preflight
[ -d "$EXTERNAL" ] || err "External disk not found at $EXTERNAL — set EXTERNAL=/path"
mkdir -p "$KB_ROOT"/{raw,staging,extracted,logs}
mkdir -p "$KB_ROOT"/raw/{ifixit,survivor-library,kicad,wikidata,wikipedia,kiwix,army-fm,hesperian,appropedia,datasheets,instructables,hackaday,youtube,open-repair,journals-ru,civildefense,ose-gvcs}

free_gb=$(df -BG "$EXTERNAL" | awk 'NR==2 {print $4}' | tr -d 'G')
log "External disk free: ${free_gb}GB at $EXTERNAL"
[ "$free_gb" -ge 200 ] || warn "Less than 200GB free — будет тесно"

# Required tools
need() { command -v "$1" >/dev/null 2>&1 || err "Missing tool: $1 — установи и повтори"; }
for t in wget aria2c curl jq git python3 yt-dlp; do need "$t"; done

# ==============================================================
# STAGE 1: FOUNDATION (public domain / CC, ~80GB)
# ==============================================================
stage_foundation() {
  log "=== STAGE 1: FOUNDATION ==="

  # 1.1 KiCad libraries (canonical electronic components)
  log "-> KiCad libraries (~5GB)"
  cd "$KB_ROOT/raw/kicad"
  for repo in kicad-symbols kicad-footprints kicad-packages3D; do
    [ -d "$repo" ] || git clone --depth 1 "https://gitlab.com/kicad/libraries/$repo.git"
  done
  ok "KiCad done"

  # 1.2 US Army Field Manuals (public domain)
  log "-> US Army FM batch (~5GB)"
  cd "$KB_ROOT/raw/army-fm"
  if [ ! -f .done ]; then
    aria2c -x 8 -j 4 -i - <<EOF
https://archive.org/download/militarymanuals/militarymanuals_archive.torrent
EOF
    # альтернатива если торрент мёртв:
    # wget -r -np -nH --cut-dirs=2 -A pdf "https://armypubs.army.mil/pub/eppubs/Doctrine_/"
    touch .done
  fi
  ok "Army FM done"

  # 1.3 Hesperian (medical, CC)
  log "-> Hesperian Where There Is No Doctor/Dentist (~500MB)"
  cd "$KB_ROOT/raw/hesperian"
  for url in \
    "https://en.hesperian.org/hhg/Where_There_Is_No_Doctor:Where_There_Is_No_Doctor_(2021).pdf" \
    "https://en.hesperian.org/hhg/Where_There_Is_No_Dentist:Where_There_Is_No_Dentist_(2021).pdf" \
    "https://en.hesperian.org/hhg/A_Book_for_Midwives" \
    "https://en.hesperian.org/hhg/A_Community_Guide_to_Environmental_Health" \
    "https://en.hesperian.org/hhg/Disabled_Village_Children"; do
    wget -c "$url" || warn "Skip $url"
  done
  ok "Hesperian done"

  # 1.4 Appropedia dump
  log "-> Appropedia dump (~2GB)"
  cd "$KB_ROOT/raw/appropedia"
  # официально рекомендуется через Special:Export, выкачиваем все статьи категории Sustainability/Engineering
  python3 - <<'PYEOF' || warn "Appropedia partial"
import urllib.request, urllib.parse, os, time
cats = ["Engineering","Electronics","Energy","Water","Health","Agriculture",
        "Sustainability","Medicine","Solar","Wind","Permaculture"]
for cat in cats:
    fn = f"appropedia-{cat}.xml"
    if os.path.exists(fn) and os.path.getsize(fn) > 1024: continue
    url = f"https://www.appropedia.org/Special:Export/Category:{urllib.parse.quote(cat)}"
    print(f"Fetching {cat}...")
    try:
        urllib.request.urlretrieve(url, fn)
        time.sleep(2)
    except Exception as e:
        print(f"  fail: {e}")
PYEOF
  ok "Appropedia done"

  # 1.5 Wikidata electronics subset (SPARQL → ~500MB)
  log "-> Wikidata electronic_component subset (~500MB)"
  cd "$KB_ROOT/raw/wikidata"
  if [ ! -f electronic_components.json ]; then
    cat > query.sparql <<'EOF'
SELECT ?item ?itemLabel ?manufacturerLabel ?packageLabel WHERE {
  ?item wdt:P31/wdt:P279* wd:Q11164.
  OPTIONAL { ?item wdt:P176 ?manufacturer. }
  OPTIONAL { ?item wdt:P186 ?package. }
  SERVICE wikibase:label { bd:serviceParam wikibase:language "en". }
}
LIMIT 100000
EOF
    curl -G "https://query.wikidata.org/sparql" \
      --data-urlencode query@query.sparql \
      -H "Accept: application/json" \
      -o electronic_components.json
  fi
  ok "Wikidata done"

  # 1.6 Kiwix ZIMs (Wikipedia, Wikivoyage, Wikibooks, Wikiversity) — multi-lang
  log "-> Kiwix ZIMs (~50GB total — Wiki EN+RU + supplementary)"
  cd "$KB_ROOT/raw/kiwix"
  for zim in \
    "https://download.kiwix.org/zim/wikipedia/wikipedia_en_all_nopic.zim" \
    "https://download.kiwix.org/zim/wikipedia/wikipedia_ru_all_nopic.zim" \
    "https://download.kiwix.org/zim/wikivoyage/wikivoyage_en_all_maxi.zim" \
    "https://download.kiwix.org/zim/wikibooks/wikibooks_en_all_maxi.zim" \
    "https://download.kiwix.org/zim/wikiversity/wikiversity_en_all_maxi.zim" \
    "https://download.kiwix.org/zim/other/appropedia_en_all_maxi.zim" \
    "https://download.kiwix.org/zim/other/wikem_en_all_maxi.zim"; do
    fn=$(basename "$zim")
    [ -f "$fn" ] && [ "$(stat -c%s "$fn")" -gt 1000000 ] || aria2c -x 8 -c "$zim" || warn "Skip $fn"
  done
  ok "Kiwix done"

  # 1.7 Civil Defense / FM-22 / vintage manuals (Internet Archive)
  log "-> Civil Defense + vintage technical (~5GB)"
  cd "$KB_ROOT/raw/civildefense"
  for id in "civildefense" "civil-defense-magazine" "FM2176SurvivalManual"; do
    [ -d "$id" ] || (mkdir -p "$id" && cd "$id" && \
      curl -fsSL "https://archive.org/metadata/$id" | jq -r '.files[] | select(.format=="Text PDF" or .format=="Image Container PDF") | .name' | \
      while read f; do wget -c "https://archive.org/download/$id/$(echo $f | sed 's/ /%20/g')"; done) || warn "Skip $id"
  done
  ok "Civil Defense done"

  # 1.8 Open Source Ecology / GVCS
  log "-> OSE / GVCS docs (~5GB)"
  cd "$KB_ROOT/raw/ose-gvcs"
  [ -d opensourceecology-wiki ] || git clone --depth 1 "https://github.com/OpenSourceEcology/opensourceecology-wiki.git" 2>/dev/null || \
    warn "OSE git clone failed — попробуй https://wiki.opensourceecology.org/wiki/Special:AllPages"
  ok "OSE done"

  # 1.9 Open Repair Data Standard
  log "-> Open Repair Alliance dataset (~1GB)"
  cd "$KB_ROOT/raw/open-repair"
  for url in \
    "https://openrepair.org/wp-content/uploads/2022/01/OpenRepairData_v0.3.csv" \
    "https://openrepair.org/wp-content/uploads/2024/01/OpenRepairData_v0.3_aggregate_202402.csv"; do
    wget -c "$url" || warn "Skip"
  done
  ok "Open Repair done"
}

# ==============================================================
# STAGE 2: SCRAPE (proprietary-ish but available, ~200GB)
# ==============================================================
stage_scrape() {
  log "=== STAGE 2: SCRAPE ==="

  # 2.1 Survivor Library (старые книги, 1850-1950, public domain)
  log "-> Survivor Library (~80-120GB)"
  cd "$KB_ROOT/raw/survivor-library"
  if [ ! -f .done ]; then
    # сайт без index, но через wget рекурсивно
    wget -r -np -nH --cut-dirs=1 -A pdf,djvu \
      --user-agent="Mozilla/5.0 ARK-bootstrap" \
      --random-wait --wait=2 \
      "http://www.survivorlibrary.com/library/" || warn "Survivor partial"
    touch .done
  fi
  ok "Survivor Library done"

  # 2.2 iFixit — через API (нужен API key)
  log "-> iFixit guides + teardowns"
  cd "$KB_ROOT/raw/ifixit"
  if [ -z "${IFIXIT_KEY:-}" ]; then
    warn "IFIXIT_KEY not set — пропускаю iFixit. Получи на ifixit.com/api/2.0"
  else
    python3 - <<PYEOF
import requests, json, os, time
KEY = os.environ["IFIXIT_KEY"]
headers = {"X-App-Id": KEY}
base = "https://www.ifixit.com/api/2.0"
# all guides
offset = 0
while True:
    r = requests.get(f"{base}/guides", params={"offset": offset, "limit": 100}, headers=headers, timeout=30)
    if r.status_code != 200: break
    data = r.json()
    if not data: break
    for g in data:
        gid = g["guideid"]
        fn = f"guide-{gid}.json"
        if os.path.exists(fn): continue
        full = requests.get(f"{base}/guides/{gid}", headers=headers, timeout=30).json()
        with open(fn, "w") as f: json.dump(full, f)
        time.sleep(0.5)
    offset += 100
    print(f"offset={offset}, last_id={data[-1].get('guideid')}")
PYEOF
  fi
  ok "iFixit step done"

  # 2.3 Instructables — через scrapy (надо отдельный crawler)
  log "-> Instructables (~150-200GB) — запусти отдельно через kb-pipeline/scrapers/instructables.py"
  warn "Instructables requires Scrapy + proxies; см. kb-pipeline/scrapers/"

  # 2.4 Hackaday.io API
  log "-> Hackaday.io API (~10GB)"
  cd "$KB_ROOT/raw/hackaday"
  if [ -z "${HACKADAY_KEY:-}" ]; then
    warn "HACKADAY_KEY not set — пропускаю. Получи на hackaday.io"
  else
    python3 - <<'PYEOF'
import requests, json, os, time
KEY = os.environ["HACKADAY_KEY"]
base = "https://api.hackaday.io/v1"
page = 1
while True:
    r = requests.get(f"{base}/projects", params={"api_key": KEY, "page": page, "per_page": 50}, timeout=30)
    data = r.json().get("projects", [])
    if not data: break
    for p in data:
        pid = p["id"]
        fn = f"proj-{pid}.json"
        if os.path.exists(fn): continue
        with open(fn, "w") as f: json.dump(p, f)
    page += 1
    print(f"page {page}")
    time.sleep(1)
PYEOF
  fi
  ok "Hackaday step done"

  # 2.5 YouTube teardown channels (только аудио + transcripts через Whisper)
  log "-> YouTube teardown channels (audio-only, ~20-50GB)"
  cd "$KB_ROOT/raw/youtube"
  for ch in \
    "https://www.youtube.com/@bigclivedotcom" \
    "https://www.youtube.com/@EEVblog" \
    "https://www.youtube.com/@MrCarlsonsLab" \
    "https://www.youtube.com/@StrangeParts" \
    "https://www.youtube.com/@AvE"; do
    name=$(basename "$ch")
    mkdir -p "$name"
    yt-dlp -f bestaudio --extract-audio --audio-format opus \
           --audio-quality 5 -o "$name/%(id)s.%(ext)s" \
           --download-archive "$name/.archive" \
           --max-downloads 200 \
           "$ch" || warn "yt-dlp partial: $name"
  done
  ok "YouTube audio done"

  # 2.6 Datasheets — через alldatasheet (top-1000)
  log "-> Datasheets (top-1000) — отдельный pipeline kb-pipeline/scrapers/datasheets.py"
  warn "Datasheets bulk требует отдельного scraper'а — см. kb-pipeline/"

  # 2.7 Российские технические журналы
  log "-> Soviet/RU technical magazines (Радио, Радиолюбитель, МК)"
  warn "Скачай вручную с RuTracker через VPN, положи в $KB_ROOT/raw/journals-ru/"
}

# ==============================================================
# STAGE 3: DEDUPE & SUMMARY
# ==============================================================
stage_dedupe() {
  log "=== STAGE 3: DEDUPE ==="
  log "Дедупликация PDF по hash + удаление мусора"
  cd "$KB_ROOT/raw"
  find . -type f -name '*.pdf' -size -10k -delete 2>/dev/null || true
  find . -type f \( -name '*.pdf' -o -name '*.djvu' \) -exec sha256sum {} \; > "$KB_ROOT/staging/file-hashes.txt"
  awk '{print $1}' "$KB_ROOT/staging/file-hashes.txt" | sort | uniq -d > "$KB_ROOT/staging/dups.txt"
  ok "Dedupe stats: $(wc -l < "$KB_ROOT/staging/dups.txt") duplicate hashes"

  log "Финальные размеры:"
  du -sh "$KB_ROOT"/raw/*/
}

# ==============================================================
# MAIN
# ==============================================================
case "${1:-all}" in
  foundation) stage_foundation ;;
  scrape) stage_scrape ;;
  dedupe) stage_dedupe ;;
  all)
    stage_foundation
    stage_scrape
    stage_dedupe
    ;;
  *)
    cat <<EOF
Usage: EXTERNAL=/mnt/external $0 [foundation|scrape|dedupe|all]

Stages:
  foundation  Public domain + CC sources (~80 GB, no API keys needed)
  scrape      iFixit, Hackaday, YouTube, Survivor (~150-250 GB, partial keys)
  dedupe      hash-based deduplication of downloaded files

Env vars:
  EXTERNAL        path to external disk (required)
  IFIXIT_KEY      iFixit API key (optional, for full guides)
  HACKADAY_KEY    Hackaday.io API key (optional)

Estimated time on 100Mbit:
  foundation: 2-4 hours
  scrape:    1-3 days (rate-limited)
  dedupe:    30-60 min
EOF
    ;;
esac

ok "Done. KB at $KB_ROOT"
du -sh "$KB_ROOT"
