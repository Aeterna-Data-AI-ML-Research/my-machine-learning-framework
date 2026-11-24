"""CASMI dual-canary gate: Panel + HUBS ranked MRR@K → SHIP/FAIL."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

from mymlfw.errors import MymlfwError
from mymlfw.metrics import mrr_at_k


def _load_truth_panel(path: Path, *, id_col: str = "id", label_col: str = "label") -> dict[str, str]:
    frame = pd.read_parquet(path) if path.suffix.lower() in {".parquet", ".pq"} else pd.read_csv(path)
    if id_col not in frame.columns or label_col not in frame.columns:
        raise MymlfwError(
            "CANARY_PANEL",
            f"Panel needs {id_col!r} and {label_col!r} columns.",
            columns=list(frame.columns),
            path=str(path),
        )
    return {
        str(i): str(y)
        for i, y in zip(frame[id_col].astype(str), frame[label_col].astype(str))
    }


def _load_ranked_submission(
    path: Path,
    *,
    id_col: str = "id",
    cand_col: str = "candidates",
    sep: str = ";",
    max_k: int = 25,
) -> dict[str, list[str]]:
    frame = pd.read_csv(path)
    if id_col not in frame.columns or cand_col not in frame.columns:
        raise MymlfwError(
            "CANARY_SUBMISSION",
            f"Submission needs {id_col!r} and {cand_col!r}.",
            columns=list(frame.columns),
        )
    out: dict[str, list[str]] = {}
    for row_id, raw in zip(frame[id_col].astype(str), frame[cand_col].astype(str)):
        parts = [p for p in str(raw).split(sep) if p != ""]
        if len(parts) > max_k:
            parts = parts[:max_k]
        if len(parts) != len(set(parts)):
            raise MymlfwError("DUPLICATE_CANDIDATE", "Ranked row has duplicate candidates.", id=row_id)
        out[row_id] = parts
    return out


def _panel_mrr(
    truth: dict[str, str],
    ranked: dict[str, list[str]],
    *,
    k: int = 25,
) -> dict[str, Any]:
    ids = sorted(set(truth) & set(ranked))
    if not ids:
        raise MymlfwError("CANARY_OVERLAP", "No overlapping ids between panel and submission.")
    scores = []
    r1_wins = 0
    r1_losses = 0
    for row_id in ids:
        gold = truth[row_id]
        cands = ranked[row_id]
        scores.append(mrr_at_k(cands, gold, k=k))
        if cands and cands[0] == gold:
            r1_wins += 1
        else:
            r1_losses += 1
    mrr = float(sum(scores) / len(scores))
    return {
        "n": len(ids),
        "mrr": mrr,
        "r1_wins": r1_wins,
        "r1_losses": r1_losses,
        "r1_hit_rate": float(r1_wins / len(ids)),
    }


def dual_canary(
    *,
    panel_path,
    hubs_path,
    submission_path,
    baseline_panel_mrr: float | None = None,
    baseline_hubs_mrr: float | None = None,
    k: int = 25,
    id_col: str = "id",
    label_col: str = "label",
    cand_col: str = "candidates",
    sep: str = ";",
) -> dict[str, Any]:
    """Score ranked submission on Panel + HUBS; SHIP iff both ΔMRR≥0 and R1 L=0 on both.

    When baselines are omitted, ΔMRR is reported as absolute MRR (treat baseline=0)
    for the SHIP rule ``both canaries ≥ 0`` on delta — i.e. absolute MRR ≥ 0 always
    passes the Δ≥0 check; then R1 L=0 is the hard filter. Prefer passing baselines
    from the last SHIP artifact.
    """
    panel = Path(panel_path)
    hubs = Path(hubs_path)
    sub = Path(submission_path)
    ranked = _load_ranked_submission(sub, id_col=id_col, cand_col=cand_col, sep=sep, max_k=k)
    panel_truth = _load_truth_panel(panel, id_col=id_col, label_col=label_col)
    hubs_truth = _load_truth_panel(hubs, id_col=id_col, label_col=label_col)
    missing_panel = sorted(set(panel_truth) - set(ranked))
    missing_hubs = sorted(set(hubs_truth) - set(ranked))
    if missing_panel or missing_hubs:
        raise MymlfwError(
            "CANARY_COVERAGE",
            "Submission missing panel/HUBS ids — refuse SHIP on partial overlap.",
            missing_panel=missing_panel[:20],
            missing_hubs=missing_hubs[:20],
            n_missing_panel=len(missing_panel),
            n_missing_hubs=len(missing_hubs),
        )
    p = _panel_mrr(panel_truth, ranked, k=k)
    h = _panel_mrr(hubs_truth, ranked, k=k)
    base_p = 0.0 if baseline_panel_mrr is None else float(baseline_panel_mrr)
    base_h = 0.0 if baseline_hubs_mrr is None else float(baseline_hubs_mrr)
    delta_p = p["mrr"] - base_p
    delta_h = h["mrr"] - base_h
    ship = (
        delta_p >= 0.0
        and delta_h >= 0.0
        and int(p["r1_losses"]) == 0
        and int(h["r1_losses"]) == 0
    )
    return {
        "verdict": "SHIP" if ship else "FAIL",
        "k": int(k),
        "panel": {**p, "delta_mrr": delta_p, "baseline_mrr": base_p},
        "hubs": {**h, "delta_mrr": delta_h, "baseline_mrr": base_h},
        "rules": {
            "both_delta_mrr_ge_0": delta_p >= 0.0 and delta_h >= 0.0,
            "r1_losses_zero_both": p["r1_losses"] == 0 and h["r1_losses"] == 0,
        },
        "submission": str(sub),
    }


def diff_ranked_submissions(
    path_a,
    path_b,
    *,
    id_col: str = "id",
    cand_col: str = "candidates",
    sep: str = ";",
    max_k: int = 25,
) -> dict[str, Any]:
    """Count R1/R2 churn between two ranked CSVs."""
    a = _load_ranked_submission(Path(path_a), id_col=id_col, cand_col=cand_col, sep=sep, max_k=max_k)
    b = _load_ranked_submission(Path(path_b), id_col=id_col, cand_col=cand_col, sep=sep, max_k=max_k)
    ids = sorted(set(a) & set(b))
    r1_churn = 0
    r2_churn = 0
    for row_id in ids:
        ca, cb = a[row_id], b[row_id]
        if (ca[:1] or [None])[0] != (cb[:1] or [None])[0]:
            r1_churn += 1
        if (ca[:2] or []) != (cb[:2] or []):
            r2_churn += 1
    return {
        "n_overlap": len(ids),
        "r1_churn": r1_churn,
        "r2_churn": r2_churn,
        "r1_churn_rate": float(r1_churn / len(ids)) if ids else 0.0,
        "r2_churn_rate": float(r2_churn / len(ids)) if ids else 0.0,
        "only_a": sorted(set(a) - set(b))[:20],
        "only_b": sorted(set(b) - set(a))[:20],
    }
