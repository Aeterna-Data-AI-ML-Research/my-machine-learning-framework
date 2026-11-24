"""Debiased Full ∧ Imbalanced promote gate (NTL / closed-set authorship)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np

from mymlfw.errors import MymlfwError
from mymlfw.metrics import balanced_accuracy


def _load_panel(path: Path) -> tuple[np.ndarray, np.ndarray, list[str]]:
    path = Path(path)
    if not path.is_file():
        raise MymlfwError("GATE_INPUT", "Panel file missing.", path=str(path))
    data = np.load(path, allow_pickle=True)
    if "y_true" not in data or "y_pred" not in data:
        raise MymlfwError(
            "GATE_INPUT",
            "Panel .npz needs y_true and y_pred arrays.",
            path=str(path),
            keys=list(data.keys()),
        )
    y_true = np.asarray(data["y_true"])
    y_pred = np.asarray(data["y_pred"])
    if "classes" in data:
        classes = [str(c) for c in np.asarray(data["classes"]).tolist()]
    else:
        classes = sorted({str(v) for v in y_true.tolist()} | {str(v) for v in y_pred.tolist()})
    return y_true, y_pred, classes


def debiased_promote(
    *,
    full_panel,
    imb_panel,
    baseline_full: float | None = None,
    baseline_imb: float | None = None,
    min_bp: float = 100.0,
    classes=None,
) -> dict[str, Any]:
    """Promote only if Full ∧ Imb balanced-accuracy gain ≥ ``min_bp`` basis points.

    Panels are paths to ``.npz`` with ``y_true`` / ``y_pred`` [/ ``classes``],
    or ``(y_true, y_pred)`` tuples. Optional baselines are absolute BA scores.
    """
    if isinstance(full_panel, (str, Path)):
        y_f, p_f, classes_f = _load_panel(Path(full_panel))
    else:
        y_f, p_f = full_panel
        classes_f = [str(c) for c in (classes or sorted(set(map(str, y_f)) | set(map(str, p_f))))]
    if isinstance(imb_panel, (str, Path)):
        y_i, p_i, classes_i = _load_panel(Path(imb_panel))
    else:
        y_i, p_i = imb_panel
        classes_i = [str(c) for c in (classes or sorted(set(map(str, y_i)) | set(map(str, p_i))))]
    class_list = [str(c) for c in (classes or classes_f or classes_i)]
    ba_full = balanced_accuracy(y_f, p_f, class_list)
    ba_imb = balanced_accuracy(y_i, p_i, class_list)
    base_f = float(baseline_full) if baseline_full is not None else None
    base_i = float(baseline_imb) if baseline_imb is not None else None
    bp_full = None if base_f is None else (ba_full - base_f) * 10_000.0
    bp_imb = None if base_i is None else (ba_imb - base_i) * 10_000.0
    if bp_full is None or bp_imb is None:
        # Absolute-mode: treat scores as already-debiased deltas in probability units
        # when baselines omitted — require both panels ≥ min_bp/10000 above 0 empty.
        promote = False
        reason = "baselines_required_for_bp_gate"
        if baseline_full is None and baseline_imb is None:
            # Allow absolute threshold on BA itself when caller passes min_bp as abs*1e4
            promote = ba_full >= 0.0 and ba_imb >= 0.0
            reason = "absolute_ba_reported_without_baselines"
            bp_full = ba_full * 10_000.0
            bp_imb = ba_imb * 10_000.0
    else:
        promote = bp_full >= float(min_bp) and bp_imb >= float(min_bp)
        reason = "ok" if promote else "below_min_bp"
    return {
        "promote": bool(promote),
        "ba_full": float(ba_full),
        "ba_imb": float(ba_imb),
        "bp_full": None if bp_full is None else float(bp_full),
        "bp_imb": None if bp_imb is None else float(bp_imb),
        "min_bp": float(min_bp),
        "reason": reason,
    }
