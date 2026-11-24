# Invariants

Explanation of the rules that tests keep in place. Break one of these and the matching phase test is the place to update first.

## One variable

A probe changes one variable. `change_count` is `1`. The identity is the variable string plus the two expected-band edges. A killed variable and a confirmed CV-LB gap stay closed through preflight (`PROBE_CLOSED`).

## Folds and blends

Call `mymlfw.cv.run_oof` for grouped folds. Fit unsupervised steps on the training side of the fold. Fit temperature on a fold that is not the one being scored. Convert logits with `log_softmax` before a probability pool. `align` raises on an id mismatch unless the caller passes `on_mismatch="drop_and_warn"`.

Exact PNG / OCF contests use `png_parity` (or a plugin), not soft class-prob proxies (`SOFT_PROXY` / `soft_proxy_vs_exact_metric`). Multi-task promotion uses equal-mean S=(S₁+…+Sₖ)/k with full-fold `n` — never N-weighted Task3 bias or `n≤400` proxies (`fold_subsample_invalid`).

## Ranked dual-canary

CASMI-shaped ship requires `canary dual` SHIP: both Panel and HUBS ΔMRR ≥ 0 and R1 losses = 0. Night-Shift score-only digests never call Kaggle submit.

## Engines and the kernel

An engine does not import `mymlfw.train.lora`. Notebook metadata sets `enable_internet` to false, and preflight rejects anything else (`INTERNET_ENABLED`). A payload named like a weight file, or a `.npz` payload, raises `PAYLOAD_KIND`. The unpacked zip has a size cap (`ZIP_TOO_LARGE`). Preflight refuses starter-baseline zip hashes and empty Output / competition fields when those keys are present. GPU kernel submit must clear `IS_RERUN` / `FAST_COMMIT` / `enable_gpu=False` dummies.

## Cloud and wheels

`cloud launch` renders a shell script after `CLOUD_APPROVAL` is set. The rendered command is one line. `pack-deps` without `--dry-run` raises `PACK_DEPS_LIVE`. SaaS / MCP cloud runners stay blocked until `gate cloud-local` (MPS Fold-0 champion JSON) passes unless explicitly skipped.

## Memory

Field notes and episodes are indexed when they are written and again when the dump is replayed. `advise` does not insert episodes. A source of `auto_advise` raises `AUTO_ADVISE_FORBIDDEN`. Episode outcomes are `worked`, `failed`, and `partial`. A bad outcome raises `BAD_EPISODE`.

The worked-step filter keeps a retrieved note when its evidence and tags are empty, or when any token is not already a ledger variable. It drops the note when the token set is non-empty and every token is already in the ledger. `name=value` is one token.

Automatic advise ingest does not store JSON or YAML bodies. Explicit `ingest --mode docs` does.

## The agent index

`llms.txt` in the checkout and `src/mymlfw/resources/llms.txt` are the same file contents. `sync-docs` rewrites only the block between `<!-- mymlfw-index -->` and `<!-- /mymlfw-index -->`. The file stays at or under 1500 whitespace-delimited tokens. The sentence `DO NOT write custom GroupKFold loops; call mymlfw.cv.run_oof.` stays verbatim.

## Plugins

`promote-plugin` copies a module into `contrib/` after the sibling test passes and an import scan accepts it. The scan rejects dynamic import, `exec`, `eval`, `compile`, and `import_module`. Plugins are CPU-only.
