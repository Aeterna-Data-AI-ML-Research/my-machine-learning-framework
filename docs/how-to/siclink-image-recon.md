# Run a SiClink-style image / recon contest

How-to. Pull stacking, equal-mean promotion, and daily PNG submit into mymlfw instead of ad-hoc scripts. Recipe card: `closed-set-bank-decode`. Playbook modality: `neural` (not `vision` — spikes / structured→image is not ConvNeXt-first).

## 1. Host metric for blend

Built-ins `log_loss` / `accuracy` / `balanced_accuracy` are wrong for Exact PNG OCF. Use the registered scorer or a plugin:

```bash
python -m mymlfw blend optimize \
  --oof branch_a.npz \
  --oof branch_b.npz \
  --labels y_pixels.npz \
  --manifest manifest.json \
  --metric png_parity
```

| Spec | Meaning |
| --- | --- |
| `png_parity` | pred÷255 vs gt≥128 pixel agreement (Exact metric). Refuses `(N,C)` class scores (`SOFT_PROXY` / `soft_proxy_vs_exact_metric`). |
| `ocf_equal_mean` | Reducer over a list of task scores: S=(S₁+…+Sₖ)/k (not N-weighted). Prefer the multitask ledger for day-to-day use. |
| `module.path:callable` | Any higher-is-better `(y_true, bundle) → float`. |

Library import: `from mymlfw.metrics.siclink import png_parity`.

## 2. Equal-mean multitask ledger

Task slots are first-class. Groups are averaged per task, then tasks equal-mean — that stops Task3-volume bias and `n≤400` proxies.

```bash
python -m mymlfw multitask splice \
  --path ledger/multitask.json \
  --task t1 --group fold0 --score 0.41 --n 87936

python -m mymlfw multitask splice \
  --path ledger/multitask.json \
  --task t2 --group fold0 --score 0.38 --n 87936

python -m mymlfw multitask splice \
  --path ledger/multitask.json \
  --task t3 --group fold0 --score 0.44 --n 87936

python -m mymlfw multitask promote-check \
  --path ledger/multitask.json \
  --baseline 0.40 \
  --min-delta 0.001 \
  --require-n 87936
```

`set-score` writes one task directly when you already have a collapsed score. `promote-check` fails with `MULTITASK_DELTA`, `MULTITASK_Z`, or `MULTITASK_SUBSAMPLE` (`fold_subsample_invalid`).

## 3. Submission shape (PNG-in-CSV zip)

```bash
python -m mymlfw submit check \
  --kind kaggle_png_csv_zip \
  --file submission.zip \
  --n-ids 30200 \
  --png-col prediction
```

Checks: exactly one CSV in the zip, unique ids, mode `L`, 64×64, ink-density band, refuse AppleDouble / `__MACOSX`. Needs Pillow (`pip install pillow`).

## 4. Artifact SHA and submit wait

Kaggle often auto-extracts `*.zip`. Prefer the inner CSV digest:

```bash
python -m mymlfw probe sha \
  --ledger ledger/experiments.csv \
  --experiment-id exp_042 \
  --artifact submission.zip
```

The JSON includes `payload.kind=zip_csv_payload` when a single CSV member is hashed.

Optional: submit and write public score back to the ledger (requires the `kaggle` CLI):

```bash
python -m mymlfw kaggle submit-wait \
  --competition your-comp-slug \
  --file submission.zip \
  --ledger ledger/experiments.csv \
  --experiment-id exp_042 \
  --dry-run   # drop --dry-run for a live submit
```

## 5. Preflight and cloud anti-waste

Preflight asserts kernel `Output` / competition sources when present, and refuses a starter-baseline zip hash. Before any cloud GPU:

```bash
python -m mymlfw gate cloud-local --record artifacts/local_mps_fold0.json
```

The probe JSON must show MPS (or named device), Fold-0, no subsample, ≥300k params, decreasing loss, and Δ vs champion ≥ θ (default 0.5). See the workspace Cloud GPU Anti-Waste rules.

## 6. Playbook and dead ends

```bash
python -m mymlfw playbook strategies --modality neural
python -m mymlfw recipes --show closed-set-bank-decode
```

Ladder: PSTH / trial features → closed-set bank → Exact-metric MBR → optional generative refine.

Tag kills in the ledger note so `advise` retrieves them before Sinkhorn/fuse proposals:

```bash
python -m mymlfw probe verdict \
  --ledger ledger/experiments.csv \
  --experiment-id exp_old \
  --verdict kill \
  --note "soft_proxy_vs_exact_metric — never soft IoU for Exact PNG"
```

Typed tags: `td_uniqueness_trap`, `soft_proxy_vs_exact_metric`, `fold_subsample_invalid` (and related NTL tags).

## See also

- [Blend and gate a submission](blend-and-gate.md)
- [CLI](../reference/cli.md) — scorers, multitask, submit kinds
- [Ledger](../reference/ledger.md) — verdicts and typed kill tags
- [Night shift](../explanation/night-shift.md) — score-only overnight (never auto-submit)
