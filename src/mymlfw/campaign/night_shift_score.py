"""Night-Shift score-only jobs — never submit to Kaggle."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from mymlfw.errors import MymlfwError
from mymlfw.gates.canary import dual_canary


def run_score_only_canary(
    *,
    panel_path,
    hubs_path,
    submission_path,
    out_dir,
    label: str = "R0",
    baseline_panel_mrr: float | None = None,
    baseline_hubs_mrr: float | None = None,
) -> dict[str, Any]:
    """Budgeted R0/R1/R2 style overnight score; writes morning digest JSON. Never submits."""
    if str(label).upper() not in {"R0", "R1", "R2", "R3"}:
        raise MymlfwError("NIGHT_SHIFT_LABEL", "Use R0/R1/R2/R3 labels.", label=label)
    report = dual_canary(
        panel_path=panel_path,
        hubs_path=hubs_path,
        submission_path=submission_path,
        baseline_panel_mrr=baseline_panel_mrr,
        baseline_hubs_mrr=baseline_hubs_mrr,
    )
    digest = {
        "kind": "night_shift_score_only",
        "label": label.upper(),
        "scored_at": datetime.now(timezone.utc).isoformat(),
        "submit": False,
        "canary": report,
        "morning_digest": (
            f"{label}: {report['verdict']} "
            f"panelΔ={report['panel']['delta_mrr']:.4f} "
            f"hubsΔ={report['hubs']['delta_mrr']:.4f} "
            f"R1_L panel={report['panel']['r1_losses']} hubs={report['hubs']['r1_losses']}"
        ),
    }
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    path = out / f"night_shift_{label.upper()}_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}.json"
    path.write_text(json.dumps(digest, indent=2, sort_keys=True) + "\n")
    digest["path"] = str(path)
    return digest
