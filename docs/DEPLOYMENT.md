# Deployment

ARK Solver targets Fly.io. The image is multi-stage `python:3.13-slim`, the
KB lives on a 5 GB Fly volume mounted at `/data`, and the runtime keeps the
KB in memory after the first read.

## Prerequisites

- A Fly.io account: https://fly.io/app/sign-up
- The `flyctl` CLI: https://fly.io/docs/hands-on/install-flyctl/
- Docker (only if you want to test the image locally)
- An `ANTHROPIC_API_KEY` for the solver

## One-time setup

```bash
flyctl auth login
flyctl apps create ark-solver --org personal
flyctl volumes create ark_kb_data --region fra --size 5 --app ark-solver
flyctl secrets set --app ark-solver \
    ANTHROPIC_API_KEY="$ANTHROPIC_API_KEY"
```

## Deploy

Two paths — both produce the same result:

### Automatic (push to `main`)

`.github/workflows/deploy.yml` validates (ruff, pytest, KB schema), then
runs `flyctl deploy --remote-only` using the `FLY_API_TOKEN` repo secret.

### Manual

```bash
bash scripts/deploy.sh             # full pipeline incl. KB upload
bash scripts/deploy.sh --skip-kb-upload   # just rebuild + redeploy
```

The script:

1. runs `validate_schema.py`
2. (re)builds `kb/output/final/ark-kb-v0.1.tar.zst` via `package.sh`
3. uploads the tarball into `/data/` over `flyctl ssh sftp` and unpacks it
4. runs `flyctl deploy --remote-only`
5. polls `https://<app>.fly.dev/health` until it returns 200

## Local development

```bash
bash scripts/local_dev.sh
```

Bootstraps `product/server/.venv`, installs requirements, and runs uvicorn
with `--reload` watching `api/`, `kb/`, `solver/`, `templates/`, and the
on-disk KB JSON files. Default port is `8181`; override with `PORT=8080
bash scripts/local_dev.sh`.

## Rollback

```bash
flyctl releases list --app ark-solver
# pick the previous version, e.g. v42
flyctl releases rollback v42 --app ark-solver
```

If the Fly volume is corrupted, you can re-run `bash scripts/deploy.sh` —
step 3 wipes `/data/{extracted,extracted-bulk,packs,INDEX.json}` before
unpacking, so the volume converges to whatever the local tarball contains.

## Health surface

| Endpoint | Purpose |
|---|---|
| `GET /health` | Liveness + KB-loaded boolean. Used by Fly health checks. |
| `GET /kb/stats` | Per-category record counts (12 CDPO categories). |

## Known gotchas

- **Cold start** — `auto_stop_machines = true` in `fly.toml`. First request
  after idle pays the boot cost (~5–10 s). Disable by setting
  `min_machines_running = 1` if latency-critical.
- **KB on the volume must outlive deploys** — the volume is named
  `ark_kb_data`. Don't `flyctl volumes destroy` it during routine deploys.
- **Tests do not run inside the image** — CI runs them on the GitHub
  runner before triggering `flyctl deploy`.
