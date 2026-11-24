# mymlfw

Local toolkit for ML and Kaggle contests. Version **0.2.0**. It keeps one experiment ledger, checks blends and submissions, and gives a coding agent a memory of what already failed. The same repo also ships a **Campaign SaaS** control plane (API, Studio web, MCP, worker) plus a shared **DS playbook** (`mymlfw playbook` / Studio New project wizard) for modality strategies and paradigm shifts.

This repository is the documentation and the package. Human reading starts at [docs/index.md](docs/index.md). Coding agents read [llms.txt](llms.txt), then [AGENTS.md](AGENTS.md).

## Docker-first (default)

Day-to-day use is Docker Compose — no host Python required for Studio or the contest CLI.

### Prerequisites

- Docker Desktop (or Docker Engine + Compose v2)
- Optional: a [Kaggle API token](https://www.kaggle.com/docs/api) for live competition sync

### Start the stack

From the repository root:

```bash
make up
# same as: make dev
# or:      docker compose -f deploy/docker-compose.yml up --build -d
```

Compose project name is **`mymlfw`**. Data-plane ports bind **`127.0.0.1` only**. Env template: [`deploy/.env.example`](deploy/.env.example).

| URL / host port | Service |
| --- | --- |
| `http://127.0.0.1:8001/health` | API (host **8001** → container 8000) |
| `http://127.0.0.1:5175/` | Studio web console |
| `http://127.0.0.1:8100/mcp` | MCP (streamable HTTP) |
| `127.0.0.1:27017` | MongoDB |
| `127.0.0.1:6380` | Redis (host **6380** → container 6379) |
| `http://127.0.0.1:9000` | Object store (S3 API; Silo / MinIO-compatible) |
| `http://127.0.0.1:9001/` | Object store console (`mymlfw` / `mymlfwsecret`) |

```bash
make ps          # container status
make logs        # follow logs
make down        # stop stack
```

### Contest CLI in Docker

The `cli` service runs `python -m mymlfw` with the host directory mounted at `/work` (default: repo root).

```bash
make cli CMD='version'
make cli CMD='playbook strategies --modality tabular'
MYMLFW_WORK=/path/to/contest make cli CMD='analyze --dir .'
make shell-cli   # interactive bash in the CLI image
```

Torch is not in the default CLI image; use a host `[train]` install or a custom image for GPU training.

### First login (local)

Compose sets `MYMLFW_GITHUB_OAUTH_STUB=true`, so you can register without a GitHub OAuth app:

1. Open Studio: [http://127.0.0.1:5175/](http://127.0.0.1:5175/)
2. Or register via API:

```bash
curl -s -X POST http://127.0.0.1:8001/v1/auth/register \
  -H 'Content-Type: application/json' \
  -d '{"email":"you@example.com","password":"password123","display_name":"You"}'
```

Save `access_token` from the response. Demo campaign data is seeded after login.

**New project:** Studio home → **New project** runs the DS playbook wizard. How-to: [studio-new-project-wizard.md](docs/how-to/studio-new-project-wizard.md).

### Agent MCP

1. In Studio: **Settings → Agent PAT** — mint a PAT
2. Point Cursor/Claude at `http://127.0.0.1:8100/mcp` with `Authorization: Bearer <pat>`

Playbook: [Keep a Studio project updated via MCP](docs/how-to/agent-mcp-campaign-sync.md).

### Optional: Kaggle token before `make up`

```bash
mkdir -p ~/.kaggle
export KAGGLE_API_TOKEN="$(tr -d '[:space:]' < ~/.kaggle/access_token)"
make up
```

Compose mounts `~/.kaggle` read-only into the API container (`make up` creates the directory if missing).

### More detail

- [Run the Campaign SaaS stack](docs/how-to/run-campaign-saas.md) — ports, feature flags, advise curls
- [Connect cloud runners](docs/how-to/connect-cloud-runners.md) — RunPod / AWS after sealing keys
- [SaaS environment reference](docs/reference/saas-env.md)
- Compose file: [`deploy/docker-compose.yml`](deploy/docker-compose.yml)

## Install (optional host CLI)

For pytest or editing without Docker, Python 3.11+:

```bash
python -m venv .venv
.venv/bin/pip install -e .
# train extra (torch):  .venv/bin/pip install -e '.[train]'
# SaaS extras on host:  .venv/bin/pip install -e '.[saas,dev]'
```

## Tests

```bash
.venv/bin/python -m pytest -q
# or: make test
```

Phase modules run from `tests/test_phase1_package.py` through `tests/test_phase16_analyze.py`. Retrieval wiring is `tests/test_rag_wiring.py`. SaaS anti-drift: `make anti-drift`.

## Marketing site (GitHub Pages)

Static marketing site lives in [`site/`](site/). Deployed by [`.github/workflows/pages.yml`](.github/workflows/pages.yml) from `site/` on pushes to `main`.

`https://aeterna-data-ai-ml-research.github.io/my-machine-learning-framework/`

## First CLI command

```bash
make cli CMD='version'
# or on host: .venv/bin/python -m mymlfw version
```

The contest walkthrough is [docs/tutorials/first-contest.md](docs/tutorials/first-contest.md).
