# Metrics and scorers

Reference for host metrics used by `blend optimize`, gates, and the multitask ledger. Higher is better unless a gate documents otherwise.

## Built-in blend metrics

Pass `--metric NAME` or `--scorer NAME` to `blend optimize`.

| Name | Input | Notes |
| --- | --- | --- |
| `log_loss` | class bundle | Mean log-prob of the gold label (default). |
| `accuracy` | class bundle | Argmax accuracy. |
| `balanced_accuracy` | class bundle | Per-class recall average. |
| `png_parity` | pixel arrays / matching `values` | pred÷255 vs gt≥128. Refuses `(N,C)` class scores (`SOFT_PROXY`). |
| `ocf_equal_mean` | list of task scores | S=(S₁+…+Sₖ)/k — not row-count weighted. Prefer `multitask` for day-to-day. |
| `balanced_accuracy_full_imb` | two panels | Joint Full∧Imb (min or mean). Used by `gate debiased`. |

## Plugins

Any `module.path:callable` that returns a finite float:

```bash
python -m mymlfw blend optimize \
  --oof a.npz --oof b.npz \
  --labels y.csv \
  --manifest m.json \
  --metric mypkg.metrics:my_ocf
```

Register at import time:

```python
from mymlfw.metrics.registry import register_scorer

@register_scorer("my_ocf")
def my_ocf(y_true, bundle, **meta) -> float:
    ...
```

`list_scorers()` / `resolve_scorer(spec)` / `safe_score(fn, …)` live in `mymlfw.metrics.registry`. NaN/Inf raises `BAD_METRIC`.

## Library helpers

| Import | Role |
| --- | --- |
| `mymlfw.metrics.siclink.png_parity` | Raw array Exact PNG score. |
| `mymlfw.metrics.siclink.png_parity_bundle` | Blend-facing wrapper. |
| `mymlfw.metrics.registry.ocf_equal_mean` | Equal-mean reducer. |
| `mymlfw.metrics.mrr_at_k` | Ranked MRR (CASMI dual-canary). |

## Related gates

| Gate / command | Metric contract |
| --- | --- |
| `canary dual` | Panel + HUBS MRR@25; SHIP iff both Δ≥0 and R1 L=0. |
| `gate debiased` | Full∧Imb balanced accuracy ≥ +100bp (configurable). |
| `multitask promote-check` | Equal-mean Δ / optional z / full-fold `n`. |
| `submit check --kind kaggle_png_csv_zip` | Shape verifier (not a CV metric). |
