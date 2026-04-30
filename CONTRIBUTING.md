# Contributing to ARK

Thanks for your interest in contributing. This document describes how to get a development environment running, the rules for submitting changes, and the structure of the knowledge base so you can add or improve records.

## Quick start

```bash
git clone https://github.com/ark-codex/ark.git
cd ark
python3.13 -m venv .venv && source .venv/bin/activate
pip install -r product/server/requirements.txt
pip install ruff pytest

# Run the test suite
pytest product/server/

# Validate the knowledge base
python3 kb/pipeline/scripts/validate_schema.py
python3 kb/pipeline/scripts/validate_xref.py

# Start the server locally
uvicorn product.server.main:app --reload
```

## Repository layout

```
ark/
├── product/server/        FastAPI runtime (vision + solver + RAG + htmx UI)
├── kb/
│   ├── pipeline/
│   │   ├── schemas/cdpo.py    Canonical data model — read this first
│   │   ├── extractors/        LLM extraction adapters
│   │   └── scripts/           Validation, packaging, helpers
│   └── output/                Generated knowledge-base records (JSON)
├── agents/                Per-agent task documents (Kimi, DeepSeek, Claude)
└── docs/                  Symlinks to active documents
```

## Coding standards

- **Python 3.13+**. Use `from __future__ import annotations` where helpful.
- **Type hints** required for all public functions.
- **Pydantic v2** for data models.
- **Lint** with `ruff check .` before submitting a PR.
- **Format** with `ruff format .`.
- **Tests** required for new features and bug fixes (`pytest product/server/`).

## Knowledge-base contributions

The knowledge base is a graph of CDPO records — Components, Devices, Projects, plus supporting collections (Materials, Tools, Skills, Phenomena, Procedures, Substitutions, Safety, Goals, Regional profiles).

To add a new record:

1. Read `kb/pipeline/schemas/cdpo.py` to find the right model.
2. Create a JSON file in the appropriate directory under `kb/output/extracted/<category>/`.
3. Use the file naming convention `<id-prefix>_<kebab-name>.json` (for example `dev_microwave-typical.json`).
4. Fill all required fields. Provide a `provenance` block with at least one source citation.
5. Validate locally: `python3 kb/pipeline/scripts/validate_schema.py`.
6. Open a PR and use the **kb-entry** issue/PR template.

Quality requirements for KB entries:

- No generic placeholders. Specify exact part numbers, sizes, voltages.
- Cite real sources (manufacturer datasheets, public-domain manuals, well-known community references).
- For procedures: include verification steps and at least one failure-mode + recovery pair.

## Pull request process

1. **Fork** the repository.
2. **Create a branch** from `main`: `git checkout -b feature/short-description`.
3. **Write the change**, including tests where applicable.
4. **Run the suite** locally: `ruff check . && pytest product/server/`.
5. **Commit** using Conventional Commits (`feat:`, `fix:`, `docs:`, `refactor:`, `test:`, `chore:`).
6. **Push** and open a PR against `main`.
7. The CI will run `ruff`, `pytest`, and `validate_schema.py`. All must pass.
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
