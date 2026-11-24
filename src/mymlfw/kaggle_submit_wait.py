"""Optional: competitions submit then wait for public score → ledger."""

from __future__ import annotations

import json
import subprocess
import time
from pathlib import Path
from typing import Any

from mymlfw.campaign.ledger import record_public_score
from mymlfw.errors import MymlfwError
from mymlfw.kaggle_notebook import prefer_csv_payload_sha


def submit_and_wait(
    *,
    competition: str,
    file_path,
    ledger_path,
    experiment_id: str,
    message: str = "mymlfw submit-wait",
    kernel: str | None = None,
    poll_seconds: float = 30.0,
    timeout_seconds: float = 900.0,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Shell out to ``kaggle competitions submit`` then poll submissions list.

    Requires the official ``kaggle`` CLI on PATH. Writes public score back via
    ``record_public_score``. Prefer CSV payload SHA for zip artifacts.
    """
    path = Path(file_path)
    if not path.is_file():
        raise MymlfwError("BAD_SUBMIT", "Submission file missing.", path=str(path))
    sha = prefer_csv_payload_sha(path)
    if dry_run:
        return {
            "ok": True,
            "dry_run": True,
            "competition": competition,
            "file": str(path),
            "payload_sha": sha,
            "kernel": kernel,
        }
    cmd = [
        "kaggle",
        "competitions",
        "submit",
        "-c",
        competition,
        "-f",
        str(path),
        "-m",
        message,
    ]
    if kernel:
        cmd.extend(["-k", kernel])
    try:
        proc = subprocess.run(cmd, check=False, capture_output=True, text=True)
    except FileNotFoundError as exc:
        raise MymlfwError(
            "KAGGLE_CLI",
            "Install the kaggle CLI and authenticate before submit-wait.",
            suggested_fix="pip install kaggle && kaggle config set -n …",
        ) from exc
    if proc.returncode != 0:
        raise MymlfwError(
            "KAGGLE_SUBMIT",
            "kaggle competitions submit failed.",
            stderr=(proc.stderr or "")[:500],
            stdout=(proc.stdout or "")[:500],
        )
    deadline = time.monotonic() + float(timeout_seconds)
    last: dict[str, Any] = {}
    while time.monotonic() < deadline:
        list_cmd = [
            "kaggle",
            "competitions",
            "submissions",
            "-c",
            competition,
            "-v",
            "--csv",
        ]
        listed = subprocess.run(list_cmd, check=False, capture_output=True, text=True)
        text = listed.stdout or ""
        # Best-effort parse: look for a numeric public score on the newest line
        score = _parse_newest_public_score(text)
        last = {"raw_head": text[:400], "public_score": score}
        if score is not None:
            row = record_public_score(ledger_path, experiment_id, float(score))
            return {
                "ok": True,
                "public_score": float(score),
                "payload_sha": sha,
                "ledger_row": {
                    "experiment_id": row.get("experiment_id"),
                    "verdict": row.get("verdict"),
                    "public_score": row.get("public_score"),
                },
                "submit_stdout": (proc.stdout or "")[:300],
            }
        time.sleep(float(poll_seconds))
    raise MymlfwError(
        "KAGGLE_SCORE_TIMEOUT",
        "Timed out waiting for public score.",
        last=last,
        timeout_seconds=timeout_seconds,
    )


def _parse_newest_public_score(csv_text: str) -> float | None:
    lines = [ln for ln in (csv_text or "").splitlines() if ln.strip()]
    if len(lines) < 2:
        return None
    # header + rows; try json fallback
    try:
        import csv
        from io import StringIO

        rows = list(csv.DictReader(StringIO(csv_text)))
        if not rows:
            return None
        row = rows[0]
        for key in ("publicScore", "public_score", "score", "PublicScore"):
            if key in row and row[key] not in (None, "", "None"):
                return float(row[key])
    except Exception:  # noqa: BLE001
        pass
    # bare float somewhere
    for token in lines[1].replace(",", " ").split():
        try:
            return float(token)
        except ValueError:
            continue
    return None
