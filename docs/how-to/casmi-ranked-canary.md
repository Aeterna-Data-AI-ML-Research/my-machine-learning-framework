# Run a CASMI-style ranked dual-canary contest

How-to. Treat dual-canary SHIP/FAIL and Project Brain dead ends as the standing gates — not more generic GBDT blend. Recipe card: `casmi-ranked-dual-canary`. Bind the contest to a Studio project and drive it via MCP at `http://127.0.0.1:8100/mcp`.

## 1. Standing ship gate

Score a ranked CSV on Panel + HUBS. SHIP only if both ΔMRR ≥ 0 **and** R1 losses = 0 on both canaries.

```bash
python -m mymlfw canary dual \
  --panel Panel120.parquet \
  --hubs HUBS19.parquet \
  --submission ranked.csv \
  --baseline-panel-mrr 0.50 \
  --baseline-hubs-mrr 0.48
```

Exit 0 = `SHIP`, exit 1 = `FAIL`. Pass baselines from the last SHIP artifact. Without baselines, ΔMRR is absolute MRR (always ≥ 0), so R1 L=0 is the hard filter.

R1/R2 churn between two ranked CSVs:

```bash
python -m mymlfw canary diff --a prev.csv --b next.csv
```

## 2. Night-Shift score-only (never submits)

Budget R0/R1/R2 encodes overnight; morning digest only:

```bash
python -m mymlfw canary night-shift \
  --panel Panel120.parquet \
  --hubs HUBS19.parquet \
  --submission ranked.csv \
  --out digests/ \
  --label R0
```

`submit` is always `false` in the digest JSON. Tip-gap campaigns need many R1 wins — public knobs alone will not close 0.505→0.554.

## 3. Vault → Project Brain

Do not re-derive dead ends in chat. Bind CASMI to a Studio project, then ingest:

```text
ingest_vault_brain(project_id, contest_dir, idempotency_key)
query_project_brain(project_id, query="SpecFold mid-only", scope="dead_ends")
```

Local ingest also indexes `PROPRIETARY_KNOWLEDGE_VAULT.md` and `*REPORT*.md` via `python -m mymlfw ingest`.

Record new kills so the next agent turn sees them:

```text
record_dead_end(project_id, variable="L10 SpecFold mid-only", lesson="…", idempotency_key)
append_vault_law(vault_path, law_id="L18", text="metabolic kill", idempotency_key)
```

## 4. Levers and immutable dirs

One variable at a time. `propose_lever_execution` refuses variables already in Project Brain dead ends. Sync ledger kills into a local registry:

```bash
python -m mymlfw lever-registry sync-kills \
  --registry levers.json \
  --ledger ledger/experiments.csv
```

Refuse overwrite of pushed `casmi26_vXX_*` trees — clone as vN+1:

```bash
python -m mymlfw experiment-dir allocate --parent runs/ --stem casmi26_v12_fuse
python -m mymlfw experiment-dir check --path runs/casmi26_v12_fuse
```

## 5. Kaggle ops via MCP

| Moment | Tool |
| --- | --- |
| After submit | `kaggle_refresh(project_id, competition, idempotency_key)` |
| Before GPU kernel | `kaggle_submit_lifecycle` — refuse `IS_RERUN` / `FAST_COMMIT` / `enable_gpu=False` |
| Title badge ≠ LB | `public_code_badge(title_score, observed_score)` |
| Licenses | `verify_project_licenses` + CASMI GNPS/NIST scrub on credits |
| SpecFold encode GPU | `quote_cloud_launch` then `launch_cloud_runner` — do not burn Kaggle T4×2 batch |

Full agent loop: [Keep a Studio project updated via MCP](agent-mcp-campaign-sync.md). Prompt: `campaign_sync`.

## 6. Dual-canary from MCP

```text
dual_canary(panel_path, hubs_path, submission_path, baseline_panel_mrr=…, baseline_hubs_mrr=…)
```

Same SHIP/FAIL contract as the CLI.

## See also

- [Agent MCP campaign sync](agent-mcp-campaign-sync.md)
- [Night shift](../explanation/night-shift.md)
- [Project Brain RAG](../explanation/project-brain-rag.md)
- [CLI](../reference/cli.md)
