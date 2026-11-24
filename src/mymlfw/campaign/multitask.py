"""Equal-mean multi-task ledger sidecar (SiClink-style S=(S1+S2+S3)/3)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np

from mymlfw.errors import MymlfwError
from mymlfw.metrics.registry import ocf_equal_mean


def load_multitask(path) -> dict[str, Any]:
    p = Path(path)
    if not p.exists():
        return {"schema_version": 1, "tasks": {}, "splices": [], "promotions": []}
    data = json.loads(p.read_text())
    if not isinstance(data, dict):
        raise MymlfwError("MULTITASK", "Multitask ledger must be a JSON object.")
    data.setdefault("schema_version", 1)
    data.setdefault("tasks", {})
    data.setdefault("splices", [])
    data.setdefault("promotions", [])
    return data


def save_multitask(path, data: dict[str, Any]) -> Path:
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n")
    return out


def set_task_score(
    data: dict[str, Any],
    *,
    task_id: str,
    score: float,
    n: int | None = None,
    group: str | None = None,
) -> dict[str, Any]:
    tasks = dict(data.get("tasks") or {})
    entry = {"score": float(score)}
    if n is not None:
        entry["n"] = int(n)
    if group is not None:
        entry["group"] = str(group)
    tasks[str(task_id)] = entry
    data = dict(data)
    data["tasks"] = tasks
    data["equal_mean"] = ocf_equal_mean([float(v["score"]) for v in tasks.values()])
    return data


def equal_mean_from_tasks(data: dict[str, Any]) -> float:
    tasks = data.get("tasks") or {}
    if not tasks:
        raise MymlfwError("MULTITASK", "No task scores recorded.")
    return ocf_equal_mean([float(v["score"]) for v in tasks.values()])


def splice_task_group(
    data: dict[str, Any],
    *,
    task_id: str,
    group: str,
    score: float,
    n: int | None = None,
) -> dict[str, Any]:
    """Record a per-(task, group) splice; task score becomes equal-mean of its groups.

    Prevents Task3-volume bias: groups are averaged first, then tasks equal-mean.
    """
    data = dict(data)
    splices = list(data.get("splices") or [])
    entry = {
        "task_id": str(task_id),
        "group": str(group),
        "score": float(score),
    }
    if n is not None:
        entry["n"] = int(n)
    # replace same (task, group) if present
    splices = [
        s
        for s in splices
        if not (s.get("task_id") == entry["task_id"] and s.get("group") == entry["group"])
    ]
    splices.append(entry)
    data["splices"] = splices
    # recompute each task as mean of its group splices
    by_task: dict[str, list[float]] = {}
    by_task_n: dict[str, list[int]] = {}
    for s in splices:
        tid = str(s["task_id"])
        by_task.setdefault(tid, []).append(float(s["score"]))
        if s.get("n") is not None:
            by_task_n.setdefault(tid, []).append(int(s["n"]))
    tasks = dict(data.get("tasks") or {})
    for tid, scores in by_task.items():
        meta: dict[str, Any] = {"score": float(np.mean(scores))}
        ns = by_task_n.get(tid) or []
        if ns:
            meta["n"] = int(sum(ns))  # total rows across groups (gate uses this)
        meta["n_groups"] = len(scores)
        tasks[tid] = meta
    data["tasks"] = tasks
    data["equal_mean"] = ocf_equal_mean([float(v["score"]) for v in tasks.values()])
    return data


def assert_promote_gates(
    data: dict[str, Any],
    *,
    baseline_equal_mean: float,
    min_delta: float = 0.001,
    min_z: float | None = None,
    require_full_fold_n: int | None = None,
) -> dict[str, Any]:
    score = equal_mean_from_tasks(data)
    delta = score - float(baseline_equal_mean)
    if delta < float(min_delta):
        raise MymlfwError(
            "MULTITASK_DELTA",
            f"Equal-mean Δ {delta:.6g} < min_delta {min_delta}.",
            equal_mean=score,
            delta=delta,
        )
    if require_full_fold_n is not None:
        for task_id, meta in (data.get("tasks") or {}).items():
            n = meta.get("n")
            if n is None or int(n) < int(require_full_fold_n):
                raise MymlfwError(
                    "MULTITASK_SUBSAMPLE",
                    "Full-fold n required per task (fold_subsample_invalid).",
                    task_id=task_id,
                    n=n,
                    require_full_fold_n=require_full_fold_n,
                )
    z = None
    if min_z is not None:
        # Optional: caller may stash fold scores under data['fold_scores']
        folds = np.asarray(data.get("fold_scores") or [], dtype=float)
        if folds.size >= 2:
            z = float((score - float(baseline_equal_mean)) / (folds.std(ddof=1) + 1e-12))
            if z < float(min_z):
                raise MymlfwError(
                    "MULTITASK_Z",
                    f"z={z:.4g} < min_z={min_z}.",
                    z=z,
                )
    return {"ok": True, "equal_mean": score, "delta": delta, "z": z}
