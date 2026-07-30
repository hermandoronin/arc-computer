# Contributing to ARC.computer

Thanks for your interest in contributing. This document describes how to get a development environment running, the rules for submitting changes, and the structure of the knowledge base so you can add or improve records.

## Quick start

> This repository contains the knowledge-base extraction pipeline only. The
> ARC solver service is not published here — see the README.

```bash
git clone https://github.com/hermandoronin/arc-computer.git
cd arc-computer
python3.13 -m venv .venv && source .venv/bin/activate
pip install pydantic zstandard httpx ruff

# Validate the knowledge base (needs KB records under kb/output/)
python3 kb/pipeline/scripts/validate_xref.py
python3 kb/pipeline/scripts/validate_coverage.py
```

There is no test suite in this repository yet.

## Repository layout

```
arc-computer/
├── kb/
│   ├── pipeline/
│   │   ├── schemas/cdpo.py    Canonical data model — read this first
│   │   ├── extractors/        LLM extraction adapters
│   │   └── scripts/           Validation, packaging, helpers
│   └── output/                Generated knowledge-base records (JSON, gitignored)
├── docs/                  Deployment and firmware-validation notes
└── scripts/               Corpus bootstrap helper
```

## Coding standards

- **Python 3.13+**. Use `from __future__ import annotations` where helpful.
- **Type hints** required for all public functions.
- **Pydantic v2** for data models.
- **Lint** with `ruff check .` before submitting a PR.
- **Format** with `ruff format .`.
- **Tests**: there is no suite yet. If you add one, wire it into `.github/workflows/ci.yml` in the same PR.

## Knowledge-base contributions

The knowledge base is a graph of CDPO records — Components, Devices, Projects, plus supporting collections (Materials, Tools, Skills, Phenomena, Procedures, Substitutions, Safety, Goals, Regional profiles).

To add a new record:

1. Read `kb/pipeline/schemas/cdpo.py` to find the right model.
2. Create a JSON file in the appropriate directory under `kb/output/extracted/<category>/`.
3. Use the file naming convention `<id-prefix>_<kebab-name>.json` (for example `dev_microwave-typical.json`).
4. Fill all required fields. Provide a `provenance` block with at least one source citation.
5. Validate locally: `python3 kb/pipeline/scripts/validate_xref.py`.
6. Open a PR and use the **kb-entry** issue/PR template.

Quality requirements for KB entries:

- No generic placeholders. Specify exact part numbers, sizes, voltages.
- Cite real sources (manufacturer datasheets, public-domain manuals, well-known community references).
- For procedures: include verification steps and at least one failure-mode + recovery pair.

## Pull request process

1. **Fork** the repository.
2. **Create a branch** from `main`: `git checkout -b feature/short-description`.
3. **Write the change**, including tests where applicable.
4. **Lint** locally: `ruff check .`.
5. **Commit** using Conventional Commits (`feat:`, `fix:`, `docs:`, `refactor:`, `test:`, `chore:`).
6. **Push** and open a PR against `main`.
7. CI currently fails on every run: both workflows install `product/server/requirements.txt`, a path that does not exist in this repository. Fixing them requires either publishing the server or rewriting the workflows.
8. A maintainer will review within ~5 business days.

## Reporting issues

Use the GitHub issue templates:

- **Bug** — something is broken.
- **Feature** — proposing new functionality.
- **KB entry** — suggesting a new knowledge-base record.

For security issues, see `SECURITY.md` — do not open a public issue.

## Code of conduct

This project follows the Contributor Covenant v2.1. See `CODE_OF_CONDUCT.md`. Be kind. Be specific. Disagree with the idea, not the person.

## License

By contributing, you agree that your contributions will be licensed under:

- **Apache-2.0** for code (see `LICENSE`).
- **CC-BY-4.0** for knowledge-base content (see `LICENSE-KB`).
- **MIT** for adapter and scraper scripts (see `LICENSE-ADAPTERS`).

You retain copyright; you are granting the project a license to redistribute under those terms.
