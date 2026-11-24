"""Notebook / kernel code-SHA compare for fire refuse."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from mymlfw.errors import MymlfwError


def _cell_source(cell: dict[str, Any]) -> str:
    src = cell.get("source", "")
    if isinstance(src, list):
        return "".join(src)
    return str(src)


def notebook_code_sha(path) -> str:
    """SHA256 over concatenated code-cell sources (stable across metadata noise)."""
    nb = json.loads(Path(path).read_text(encoding="utf-8"))
    cells = nb.get("cells") or []
    parts = []
    for cell in cells:
        if cell.get("cell_type") != "code":
            continue
        parts.append(_cell_source(cell))
    blob = "\n\n".join(parts).encode("utf-8")
    return hashlib.sha256(blob).hexdigest()


def payload_sha256(path) -> str:
    data = Path(path).read_bytes()
    return hashlib.sha256(data).hexdigest()


def prefer_csv_payload_sha(path) -> dict[str, str]:
    """Prefer inner CSV SHA when path is a zip that auto-extracts on Kaggle."""
    p = Path(path)
    digest = payload_sha256(p)
    result = {"path": str(p), "sha256": digest, "kind": "file"}
    if p.suffix.lower() == ".zip":
        import zipfile

        with zipfile.ZipFile(p) as zf:
            csv_members = [n for n in zf.namelist() if n.lower().endswith(".csv")]
            if len(csv_members) == 1:
                data = zf.read(csv_members[0])
                result = {
                    "path": str(p),
                    "member": csv_members[0],
                    "sha256": hashlib.sha256(data).hexdigest(),
                    "kind": "zip_csv_payload",
                }
    return result


def verify_notebook(*, ref_path, cand_path) -> dict[str, Any]:
    """Compare two local notebooks → IDENTICAL | FACTORIAL_DIFF | UNRELATED."""
    ref = Path(ref_path)
    cand = Path(cand_path)
    if not ref.is_file() or not cand.is_file():
        raise MymlfwError(
            "NOTEBOOK_MISSING",
            "Both --ref and --vs notebook paths must exist (download ref first).",
            ref=str(ref),
            vs=str(cand),
        )
    ref_sha = notebook_code_sha(ref)
    cand_sha = notebook_code_sha(cand)
    if ref_sha == cand_sha:
        return {
            "status": "IDENTICAL",
            "ref_sha": ref_sha,
            "cand_sha": cand_sha,
            "diff_cells": [],
        }
    ref_nb = json.loads(ref.read_text(encoding="utf-8"))
    cand_nb = json.loads(cand.read_text(encoding="utf-8"))
    ref_cells = [c for c in (ref_nb.get("cells") or []) if c.get("cell_type") == "code"]
    cand_cells = [c for c in (cand_nb.get("cells") or []) if c.get("cell_type") == "code"]
    diffs: list[dict[str, Any]] = []
    n = max(len(ref_cells), len(cand_cells))
    for i in range(n):
        a = _cell_source(ref_cells[i]) if i < len(ref_cells) else None
        b = _cell_source(cand_cells[i]) if i < len(cand_cells) else None
        if a != b:
            diffs.append({"index": i, "ref_len": 0 if a is None else len(a), "cand_len": 0 if b is None else len(b)})
    # Heuristic: many shared cells → factorial edit; few → unrelated
    shared = n - len(diffs)
    status = "FACTORIAL_DIFF" if shared >= max(1, n // 3) else "UNRELATED"
    return {
        "status": status,
        "ref_sha": ref_sha,
        "cand_sha": cand_sha,
        "diff_cells": diffs,
        "n_code_cells_ref": len(ref_cells),
        "n_code_cells_cand": len(cand_cells),
    }
