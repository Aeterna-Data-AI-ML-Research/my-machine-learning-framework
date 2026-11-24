"""NTL / contest-enforcer status snapshot for MCP (no Mongo in mcp handlers)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from mymlfw.campaign.fire_planner import default_state, load_fire_state, plan_snapshot


def read_ntl_status(
    *,
    contest_dir: str | None = None,
    fire_state_path: str | None = None,
    gate_json_path: str | None = None,
    pin_id: str | None = None,
) -> dict[str, Any]:
    """Assemble pin / candidates / last gate / fire planner for agents."""
    root = Path(contest_dir).resolve() if contest_dir else None
    fire_path = (
        Path(fire_state_path)
        if fire_state_path
        else (root / "artifacts" / "fire_planner.json" if root else None)
    )
    gate_path = (
        Path(gate_json_path)
        if gate_json_path
        else (root / "artifacts" / "last_gate.json" if root else None)
    )

    if fire_path is None:
        fire = plan_snapshot(default_state())
    else:
        fire = plan_snapshot(load_fire_state(fire_path))

    last_gate = None
    if gate_path and gate_path.is_file():
        last_gate = json.loads(gate_path.read_text())

    held: list[str] = []
    if root:
        for name in ("candidates", "cand", "held_candidates"):
            d = root / name
            if d.is_dir():
                held = sorted(p.name for p in d.iterdir() if p.is_dir())
                break

    pin = pin_id
    if pin is None and root:
        for candidate in (
            root / "artifacts" / "CURRENT_PIN.txt",
            root / "FIRE_KERNEL_VERSIONS.json",
        ):
            if candidate.is_file():
                if candidate.suffix == ".json":
                    try:
                        data = json.loads(candidate.read_text())
                        pin = str(data.get("live") or data.get("pin_id") or candidate.name)
                    except json.JSONDecodeError:
                        pin = candidate.name
                else:
                    pin = candidate.read_text().strip() or candidate.name
                break

    return {
        "ok": True,
        "pin_id": pin,
        "contest_dir": str(root) if root else None,
        "held_candidates": held,
        "n_rem": fire.get("n_rem_submits"),
        "n_rem_gpu": fire.get("n_rem_gpu"),
        "live_kernel_sha": fire.get("live_pin_sha"),
        "last_gate": last_gate,
        "fire_planner": fire,
        "feature": "contest_enforcer",
    }
