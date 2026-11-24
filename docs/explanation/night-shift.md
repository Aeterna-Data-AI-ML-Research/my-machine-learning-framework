# Night shift

Autopilot is a budgeted successive-halving loop (R0 smoke → R1 fold0 → R2 full CV) under `active_execution_lock=autopilot`. Spot preemption does not count as an infra strike. The morning digest asks a human to promote or queue Kaggle; the worker never submits overnight. Enable with `feature_flags.night_shift`.

## Two lanes

| Lane | When | Submit? |
| --- | --- | --- |
| Autopilot (`feature_flags.night_shift`) | Studio project with open lever lock | Never overnight — human promotes from digest |
| `canary night-shift` | Ranked Panel+HUBS contests (CASMI) | Never — score-only JSON digest |

## CASMI / ranked score-only

```bash
python -m mymlfw canary night-shift \
  --panel Panel120.parquet --hubs HUBS19.parquet \
  --submission ranked.csv --out digests/ --label R0
```

Writes a morning digest JSON with ΔMRR / R1 W/L / SHIP|FAIL. `submit` is always `false`. Tip-gap campaigns (e.g. 0.505→0.554 needing many R1 wins) should budget R0/R1/R2 encodes overnight and leave Kaggle submit to a human after digest review.

Full ranked loop: [CASMI ranked canary](../how-to/casmi-ranked-canary.md).
