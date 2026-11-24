"""CASMI / ranked-contest ops helpers used by MCP (no driver IO in mcp/)."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from mymlfw.errors import MymlfwError
from mymlfw.gates.canary import diff_ranked_submissions, dual_canary

# Kernel notebook cell / log smells that wasted CASMI GPU waves (v178–v181)
DUMMY_RUN_PATTERNS = (
    re.compile(r"\bIS_RERUN\s*=\s*True\b", re.I),
    re.compile(r"\bFAST_COMMIT\s*=\s*True\b", re.I),
    re.compile(r"\benable_gpu\s*=\s*False\b", re.I),
    re.compile(r"alcohol\s*csv", re.I),
)

# SpecFold commercial track — flag known non-commercial / restricted libs
CASMI_LICENSE_SCRUB = (
    ("GNPS", "BLOCKED_NONCOMMERCIAL"),
    ("NIST", "BLOCKED_NONCOMMERCIAL"),
    ("SpecFold", "UNVERIFIED_LICENSE"),
)


def detect_dummy_kernel_run(text: str) -> dict[str, Any]:
    hits = [p.pattern for p in DUMMY_RUN_PATTERNS if p.search(text or "")]
    return {
        "dummy_risk": bool(hits),
        "hits": hits,
        "suggested_fix": (
            "Refuse GPU submit: clear IS_RERUN/FAST_COMMIT dummies and enable_gpu "
            "before kernel-linked submit."
            if hits
            else None
        ),
    }


def append_vault_law(vault_path, *, law_id: str, text: str) -> dict[str, Any]:
    """Append a short law line to a local vault markdown file.

    Refuses path traversal in ``law_id`` and only writes files whose basename
    looks like a knowledge vault (``*VAULT*.md`` / ``PROPRIETARY_KNOWLEDGE_VAULT.md``).
    """
    lid = str(law_id or "").strip()
    if not lid or any(ch in lid for ch in ("/", "\\", "\0", "..")):
        raise MymlfwError(
            "VAULT_LAW_ID",
            "law_id must be a short heading without path separators.",
            law_id=law_id,
        )
    path = Path(vault_path).expanduser()
    name_upper = path.name.upper()
    if path.suffix.lower() not in {".md", ".txt"} or (
        "VAULT" not in name_upper and name_upper != "PROPRIETARY_KNOWLEDGE_VAULT.MD"
    ):
        raise MymlfwError(
            "VAULT_PATH",
            "Refuse write: vault_path basename must be *VAULT*.md "
            "(e.g. PROPRIETARY_KNOWLEDGE_VAULT.md).",
            path=str(path),
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    line = f"\n## {lid}\n\n{text.strip()}\n"
    if path.exists():
        existing = path.read_text(encoding="utf-8")
        if lid in existing and text.strip() in existing:
            return {"ok": True, "path": str(path), "deduped": True}
        path.write_text(existing + line, encoding="utf-8")
    else:
        path.write_text(f"# Knowledge vault\n{line}", encoding="utf-8")
    return {"ok": True, "path": str(path), "deduped": False, "law_id": lid}


def public_code_badge_note(
    *, title_score: float | None, observed_score: float | None
) -> dict[str, Any]:
    """Surface badge≠score (e.g. title 0.505 / often 0.501)."""
    if title_score is None or observed_score is None:
        return {"badge_ne_score": None, "message": "Pass title_score and observed_score."}
    gap = float(title_score) - float(observed_score)
    return {
        "badge_ne_score": abs(gap) >= 0.002,
        "title_score": float(title_score),
        "observed_score": float(observed_score),
        "gap": gap,
        "message": (
            f"Title badge {title_score} ≠ observed {observed_score} (gap {gap:+.4f}). "
            "Do not treat notebook title as LB truth."
            if abs(gap) >= 0.002
            else "Title badge matches observed within 0.002."
        ),
    }


def parse_kernel_status_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """Normalize Kaggle kernel/submit lifecycle fields for agents."""
    status = str(payload.get("status") or payload.get("kernel_status") or "")
    err = payload.get("error") or payload.get("failureMessage") or payload.get("gpu_error")
    dummy = detect_dummy_kernel_run(json.dumps(payload))
    return {
        "status": status,
        "error": err,
        "dummy_run": dummy,
        "enable_gpu": payload.get("enable_gpu"),
        "is_rerun": payload.get("IS_RERUN") or payload.get("is_rerun"),
        "fast_commit": payload.get("FAST_COMMIT") or payload.get("fast_commit"),
    }


def inspect_kernel_source(source: str) -> dict[str, Any]:
    """Pre-submit inspect: dummy flags + enable_gpu smell.

    ``ship_ok`` is false only when dummy risk hits OR ``enable_gpu=False`` is
    explicit. Absence of ``enable_gpu=True`` is not a refuse (metadata may set GPU).
    """
    text = source or ""
    dummy = detect_dummy_kernel_run(text)
    enable_gpu_false = bool(re.search(r"\benable_gpu\s*=\s*False\b", text, re.I))
    enable_gpu_true = bool(re.search(r"\benable_gpu\s*=\s*True\b", text, re.I))
    return {
        **dummy,
        "enable_gpu_true": enable_gpu_true,
        "enable_gpu_false": enable_gpu_false,
        "ship_ok": (not dummy["dummy_risk"]) and (not enable_gpu_false),
    }


def scrub_casmi_credits(credits: list[dict[str, Any]]) -> dict[str, Any]:
    """Flag GNPS/NIST/SpecFold credits for commercial-track license gate."""
    flagged = []
    out = []
    for c in credits:
        name = str(c.get("name") or "")
        row = dict(c)
        for needle, status in CASMI_LICENSE_SCRUB:
            if needle.lower() in name.lower():
                row["status"] = status
                row.setdefault("license_note", f"CASMI scrub matched {needle}")
                flagged.append({"name": name, "status": status, "needle": needle})
                break
        out.append(row)
    return {"credits": out, "flagged": flagged, "n_flagged": len(flagged)}


def submit_lifecycle_snapshot(
    *,
    submissions: list[dict[str, Any]] | None = None,
    kernels: list[dict[str, Any]] | None = None,
    kernel_source: str | None = None,
) -> dict[str, Any]:
    """Poll-shaped summary: recent submissions/LB rows + kernel dummy/GPU errors."""
    subs = list(submissions or [])
    kerns = [parse_kernel_status_payload(k) for k in (kernels or [])]
    gpu_errors = [k for k in kerns if k.get("error")]
    inspect = inspect_kernel_source(kernel_source) if kernel_source else None
    return {
        "n_submissions": len(subs),
        "recent_submissions": subs[:10],
        "kernels": kerns[:10],
        "gpu_errors": gpu_errors[:5],
        "kernel_inspect": inspect,
        "refuse_submit": bool(
            (inspect and not inspect.get("ship_ok"))
            or any(k.get("dummy_run", {}).get("dummy_risk") for k in kerns)
        ),
    }


def run_dual_canary(**kwargs: Any) -> dict[str, Any]:
    return dual_canary(**kwargs)


def run_diff_ranked(path_a, path_b, **kwargs: Any) -> dict[str, Any]:
    return diff_ranked_submissions(path_a, path_b, **kwargs)


def refresh_kaggle_intel_for_project(
    store: Any,
    *,
    workspace_id: str,
    project_id: str,
    competition: str,
    live: bool = True,
    discussions: list | None = None,
    kernels: list | None = None,
    token: str = "",
) -> dict[str, Any]:
    """MCP-facing refresh: live Kaggle sync or cache payload → brain intel."""
    from mymlfw.saas.kaggle_client import KaggleClientError
    from mymlfw.saas.kaggle_service import refresh_intel_cache, sync_competition_from_kaggle

    if not live:
        panel = refresh_intel_cache(
            competition=competition,
            discussions=list(discussions or []),
            kernels=list(kernels or []),
            refreshed_by="mcp_cache",
        )
    else:
        try:
            panel = sync_competition_from_kaggle(
                competition=competition, token=token or ""
            )
        except KaggleClientError as exc:
            raise MymlfwError(str(exc.code), str(exc.message)) from exc
        except Exception as exc:  # noqa: BLE001 — surface as structured error
            raise MymlfwError("kaggle_refresh_failed", str(exc)) from exc
    # Strip secrets before store
    clean = {k: v for k, v in panel.items() if not str(k).startswith("_")}
    if hasattr(store, "set_kaggle_intel"):
        store.set_kaggle_intel(workspace_id, project_id, clean)
    return clean
