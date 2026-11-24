"""Typed verdict / dead-end tags for advise retrieval."""

from __future__ import annotations

from pathlib import Path

TYPED_VERDICT_TAGS: tuple[str, ...] = (
    "td_uniqueness_trap",
    "soft_proxy_vs_exact_metric",
    "fold_subsample_invalid",
    "sibling_odds_rebrand",
    "typo_micro_variant",
    "o3_o4_mps_fail",
    "areeb_mix3",
    "duplicate_code_sha",
    "noise_band",
)

SINKHORN_HINTS = ("sinkhorn", "hungarian", "post α", "post alpha", "fuse", "twinhead blend")


def tag_from_note(note: str) -> list[str]:
    text = (note or "").lower()
    hits = []
    for tag in TYPED_VERDICT_TAGS:
        key = tag.replace("_", " ")
        if tag in text or key in text:
            hits.append(tag)
    if "sinkhorn" in text and "soft_proxy_vs_exact_metric" not in hits:
        hits.append("soft_proxy_vs_exact_metric")
    return hits


def ledger_kill_notes(ledger_path) -> list[str]:
    """Pull typed kill / trap tags from a contest ledger for advise retrieval."""
    path = Path(ledger_path)
    if not path.is_file():
        return []
    try:
        from mymlfw.campaign.ledger import load_ledger
    except Exception:  # noqa: BLE001
        return []
    notes: list[str] = []
    for row in load_ledger(path):
        verdict = str(row.get("verdict") or "")
        note = str(row.get("note") or "")
        variable = str(row.get("variable") or "")
        blob = f"{verdict} {note} {variable}"
        tags = tag_from_note(blob)
        if verdict in {
            "kill",
            "confirmed-large-gap",
            "noise",
            "DUPLICATE_CODE",
            *TYPED_VERDICT_TAGS,
        }:
            tags = list(dict.fromkeys([*tags, *tag_from_note(verdict)]))
            notes.append(
                f"ledger_kill:{variable}:{verdict}:{','.join(tags) or 'untagged'}:{note}"
            )
        elif tags:
            notes.append(f"ledger_tag:{variable}:{','.join(tags)}:{note}")
    return notes


def prioritize_exact_id_steps(next_steps: list[str], retrieved_notes: list[str]) -> list[str]:
    """Push L1/L2/exact-ID / OCF-bank ahead of Sinkhorn-grid suggestions."""
    blob = "\n".join(retrieved_notes).lower()
    preferred = []
    deferred = []
    for step in next_steps:
        low = step.lower()
        if any(h in low for h in SINKHORN_HINTS) and (
            "exact-id" in blob or "l1 verbatim" in blob or "ocf bank" in blob or "margin079" in blob
        ):
            deferred.append(step)
        else:
            preferred.append(step)
    boost = []
    if "l1" in blob or "verbatim" in blob:
        boost.append("Run L1 verbatim pin path before any post/Sinkhorn grid.")
    if "l2" in blob or "margin079" in blob:
        boost.append("Evaluate L2 margin079 specialist before fuse/post α.")
    if "exact-id" in blob or "exact id" in blob:
        boost.append("Prefer exact-ID / contested-only specialist over uniform Sinkhorn 1.0.")
    if "ocf" in blob or "bank-decode" in blob:
        boost.append("Use closed-set bank-decode + Exact-metric MBR (not ConvNeXt defaults).")
    merged = boost + preferred + deferred
    # unique preserve order
    seen = set()
    out = []
    for item in merged:
        if item in seen:
            continue
        seen.add(item)
        out.append(item)
    return out[:8]
