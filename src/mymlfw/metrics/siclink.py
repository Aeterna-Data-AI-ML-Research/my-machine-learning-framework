"""SiClink / image-recon host metrics (PNG parity + OCF helpers)."""

from __future__ import annotations

import numpy as np

from mymlfw.errors import MymlfwError


def png_parity(
    y_true,
    y_pred,
    *,
    threshold: float = 128.0,
    pred_div: float = 255.0,
) -> float:
    """Pixel agreement after PNG-parity transform: pred/pred_div vs gt>=threshold.

    Higher is better. ``y_true`` / ``y_pred`` must broadcast to the same shape
    (uint8 or float pixels). Predictions are scaled by ``pred_div`` then
    binarized at 0.5; ground truth is binarized at ``threshold``.
    """
    gt = np.asarray(y_true, dtype=float)
    pred = np.asarray(y_pred, dtype=float)
    if gt.size == 0 or pred.size == 0:
        raise MymlfwError("BAD_METRIC", "png_parity needs non-empty arrays.")
    if gt.shape != pred.shape:
        raise MymlfwError(
            "BAD_METRIC",
            "png_parity requires matching shapes.",
            gt_shape=list(gt.shape),
            pred_shape=list(pred.shape),
        )
    if not np.isfinite(gt).all() or not np.isfinite(pred).all():
        raise MymlfwError("BAD_METRIC", "png_parity rejects NaN/Inf.")
    gt_bin = gt >= float(threshold)
    pred_bin = (pred / float(pred_div)) >= 0.5
    return float(np.mean(gt_bin == pred_bin))


def png_parity_bundle(y_true, bundle, **meta) -> float:
    """Blend-optimize scorer: align ``y_true`` rows to ``bundle.values``.

    Supports:
    - ``values`` shape ``(N, H*W)`` with ``y_true`` the same, or
    - ``values`` shape ``(N, H, W)`` stacked as scores kind with matching y_true.
    Class-probability bundles ``(N, C)`` are refused — use accuracy / bank-decode.
    """
    threshold = float(meta.get("threshold", 128.0))
    pred_div = float(meta.get("pred_div", 255.0))
    gt = np.asarray(y_true, dtype=float)
    pred = np.asarray(getattr(bundle, "values", bundle), dtype=float)
    if pred.ndim == 2 and gt.ndim == 1 and pred.shape[0] == gt.shape[0] and pred.shape[1] > 1:
        # Likely class scores — refuse soft proxy for Exact PNG metric
        raise MymlfwError(
            "SOFT_PROXY",
            "png_parity refuses (N,C) class scores — use Exact PNG arrays "
            "or closed-set bank-decode (soft_proxy_vs_exact_metric).",
            shape=list(pred.shape),
        )
    if gt.ndim == 1 and pred.ndim == 2 and pred.shape[0] == gt.shape[0]:
        # one flat row of pixels per id; y_true must be 2d — expand refused
        raise MymlfwError(
            "BAD_METRIC",
            "Pass y_true with the same pixel layout as bundle.values.",
            gt_shape=list(gt.shape),
            pred_shape=list(pred.shape),
        )
    if pred.ndim == 3:
        pred = pred.reshape(pred.shape[0], -1)
    if gt.ndim == 3:
        gt = gt.reshape(gt.shape[0], -1)
    if pred.ndim == 2 and gt.ndim == 2 and pred.shape == gt.shape:
        # mean over rows of per-image png_parity
        scores = [
            png_parity(gt[i], pred[i], threshold=threshold, pred_div=pred_div)
            for i in range(gt.shape[0])
        ]
        return float(np.mean(scores))
    return png_parity(gt, pred, threshold=threshold, pred_div=pred_div)


def ocf_tasks_from_scores(task_scores: dict[str, float]) -> float:
    """Equal-mean OCF over named task slots (not N-weighted)."""
    from mymlfw.metrics.registry import ocf_equal_mean

    if not task_scores:
        raise MymlfwError("BAD_METRIC", "ocf_tasks_from_scores needs task scores.")
    return ocf_equal_mean(list(task_scores.values()))
