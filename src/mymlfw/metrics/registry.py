"""Pluggable higher-is-better scorers for blend optimize and gates."""

from __future__ import annotations

import importlib
import math
from collections.abc import Callable
from typing import Any

import numpy as np

from mymlfw.errors import MymlfwError

Scorer = Callable[..., float]

_REGISTRY: dict[str, Scorer] = {}


def register_scorer(name: str, fn: Scorer) -> Scorer:
    key = str(name).strip()
    if not key:
        raise MymlfwError("BAD_SCORER", "Scorer name is required.")
    _REGISTRY[key] = fn
    return fn


def list_scorers() -> list[str]:
    return sorted(_REGISTRY)


def resolve_scorer(spec: str) -> Scorer:
    """Resolve ``builtin_name`` or ``module.path:callable``."""
    text = str(spec).strip()
    if not text:
        raise MymlfwError("BAD_SCORER", "Pass --metric or --scorer.")
    if text in _REGISTRY:
        return _REGISTRY[text]
    if ":" in text:
        module_name, _, attr = text.partition(":")
        try:
            mod = importlib.import_module(module_name)
            fn = getattr(mod, attr)
        except Exception as exc:  # noqa: BLE001 — surface as BAD_SCORER
            raise MymlfwError(
                "BAD_SCORER",
                "Could not import scorer path:callable.",
                scorer=text,
                detail=str(exc),
            ) from exc
        if not callable(fn):
            raise MymlfwError("BAD_SCORER", "Scorer attribute is not callable.", scorer=text)
        return fn
    raise MymlfwError(
        "BAD_SCORER",
        "Unknown scorer. Use a built-in name or module.path:callable.",
        scorer=text,
        known=list_scorers(),
    )


def safe_score(fn: Scorer, *args: Any, **kwargs: Any) -> float:
    value = float(fn(*args, **kwargs))
    if not math.isfinite(value):
        raise MymlfwError("BAD_METRIC", "Scorer returned NaN/Inf.", value=value)
    return value


def _score_log_loss(y_true, bundle, **_meta) -> float:
    from mymlfw.blend.optimize import score_bundle

    return score_bundle(y_true, bundle, "log_loss")


def _score_accuracy(y_true, bundle, **_meta) -> float:
    from mymlfw.blend.optimize import score_bundle

    return score_bundle(y_true, bundle, "accuracy")


def _score_balanced_accuracy(y_true, bundle, **_meta) -> float:
    from mymlfw.blend.optimize import score_bundle

    return score_bundle(y_true, bundle, "balanced_accuracy")


def balanced_accuracy_full_imb(
    y_true_full,
    pred_full,
    y_true_imb,
    pred_imb,
    classes,
    *,
    reduce: str = "min",
) -> float:
    """Joint Full∧Imb balanced accuracy (min or mean of the two panels)."""
    from mymlfw.metrics import balanced_accuracy

    full = balanced_accuracy(y_true_full, pred_full, classes)
    imb = balanced_accuracy(y_true_imb, pred_imb, classes)
    if reduce == "mean":
        return float((full + imb) / 2.0)
    return float(min(full, imb))


def ocf_equal_mean(task_scores: list[float] | np.ndarray, **_meta) -> float:
    """Equal-mean across task slots: S=(S1+…+Sk)/k (not N-weighted)."""
    arr = np.asarray(task_scores, dtype=float).ravel()
    if arr.size == 0:
        raise MymlfwError("BAD_METRIC", "ocf_equal_mean needs at least one task score.")
    if not np.isfinite(arr).all():
        raise MymlfwError("BAD_METRIC", "ocf_equal_mean rejects NaN/Inf task scores.")
    return float(np.mean(arr))


def _score_png_parity(y_true, bundle, **meta) -> float:
    from mymlfw.metrics.siclink import png_parity_bundle

    return png_parity_bundle(y_true, bundle, **meta)


register_scorer("log_loss", _score_log_loss)
register_scorer("accuracy", _score_accuracy)
register_scorer("balanced_accuracy", _score_balanced_accuracy)
register_scorer("balanced_accuracy_full_imb", balanced_accuracy_full_imb)
register_scorer("ocf_equal_mean", ocf_equal_mean)
register_scorer("png_parity", _score_png_parity)
