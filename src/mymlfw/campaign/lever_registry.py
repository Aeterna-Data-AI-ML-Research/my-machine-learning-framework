"""One-variable lever registry — auto-kill confirmed-large-gap knobs."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from mymlfw.campaign.ledger import load_ledger
from mymlfw.errors import MymlfwError

# CASMI / SpecFold knobs commonly re-shipped as noise forks
DEFAULT_CASMI_KNOBS = (
    "_AP_KEEP1",
    "_NPX_LAM",
    "SpecFold_LOCK",
    "N-1c_LAM",
    "AP_LAM0.65",
    "iso_v5",
)


def load_lever_registry(path) -> dict[str, Any]:
    p = Path(path)
    if not p.exists():
        return {"schema_version": 1, "levers": {}, "killed": []}
    data = json.loads(p.read_text())
    if not isinstance(data, dict):
        raise MymlfwError("LEVER_REGISTRY", "Registry must be a JSON object.")
    data.setdefault("schema_version", 1)
    data.setdefault("levers", {})
    data.setdefault("killed", [])
    return data


def save_lever_registry(path, data: dict[str, Any]) -> Path:
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n")
    return out


def register_lever(
    data: dict[str, Any],
    *,
    variable: str,
    band_low: float,
    band_high: float,
    experiment_id: str | None = None,
) -> dict[str, Any]:
    levers = dict(data.get("levers") or {})
    if variable in levers and levers[variable].get("status") == "killed":
        raise MymlfwError(
            "LEVER_KILLED",
            "Variable was auto-killed after confirmed-large-gap — pick a new knob.",
            variable=variable,
        )
    levers[str(variable)] = {
        "band_low": float(band_low),
        "band_high": float(band_high),
        "experiment_id": experiment_id,
        "status": "open",
    }
    data = dict(data)
    data["levers"] = levers
    return data


_KILL_VERDICTS = {
    "kill",
    "confirmed-large-gap",
    "noise",
    "DUPLICATE_CODE",
}


def sync_kills_from_ledger(data: dict[str, Any], ledger_path) -> dict[str, Any]:
    """Mark registry levers killed when ledger verdict is a closed kill/noise/gap."""
    rows = load_ledger(ledger_path)
    data = dict(data)
    levers = dict(data.get("levers") or {})
    killed = list(data.get("killed") or [])
    for row in rows:
        if row.get("verdict") not in _KILL_VERDICTS:
            continue
        var = row.get("variable") or ""
        if not var:
            continue
        entry = levers.get(var) or {"band_low": None, "band_high": None}
        entry["status"] = "killed"
        entry["experiment_id"] = row.get("experiment_id")
        entry["verdict"] = row.get("verdict")
        levers[var] = entry
        if var not in killed:
            killed.append(var)
    data["levers"] = levers
    data["killed"] = killed
    return data


def auto_kill_large_gap_probes(ledger_path) -> list[dict[str, str]]:
    """List closed large-gap / noise rows for registry sync — never rewrites ledger verdicts."""
    rows = load_ledger(ledger_path)
    return [
        {
            "experiment_id": str(row.get("experiment_id") or ""),
            "variable": str(row.get("variable") or ""),
            "verdict": str(row.get("verdict") or ""),
        }
        for row in rows
        if row.get("verdict") in _KILL_VERDICTS and row.get("variable")
    ]
