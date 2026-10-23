<div align="center">

# ARC.computer

### Офлайновая база знаний для сборки инструментов из бытового электронного хлама.

> *Knowledge that works anywhere — without depending on someone else's server.*

[![License: Apache 2.0](https://img.shields.io/badge/Code-Apache%202.0-blue.svg)](LICENSE)
[![License: CC-BY 4.0](https://img.shields.io/badge/KB-CC--BY--4.0-green.svg)](LICENSE-KB)
[![License: MIT](https://img.shields.io/badge/Adapters-MIT-orange.svg)](LICENSE-ADAPTERS)
[![Python 3.13+](https://img.shields.io/badge/python-3.13+-blue.svg)](https://www.python.org/)
[![Status: browser MVP](https://img.shields.io/badge/status-browser%20MVP-orange.svg)](product/web/README.md)

</div>

---

## Что лежит в этом репозитории

**Пайплайн базы знаний и браузерный MVP в [`product/web/`](product/web/README.md).**

Новый Field Manual: восемь стартовых сборок, инвентарь с количеством, подбор по
точным ID, списки недостающего, доноры, экспорт и офлайн-кэш. Поиск охватывает
1 225 проектов, 1 115 разборов (400 уникальных ID устройств) и 55 414 компонентов.
API-ключи для работы сайта не нужны.

Приложение ARC — FastAPI-сервис с htmx-интерфейсом, reverse-BOM solver и
vision-клиентом — **в этом репозитории не опубликовано**. Его нет ни в рабочем
дереве, ни в одном коммите. Предыдущая версия README описывала его так, будто
он поставляется вместе с репозиторием; это было неправдой.

| Каталог | Что это | Состояние |
|---|---|---|
| `kb/pipeline/schemas/` | Онтология CDPO (Component–Device–Project) на Pydantic v2, включая модель firmware genome | работает, импортируется |
| `kb/pipeline/extractors/` | LLM-адаптеры извлечения + промпты, оценка стоимости, сборщик финального пакета (tar + zstd) | запускается при наличии API-ключей и входных данных |
| `kb/pipeline/scripts/` | Скрейперы (iFixit, Instructables, Hackaday, YouTube), валидаторы, построение индекса, упаковка | запускается |
| `scripts/bootstrap-kb.sh` | Массовая загрузка корпусов (Kiwix ZIM, KiCad, archive.org, Appropedia, Wikidata, OpenRepair) | запускается |
| `docs/` | Заметки по деплою и валидации прошивок | справочно |

В MVP есть семь тестов логики и целостности корпуса, а также проверка статических
ресурсов. Старые workflow, ссылавшиеся на отсутствующий сервер, удалены ранее.

## Задача

Инструменты «AI для железа» говорят, что **купить**. Универсальная языковая
модель придумывает несуществующие номиналы. Офлайновые энциклопедии ищут, но не
рассуждают об инвентаре.

Цель ARC — машиночитаемый офлайновый корпус знаний, по которому можно ответить
«что я могу собрать из того, что уже есть» без сети. Этот репозиторий содержит
ту часть, которая этот корпус собирает.

## Три режима (замысел неопубликованного solver'а)

1. **Reverse-BOM** — «у меня X, хочу Y» → компоненты из имеющегося хлама и план сборки
2. **Forward-BOM** — «хочу собрать Y» → BOM + где такие компоненты обычно найти
3. **Discovery** — «у меня X» → проекты, которые из этого собираются

В браузерном MVP реализован ограниченный подбор по явному составу и точным ID.
Общий движок совместимости, локальная LLM и распознавание по фото пока отсутствуют.

## База знаний

KB собирается пайплайном из `kb/pipeline/`. Компактный браузерный снимок теперь
находится в `product/web/dist/data/`. Корпус восстановлен 23.10.2026 из
`/run/media/user/External/ark/`. Контрольная сумма финального архива совпала с
файлом SHA-256. [Отчёт восстановления](product/web/research/data-audit.json).

| Категория | Записей (локальная сборка) |
|---|--:|
| **Components** (canonical) | 55,414 |
| **Devices** (разборы / уникальные ID) | 1,115 / 400 |
| **Materials** (DIY recipes) | 1,242 |
| **Projects** (recipes) | 1,225 |
| **Tools** (with build-from-junk paths) | 716 |
| **Phenomena** (physics for solver) | 301 |
| **Skills** (with prerequisites) | 203 |
| **Goals** (top-level) | 50 |
| **Regional profiles** (mains/radio/etc) | 50 |

В финальном пакете каталоги проектов и устройств пустые; они восстановлены из
`extracted-bulk/`. Прежние количества замен, профилей безопасности и прошивок этой
проверкой не подтверждены. Ссылки проектов восстановлены из сырого архива, но
содержание всего корпуса не проверено. Непроверенные инструкции сборки исключены
из веб-снимка. Пространства ID `comp:` и `cmp:` не приравниваются автоматически.

`kb/pipeline/scripts/package.sh` называет пакет `ark-kb-v0.1.tar.zst`. Старый
README предлагал скачать `releases/latest/download/arc-kb.tar.zst` (в русской
версии — `ark-kb.tar.zst`); ссылка отдаёт 404, у релиза `v0.1.0` нет ассетов,
поэтому она удалена, а не переименована.

## Quickstart

```bash
git clone https://github.com/hermandoronin/arc-computer.git
cd arc-computer

pip install pydantic zstandard httpx

# Посмотреть модель данных
python -c "from kb.pipeline.schemas.cdpo import *; print('CDPO models loaded')"

# Загрузить исходные корпуса (большие, нужно место на диске)
bash scripts/bootstrap-kb.sh

# Запустить экстрактор (нужен API-ключ LLM)
python kb/pipeline/extractors/run_device_extractor.py --help
```

Запуск браузерного MVP:

```bash
cd product/web
npm run dev
# http://127.0.0.1:3037
npm test
python3 scripts/check_static.py
```

Нужен Python 3; для тестов — Node.js 20+. Установка npm-зависимостей не требуется.
Предпросмотр Chrome был отклонён инструментом доступа, поэтому визуальная проверка
компьютера/телефона, реальные клики и офлайн-перезагрузка не подтверждены.
Физические сборки не проходили стендовые испытания. [Документация MVP](product/web/README.md).

## Stack

- **Модель данных:** Pydantic v2 (`kb/pipeline/schemas/cdpo.py`)
- **Извлечение:** LLM-адаптеры поверх скачанных корпусов, промпты в `kb/pipeline/extractors/prompts/`
- **Упаковка:** tar + zstd (`kb/pipeline/scripts/package.sh`)
- **Валидация:** cross-reference, coverage, anti-laziness regex, компиляция прошивок через simavr/avr-gcc/arm-none-eabi

## Архитектура

```
arc-computer/
├── README.md
│
├── kb/
│   ├── STRATEGY.md         ← two-zone storage plan
│   ├── pipeline/
│   │   ├── schemas/cdpo.py ← canonical Pydantic data model
│   │   ├── extractors/     ← LLM extraction adapters + промпты
│   │   └── scripts/        ← scrapers, validators, packagers
│   └── output/             ← .gitignore'd, не опубликовано
│
├── docs/                   ← deployment, firmware validation
└── scripts/                ← bootstrap корпусов
```

## Roadmap

- [x] **Браузерный Field Manual MVP** — инвентарь, сборки, восстановленный корпус, экспорт и офлайн-кэш

- [x] **Модель данных CDPO** — Pydantic-схемы, включая firmware genome
- [x] **Пайплайн извлечения** — скрейперы, LLM-экстракторы, валидаторы, упаковщик
- [ ] **Опубликовать KB** — ассет релиза, воспроизводимая сборка
- [ ] **Опубликовать solver** — FastAPI-сервис и интерфейс, описанные выше
- [ ] **v0.2** — content packs (Marine, HAM, Homestead, 3D-printer salvage)
- [ ] **v0.3** — Raspberry Pi 5 kit с предзагруженной KB, vision inventory
- [ ] **v1.0** — многоязычная KB, mesh между устройствами

## Documentation

| Document | What |
|---|---|
| [`kb/STRATEGY.md`](kb/STRATEGY.md) | Storage tiering (hot zone on device, cold on dev disk) |
| [`docs/DEPLOYMENT.md`](docs/DEPLOYMENT.md) | Заметки по деплою неопубликованного сервера |
| [`docs/FIRMWARE-VALIDATION.md`](docs/FIRMWARE-VALIDATION.md) | simavr/qemu/avr-gcc setup |

## Contributing

See [`CONTRIBUTING.md`](CONTRIBUTING.md).

- **Code style:** ruff (Python 3.13+)
- **KB entries** follow [`kb/pipeline/schemas/cdpo.py`](kb/pipeline/schemas/cdpo.py)
- **Conventional Commits**

Issue templates: [bug](.github/ISSUE_TEMPLATE/bug.md) · [feature](.github/ISSUE_TEMPLATE/feature.md) · [knowledge-base entry](.github/ISSUE_TEMPLATE/kb-entry.md).

Community standards: [`CODE_OF_CONDUCT.md`](CODE_OF_CONDUCT.md) (Contributor Covenant 2.1). Security disclosures: [`SECURITY.md`](SECURITY.md).

## License

| Scope | License | File |
|---|---|---|
| Code (pipeline, extractors, validators) | Apache-2.0 | [`LICENSE`](LICENSE) |
| Knowledge-base content | CC-BY-4.0 | [`LICENSE-KB`](LICENSE-KB) |
| Adapters and scrapers | MIT | [`LICENSE-ADAPTERS`](LICENSE-ADAPTERS) |

Per-record provenance metadata in KB JSONs may indicate upstream sources (iFixit content under CC-BY-NC-SA, manufacturer datasheets, etc) — respect upstream licenses when redistributing.

## Stay in touch

- Issues — открыть [на GitHub](https://github.com/hermandoronin/arc-computer/issues)

---

<div align="center">

**Built for people who build, fix, and grow things — anywhere, anytime.**

[Get involved](CONTRIBUTING.md) · [Report security issue](SECURITY.md)

</div>
