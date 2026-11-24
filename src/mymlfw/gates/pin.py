"""NTL / code-comp pin laws as machine checks."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml

from mymlfw.errors import MymlfwError

DEFAULT_PIN: dict[str, Any] = {
    "min_bp": 100.0,
    "append_only_candidate_dirs": True,
    "protected_paths": ["FIRE_KERNEL_VERSIONS.json"],
    "mount_allowlist": {"llama": ["alexchilton/"]},
    "banned_mount_patterns": ["metaresearch", "copytree-32GB", "copytree_32gb"],
    "post_defaults": {"mode": "damped_sinkhorn", "post": 0},
    "banned_post": ["hungarian", "uniform_sinkhorn_1.0", "sinkhorn_1.0"],
    "class_order": "model_name_string",
}


def load_pin_config(path=None) -> dict[str, Any]:
    cfg = dict(DEFAULT_PIN)
    if path is None:
        return cfg
    p = Path(path)
    if not p.is_file():
        raise MymlfwError("PIN_CONFIG", "Pin config file missing.", path=str(p))
    raw = yaml.safe_load(p.read_text()) or {}
    if not isinstance(raw, dict):
        raise MymlfwError("PIN_CONFIG", "Pin config must be a mapping.")
    cfg.update(raw)
    return cfg


def check_ntl_pin_laws(
    *,
    contest_dir,
    candidate_dir=None,
    mount_specs: list[str] | None = None,
    post_mode: str | None = None,
    post_value: float | None = None,
    overwrite_paths: list[str] | None = None,
    pin_config=None,
) -> dict[str, Any]:
    """Return ``{ok, violations[]}``. Raises nothing — callers decide refuse vs warn."""
    root = Path(contest_dir).resolve()
    cfg = pin_config if isinstance(pin_config, dict) else load_pin_config(pin_config)
    violations: list[dict[str, str]] = []

    for name in cfg.get("protected_paths") or []:
        protected = root / name
        if overwrite_paths:
            for raw in overwrite_paths:
                target = Path(raw)
                if not target.is_absolute():
                    target = (root / target).resolve()
                if protected.exists() and target.resolve() == protected.resolve():
                    violations.append(
                        {
                            "code": "PROTECTED_PIN_OVERWRITE",
                            "message": f"Refuse overwrite of armed pin file {name}",
                        }
                    )

    if candidate_dir is not None and cfg.get("append_only_candidate_dirs"):
        cand = Path(candidate_dir)
        if not cand.is_absolute():
            cand = (root / cand).resolve()
        if cand.exists() and any(cand.iterdir()):
            # Existing non-empty dir without explicit append marker → refuse clobber intent
            marker = cand / ".mymlfw_append_ok"
            if not marker.exists() and overwrite_paths:
                violations.append(
                    {
                        "code": "CANDIDATE_DIR_NOT_APPEND_ONLY",
                        "message": "Candidate dir exists; pass append-only workflow or .mymlfw_append_ok",
                    }
                )

    allow = cfg.get("mount_allowlist") or {}
    banned = [str(x).lower() for x in (cfg.get("banned_mount_patterns") or [])]
    for spec in mount_specs or []:
        lower = str(spec).lower()
        for pat in banned:
            if pat in lower:
                violations.append(
                    {
                        "code": "BANNED_MOUNT_PATTERN",
                        "message": f"Mount matches banned pattern {pat!r}: {spec}",
                    }
                )
        llama_ok = allow.get("llama") or []
        if "llama" in lower or "meta-llama" in lower:
            if llama_ok and not any(str(a).lower() in lower for a in llama_ok):
                violations.append(
                    {
                        "code": "MOUNT_ALLOWLIST",
                        "message": f"Llama mount must be one of {llama_ok}: {spec}",
                    }
                )

    banned_post = [str(x).lower() for x in (cfg.get("banned_post") or [])]
    if post_mode and str(post_mode).lower() in banned_post:
        violations.append(
            {
                "code": "BANNED_POST",
                "message": f"Post mode {post_mode!r} is banned under pin laws",
            }
        )
    if post_value is not None and abs(float(post_value) - 1.0) < 1e-12:
        if "uniform_sinkhorn_1.0" in banned_post or "sinkhorn_1.0" in banned_post:
            violations.append(
                {
                    "code": "BANNED_POST",
                    "message": "Uniform Sinkhorn 1.0 / --post 1.0 is banned; use damped band + --post 0",
                }
            )

    defaults = cfg.get("post_defaults") or {}
    return {
        "ok": not violations,
        "violations": violations,
        "post_defaults": defaults,
        "class_order": cfg.get("class_order", "model_name_string"),
        "min_bp": float(cfg.get("min_bp", 100.0)),
        "config_path": None if pin_config is None or isinstance(pin_config, dict) else str(pin_config),
    }


def write_gate_snapshot(path, payload: dict[str, Any]) -> Path:
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    return out
