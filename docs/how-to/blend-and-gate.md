# Blend and gate a submission

How-to. Fit blend weights on out-of-fold predictions, then refuse a submission that fails the ledger, the hash, or the kernel rules.

For Exact PNG / multi-task OCF contests, prefer [SiClink image / recon](siclink-image-recon.md). For ranked MRR@25 dual-canary, prefer [CASMI ranked canary](casmi-ranked-canary.md). Scorer table: [Metrics and scorers](../reference/metrics-scorers.md).

## Align and weight

Each branch is a `.npz` prediction bundle. Branches must share ids. Class order mismatches raise `CLASS_ORDER_MISMATCH`. The suggested fix is `blend reorder-classes`.

```bash
python -m mymlfw blend optimize \
  --oof branch_a.npz \
  --oof branch_b.npz \
  --labels y.csv \
  --manifest manifest.json \
  --metric log_loss
```

`--metric` / `--scorer` may be a built-in (`log_loss`, `accuracy`, `balanced_accuracy`, `png_parity`, `ocf_equal_mean`) or `module.path:callable`. Add `--l2` to change the default `0.05`.

Check redundancy before you keep a branch:

```bash
python -m mymlfw blend diversity \
  --oof branch_a.npz --cv 0.81 \
  --oof branch_b.npz --cv 0.80
```

`--strict` turns a high-redundancy warning into an error.

## Check train against test

```bash
python -m mymlfw check-shift \
  --train data/train.csv \
  --test data/test.csv \
  --numeric feature_1
```

A detected shift returns `SHIFT_DETECTED`. The analyzer also adds `check_shift` to its retrieval query when the train and test column sets differ.

## Gate the file

Register the probe first. `kill` and `confirmed-large-gap` return `PROBE_CLOSED`. The kernel document must set `enable_internet` to false. `gate.json`, `leak.json`, and `runtime.json` must each carry the artifact sha256.

```bash
python -m mymlfw preflight \
  --require-scale-report \
  --ledger ledger/experiments.csv \
  --experiment-id exp_002 \
  --artifact submission.parquet \
  --gate gate.json \
  --leak leak.json \
  --runtime runtime.json \
  --kernel kernel/kernel-metadata.json \
  --scale-report scale.json
```

Build the scale report from the train table:

```bash
python -m mymlfw simulate-test \
  --train data/train.csv \
  --rows 25000 \
  --sample-seconds 1 \
  --out scale.json
```

Check the submission shape:

```bash
python -m mymlfw submit check --kind id_label --file submission.csv --classes a,b
```

| `--kind` | Checks |
| --- | --- |
| `id_label` | Id + label columns / class set. |
| `ranked` | Candidate lists; default `--max-k 25`. |
| `kaggle_png_csv_zip` | Base64 PNG rows (mode L, 64×64, ink, AppleDouble, `--n-ids`). |

`probe sha` prefers the inner CSV SHA when the artifact is a single-CSV zip (Kaggle auto-extract).

Debiased NTL promote and cloud anti-waste:

```bash
python -m mymlfw gate debiased --full full.npz --imb imb.npz --baseline-full 0.5 --baseline-imb 0.5
python -m mymlfw gate cloud-local --record artifacts/local_mps_fold0.json
```

## Kernel payload

```bash
python -m mymlfw kernel build \
  --src kernel/src \
  --out contest.ipynb \
  --payload worker.py
```

A payload whose name contains `weight`, or a `.npz` payload, raises `PAYLOAD_KIND`. Payloads over 512000 bytes raise `PAYLOAD_TOO_LARGE`. Ship weights as a dataset, not inside the notebook.

`pack-deps` prints a download plan only when you pass `--dry-run`. A live download raises `PACK_DEPS_LIVE`.
