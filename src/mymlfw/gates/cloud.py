"""Local champion gate before cloud GPU spend."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from mymlfw.errors import MymlfwError

DEFAULT_MIN_PARAMS = 300_000
DEFAULT_MIN_DELTA = 0.5


def cloud_blocked_payload(
    *,
    reason: str,
    details: dict[str, Any] | None = None,
) -> dict[str, Any]:
    body = {
        "error_code": "CLOUD_BLOCKED",
        "message": reason,
        "suggested_fix": (
            "Train locally on MPS Fold-0 (full fold, >=300k params, decreasing loss) "
            "and beat CHAMPION by the contest Δ before launch_cloud_runner."
        ),
    }
    if details:
        body["details"] = details
    return body


def load_local_probe_record(path) -> dict[str, Any]:
    p = Path(path)
    if not p.is_file():
        raise MymlfwError("CLOUD_BLOCKED", "Local probe record missing.", path=str(p))
    data = json.loads(p.read_text())
    if not isinstance(data, dict):
        raise MymlfwError("CLOUD_BLOCKED", "Local probe record must be a JSON object.")
    return data


def assert_local_champion_gate(
    record: dict[str, Any] | str | Path,
    *,
    min_params: int = DEFAULT_MIN_PARAMS,
    min_delta: float = DEFAULT_MIN_DELTA,
    require_device: str = "mps",
) -> dict[str, Any]:
    """Raise ``MymlfwError(CLOUD_BLOCKED)`` unless local probe clears anti-waste rules."""
    data = load_local_probe_record(record) if not isinstance(record, dict) else dict(record)
    device = str(data.get("device") or "").lower()
    if require_device and device != str(require_device).lower():
        raise MymlfwError(
            "CLOUD_BLOCKED",
            f"Local probe device must be {require_device!r}.",
            device=device,
        )
    if not data.get("fold0"):
        raise MymlfwError("CLOUD_BLOCKED", "Local probe must be Fold-0.")
    if data.get("subsampled"):
        raise MymlfwError("CLOUD_BLOCKED", "Full fold required (no subsample).")
    params = int(data.get("trainable_params") or 0)
    if params < int(min_params):
        raise MymlfwError(
            "CLOUD_BLOCKED",
            f"Need trainable_params >= {min_params}.",
            trainable_params=params,
        )
    if not data.get("loss_decreasing"):
        raise MymlfwError("CLOUD_BLOCKED", "Train loss must be decreasing.")
    delta = float(data.get("delta_vs_champion") or 0.0)
    if delta < float(min_delta):
        raise MymlfwError(
            "CLOUD_BLOCKED",
            f"Need delta_vs_champion >= {min_delta}.",
            delta_vs_champion=delta,
        )
    return {
        "ok": True,
        "device": device,
        "trainable_params": params,
        "delta_vs_champion": delta,
    }


RUNPOD_EXIT_TRAP = """# myMLFW cloud anti-waste — terminate pod on any exit (not stop)
# Usage: POD_ID=... WORKSPACE=... MAC_SYNC=... bash -c "$(cat <<'EOF'
trap 'sync_artifacts_to_mac; rm -rf \"$WORKSPACE/data\"; runpodctl remove pod \"$POD_ID\"' EXIT
timeout \"${TIMEOUT:-4h}\" \"$@\"
# EOF
)"
"""
