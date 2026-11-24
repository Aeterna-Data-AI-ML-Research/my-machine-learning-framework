# CLI

Reference for mymlfw 0.4.0. The program is `python -m mymlfw`. `--debug` adds a traceback field to the error JSON. Every other failure is one JSON object on stderr with `error_code` and `suggested_fix`, and the process exits 1.

## Host vs Docker

| How | Command |
| --- | --- |
| Docker (default) | `make cli CMD='version'` — mounts workdir at `/work` (`make` sets absolute `MYMLFW_WORK`) |
| Docker (script) | `./deploy/run-cli.sh version` |
| Docker (compose) | `MYMLFW_WORK=$PWD docker compose -f deploy/docker-compose.yml --profile cli run --rm cli version` (compose default mount is `..` = repo root) |
| Host venv | `.venv/bin/python -m mymlfw version` after `pip install -e .` |

Rebuild the image after Dockerfile changes with `make cli-build`. Torch is not in the default CLI image; install `.[train]` on the host or build a custom image for GPU training. Stack how-to: [Run the Campaign SaaS stack](../how-to/run-campaign-saas.md).

Flags below are the ones the parser requires or commonly takes. Defaults are the argparse defaults.

## Contest loop

| Command | Required | Notes |
| --- | --- | --- |
| `version` | | Prints `0.4.0`. |
| `new-contest NAME --dest DIR` | `NAME`, `--dest` | Creates the tree in [Contest layout](contest-layout.md). |
| `gate debiased --full F.npz --imb I.npz` | panels | Debiased Full∧Imb promote JSON (`--min-bp`, baselines). |
| `gate pin-check --dir CONTEST` | `--dir` | NTL pin laws (mounts, post, protected FIRE files). |
| `gate cloud-local --record probe.json` | `--record` | MPS Fold-0 champion gate before RunPod. |
| `fire status --state PATH` / `fire assert` | `--state` | Daily submit/GPU quotas; refuse identical LIVE SHA / resubmit. |
| `kaggle verify-notebook --ref A --vs B` | paths | `IDENTICAL` / `FACTORIAL_DIFF` / `UNRELATED` + code SHA. |
| `kaggle submit-wait` | competition + file + ledger | Submit then poll public score → ledger (`--dry-run` ok). |
| `canary dual` | `--panel`, `--hubs`, `--submission` | Ranked MRR@25 SHIP/FAIL (both Δ≥0, R1 L=0). |
| `canary diff` | `--a`, `--b` | R1/R2 churn between ranked CSVs. |
| `canary night-shift` | panel + hubs + submission + `--out` | Score-only digest; never submits. |
| `probe score … --noise-band 0.005` | | Verdict `noise` unless Δ clears band (+ optional `--debiased-ok`). |
| `probe sha … --code` | | Store `code_sha256`; prefers CSV payload SHA inside zips; duplicate → `DUPLICATE_CODE`. |
| `submit check --kind kaggle_png_csv_zip` | `--file` | PNG-in-CSV zip (mode L, 64×64, ink, AppleDouble, 30200 ids). |
| `blend optimize --metric SPEC` | | Built-ins, `png_parity`, `ocf_equal_mean`, or `module.path:callable`. See [Metrics](metrics-scorers.md). |
| `multitask set-score` / `splice` / `promote-check` | `--path` | Equal-mean S=(S1+…+Sk)/k; per-(task,group) splice; Δ/z/full-n gates. |
| `experiment-dir allocate` / `check` | `--parent`/`--stem` or `--path` | Immutable vN+1 clones; refuse overwrite of pushed `casmi26_v*`. |
| `lever-registry sync-kills` | `--registry`, `--ledger` | Auto-kill confirmed-large-gap / noise knobs. |
| `profile-data --dir DIR` | `--dir` | Writes a profile. `--out` sets the path. `--recommend` is accepted and changes nothing: recommendations are always written. |
| `recipes --match TEXT` | | Substring match on recipe cards. `ranking` returns the ranking card only. |
| `recipes --show ID` | | Prints one card. |
| `playbook strategies --modality MOD` | | Strategy ladder for `tabular` / `text` / `vision` / `sequential` / `neural`. `--json` for machine output. |
| `playbook shifts --modality MOD --kind KIND` | | Paradigm shifts filtered by venue (`kaggle` \| `standalone`). |
| `playbook roadmap --modality MOD --kind KIND` | | Prints Stages 1–5 (+ `--shift ID` repeatable). `--baseline`, `--validation`, `--json`. |
| `playbook catalog --modality MOD --kind KIND` | | Full JSON catalog (same payload as `GET /v1/playbook/catalog`). |
| `archive-contest --ledger PATH --playbook PATH` | both paths | Writes `## proven_wins` and `## known_traps`. `--recipe ID` also appends those lists to that card. |
| `analyze --dir DIR` | `--dir` | Read-only JSON. `--task`, `--db`, `--out`. |
| `advise --dir DIR` | `--dir` | Git worktree. `--task` defaults to `next experiment`. `--db`, `--clean`, `--id`. |
| `sync-docs` | | Regenerates the recipe block in `llms.txt`. Refuses a file over 1500 whitespace tokens. |

## Ledger

| Command | Required |
| --- | --- |
| `probe register` | `--ledger`, `--experiment-id`, `--variable`, `--band-low`, `--band-high`. `--baseline-id` defaults to empty and then the command rejects it. `--change-count` must stay 1. |
| `probe update-cv` | `--ledger`, `--experiment-id`, `--cv-mean`. Optional `--cv-std`. |
| `probe score` | `--ledger`, `--experiment-id`, `--public-score`. |
| `probe verdict` | `--ledger`, `--experiment-id`, `--verdict`. Optional `--note`. |
| `probe sha` | `--ledger`, `--experiment-id`, `--artifact`. |

## Blend, shift, submit

| Command | Required |
| --- | --- |
| `blend optimize` | Repeat `--oof`. `--labels`, `--manifest`. `--metric` / `--scorer`: `log_loss` (default), `accuracy`, `balanced_accuracy`, `png_parity`, `ocf_equal_mean`, or `module.path:callable`. `--l2` defaults to `0.05`. |
| `blend diversity` | Repeat `--oof` and `--cv`. `--strict` is optional. |
| `blend reorder-classes` | `--target`, `--source`, `--out`. |
| `diagnose-oof` | `--oof`, `--train`, `--out`. |
| `check-shift` | `--train`, `--test`, `--numeric`. |
| `preflight` | `--ledger`, `--experiment-id`, `--artifact`, `--gate`, `--leak`, `--runtime`, `--kernel`. `--scale-report` with `--require-scale-report`. Optional `--previous-hashes`. |
| `submit check` | `--kind id_label\|ranked\|kaggle_png_csv_zip`, `--file`. `--label-col` / `--png-col` / `--n-ids` / `--max-k`. |
| `multitask set-score` | `--path`, `--task`, `--score`. Optional `--n`, `--group`. |
| `multitask splice` | `--path`, `--task`, `--group`, `--score`. Optional `--n`. |
| `multitask promote-check` | `--path`, `--baseline`. Optional `--min-delta`, `--min-z`, `--require-n`. |
| `simulate-test` | `--train`, `--out`. `--rows` defaults to 25000. `--sample-seconds` defaults to 1. |

## Canary, dirs, levers

| Command | Required |
| --- | --- |
| `canary dual` | `--panel`, `--hubs`, `--submission`. Optional `--baseline-panel-mrr`, `--baseline-hubs-mrr`, `--k` (default 25). |
| `canary diff` | `--a`, `--b`. |
| `canary night-shift` | `--panel`, `--hubs`, `--submission`, `--out`. Optional `--label` (`R0`…`R3`), baselines. |
| `experiment-dir allocate` | `--parent`, `--stem`. |
| `experiment-dir check` | `--path`. |
| `lever-registry sync-kills` | `--registry`, `--ledger`. |
| `kaggle submit-wait` | `--competition`, `--file`, `--ledger`, `--experiment-id`. Optional `-k`, `--poll`, `--timeout`, `--dry-run`. |

How-tos: [CASMI ranked canary](../how-to/casmi-ranked-canary.md), [SiClink image / recon](../how-to/siclink-image-recon.md).

## Kernel, train, cloud

| Command | Required |
| --- | --- |
| `kernel build` | `--src`, `--out`, and at least one `--payload`. |
| `pack-deps` | `--requirements`, `--out`. Pass `--dry-run`. Without it the command raises `PACK_DEPS_LIVE`. |
| `train lora` | `--dry-run` together with `--train`, `--ledger`, `--experiment-id`, `--baseline-id`, `--variable`, `--band-low`, `--band-high`. `--smoke` needs the train extra. |
| `train soup` | Repeat `--adapter` and `--weight`. `--out`. |
| `train grpo` | `--groups`. |
| `cloud launch` | `--project`, `--role`, `--gpu`, `--command`, `--idle-kill`, `--max-runtime`, `--ledger`, `--experiment-id`, `--baseline-id`, `--variable`, `--band-low`, `--band-high`, `--out`. The environment variable `CLOUD_APPROVAL` must be set. The command writes a script. It does not start a machine. |

## Campaign SaaS cloud (providers)

Requires the `saas` extra and `MYMLFW_CLOUD_RUNNERS=1`. Live RunPod/AWS when credentials are sealed and `MYMLFW_CLOUD_MOCK` is unset. See [Connect cloud runners](../how-to/connect-cloud-runners.md) and [SaaS environment](saas-env.md).

| Command | Required | Notes |
| --- | --- | --- |
| `cloud connect` | `--provider runpod\|aws` | RunPod: `--api-key`. AWS: `--role-arn`, optional `--region`. |
| `cloud disconnect` | `--provider` | Soft-disconnect account. |
| `cloud list` | | Accounts + runners JSON. |
| `cloud gpus` | `--provider` | Catalog + `cost_estimate_micros_hr`. |
| `cloud launch` | `--provider`, `--gpu-type` | Pass `--quote-only` first. Billable without it when connected. |
| `cloud stop` | `--runner-id` | |
| `cloud terminate` | `--runner-id` | |

When both the contest renderer and SaaS subcommands share the `cloud` parser name, the SaaS path is selected when `--provider` is present; the renderer path uses `--project` / `--out` / `CLOUD_APPROVAL`.

## Memory

| Command | Required |
| --- | --- |
| `remember` | `--tag`, `--rule`. Optional `--evidence`, `--db`, `--notes`. |
| `episode add` | `--contest`, `--task`, `--actions`, `--outcome`, `--lesson`. Optional `--evidence`, `--tag`, `--supersedes`, `--db`. |
| `episode recall` | `--task`. Optional `--data-dir`, `--db`. |
| `ingest` | `--path`, or `--sync` with no path. `--mode` is `docs`, `repo`, or `auto`. Optional `--tag`, `--db`. |
| `search` | A positional query or `--query`. `--type` defaults to `code_pattern`. Optional `--db`. |
| `promote-plugin FILE.py --category NAME` | The plugin file and `--category`. Optional `--dest`, `--tests-dest`. |

Imports that match these commands are listed in `llms.txt`.
