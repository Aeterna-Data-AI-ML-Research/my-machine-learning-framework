# Ledger

Reference for `ledger/experiments.csv`. Columns, in order:

| Column | Written by |
| --- | --- |
| `date` | `probe register`, as `YYYY-MM-DD`. |
| `experiment_id` | `probe register`. Reusing an id for a different variable raises `DUPLICATE_EXPERIMENT`. |
| `baseline_id` | `probe register`. Required. |
| `variable` | `probe register`. One name, including a form such as `lora_r=64`. |
| `change_count` | Always `1`. Any other count raises `SECOND_VARIABLE`. |
| `cv_mean` | `probe update-cv`. |
| `cv_std` | `probe update-cv` when `--cv-std` is passed. |
| `cv_delta` | Recomputed when `cv_mean` is set, against the baseline row. |
| `expected_band_low` | `probe register`. |
| `expected_band_high` | `probe register`. |
| `public_score` | `probe score`. |
| `cv_lb_gap` | Absolute gap between `cv_mean` and `public_score` when both exist. |
| `artifact_sha256` | `probe sha` (prefers inner CSV SHA for single-CSV zips), and preflight when the cell is still empty. |
| `code_sha256` | `probe sha --code`; duplicate code → `DUPLICATE_CODE`. |
| `verdict` | `pending` at registration. See below. |
| `note` | `--note` on register or verdict. Put typed kill tags here for advise retrieval. |

## Verdicts

| Value | Meaning |
| --- | --- |
| `pending` | Registered, not closed. |
| `promote-candidate` | Kept. Archive lists it under proven wins when `cv_delta` is set. |
| `kill` | Do not repeat. Preflight returns `PROBE_CLOSED`. |
| `confirmed-large-gap` | Public score was outside the registered band. Preflight returns `PROBE_CLOSED`. |
| `noise` | Public Δ inside `--noise-band` (optional on `probe score`). |
| `DUPLICATE_CODE` | Same `code_sha256` as an earlier row. |

`probe score` sets `confirmed-large-gap` by itself when the public score is outside the band (or `noise` when inside the noise band). Other verdicts are set with `probe verdict`.

A probe is identified by the variable string plus the two band edges. Registering that identity again raises `DUPLICATE_PROBE`, including while the first row is still `pending`. The same `experiment_id` and the same identity returns the existing pending row.

Pending rows are not retrieval chunks. A non-pending `kill` or `confirmed-large-gap` is a trap. `promote-candidate` is a win.

## Typed kill tags

Put these strings in `note` (or as the verdict when closing) so `advise` and `lever-registry sync-kills` surface them before Sinkhorn/fuse-style levers:

| Tag | Typical meaning |
| --- | --- |
| `td_uniqueness_trap` | Uniqueness / collision dead end. |
| `soft_proxy_vs_exact_metric` | Soft IoU / class-prob proxy instead of Exact PNG / Exact-ID. |
| `fold_subsample_invalid` | `n` below full fold (multitask / cloud gates also use this code). |
| `sibling_odds_rebrand` | Rebranded sibling odds. |
| `typo_micro_variant` | Typo / micro fork. |
| `duplicate_code_sha` | Same code SHA as a prior fire. |
| `noise_band` | Δ inside noise band. |

Sync into a local lever registry:

```bash
python -m mymlfw lever-registry sync-kills --registry levers.json --ledger ledger/experiments.csv
```

## Multitask sidecar

Equal-mean task scores live in a separate JSON file (not a new CSV column). See [SiClink image / recon](../how-to/siclink-image-recon.md) and `multitask` in [CLI](cli.md).

## Archive order

`archive-contest` writes `## proven_wins` with the largest `cv_delta` first, and `## known_traps` from `kill` and `confirmed-large-gap` with the most negative `cv_delta` first.
