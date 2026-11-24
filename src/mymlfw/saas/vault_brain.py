"""Ingest contest vault / REPORT markdown into Project Brain (dead_ends + axioms)."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from mymlfw.saas.ids import new_axiom_id
from mymlfw.saas.schemas import DeadEndCreate, DeadEndStatus

_HEADING = re.compile(r"^##\s+(.+)$", re.M)
# L10 SpecFold mid-only, iso_v5 −0.006, AP_LAM0.65 → 0.499
_LAW_ID = re.compile(r"^(L\d+|iso_\w+|AP_\w+|N-?\d\w*|SpecFold\w*|_[A-Z0-9_]+)\b", re.I)


def parse_vault_sections(text: str) -> list[dict[str, str]]:
    """Split vault markdown on ## headings into {id, body} sections."""
    parts = _HEADING.split(text or "")
    if len(parts) < 3:
        body = (text or "").strip()
        return [{"id": "vault_root", "body": body}] if body else []
    # parts[0] is preamble; then (heading, body)*
    out: list[dict[str, str]] = []
    for i in range(1, len(parts), 2):
        title = parts[i].strip()
        body = parts[i + 1].strip() if i + 1 < len(parts) else ""
        if not title:
            continue
        out.append({"id": title, "body": body})
    return out


def section_as_dead_end(section: dict[str, str]) -> DeadEndCreate | None:
    """Map a vault section to a dead-end when it looks like a killed law / knob."""
    title = section["id"]
    body = section["body"]
    lower = f"{title}\n{body}".lower()
    killish = any(
        w in lower
        for w in (
            "dead end",
            "dead-end",
            "kill",
            "do not",
            "never",
            "confirmed-large-gap",
            "noise",
            "−0.",
            "-0.",
            "mid-only",
            "metabolic",
        )
    )
    if not killish and not _LAW_ID.match(title):
        return None
    variable = title[:240]
    lesson = (body or title)[:2000]
    if not lesson.strip():
        return None
    return DeadEndCreate(
        variable=variable,
        lesson=lesson,
        status=DeadEndStatus.active_block,
    )


def section_as_axiom(section: dict[str, str], *, project_id: str) -> dict[str, Any] | None:
    title = section["id"]
    body = (section["body"] or "").strip()
    if not (_LAW_ID.match(title) or title.upper().startswith("L")):
        return None
    statement = f"{title}: {body.splitlines()[0] if body else title}".strip()[:500]
    return {
        "_id": new_axiom_id(),
        "project_id": project_id,
        "statement": statement,
        "evidence_count": 1,
        "pinned": True,
        "epoch_id": "vault_ingest",
        "source": "vault",
        "law_id": title,
    }


def ingest_vault_paths(
    store: Any,
    *,
    workspace_id: str,
    project_id: str,
    paths: list,
) -> dict[str, Any]:
    """Parse vault/REPORT files into BRAIN_STORE dead_ends + axioms."""
    added_dead = 0
    added_ax = 0
    skipped = 0
    existing_vars = {
        str(d.get("variable") or "")
        for d in store.dead_ends.get(project_id, [])
    }
    existing_laws = {
        str(a.get("law_id") or a.get("statement") or "")
        for a in store.axioms.get(project_id, [])
    }
    for raw in paths:
        path = Path(raw)
        if not path.is_file():
            skipped += 1
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        for section in parse_vault_sections(text):
            ded = section_as_dead_end(section)
            if ded and ded.variable not in existing_vars:
                store.add_dead_end(workspace_id, project_id, ded)
                existing_vars.add(ded.variable)
                added_dead += 1
            ax = section_as_axiom(section, project_id=project_id)
            if ax and ax["law_id"] not in existing_laws:
                store.axioms.setdefault(project_id, []).append(ax)
                existing_laws.add(ax["law_id"])
                added_ax += 1
    return {
        "ok": True,
        "dead_ends_added": added_dead,
        "axioms_added": added_ax,
        "skipped_paths": skipped,
        "project_id": project_id,
    }


def discover_vault_files(root) -> list[Path]:
    """Find PROPRIETARY_KNOWLEDGE_VAULT.md and *REPORT*.md under root.

    Stays inside ``root`` after resolve (skips symlink escapes).
    """
    base = Path(root).expanduser().resolve()
    found: list[Path] = []
    if not base.is_dir():
        return found
    for path in base.rglob("*"):
        if not path.is_file():
            continue
        try:
            path.resolve().relative_to(base)
        except ValueError:
            continue
        name = path.name
        upper = name.upper()
        if name == "PROPRIETARY_KNOWLEDGE_VAULT.md":
            found.append(path)
        elif "REPORT" in upper and path.suffix.lower() in {".md", ".txt"}:
            found.append(path)
    return sorted(set(found))


async def ingest_vault_paths_mongo(
    db: Any,
    *,
    workspace_id: str,
    project_id: str,
    paths: list,
) -> dict[str, Any]:
    """Persist vault sections into Mongo dead_ends + project_axioms (via saas/db)."""
    from mymlfw.saas.db import project_data
    from mymlfw.saas.db.project_db import ProjectScopedDB

    proj = await project_data.get_project(db, workspace_id, project_id)
    if proj is None:
        raise KeyError("project_not_found")
    pdb = ProjectScopedDB(db, workspace_id=workspace_id, project_id=project_id)
    existing_vars = {
        str(d.get("variable") or "") for d in await pdb.list_dead_end_docs()
    }
    existing_laws = {
        str(a.get("law_id") or a.get("statement") or "")
        async for a in pdb.axioms.find({})
    }
    added_dead = 0
    added_ax = 0
    skipped = 0
    for raw in paths:
        path = Path(raw)
        if not path.is_file():
            skipped += 1
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        for section in parse_vault_sections(text):
            ded = section_as_dead_end(section)
            if ded and ded.variable not in existing_vars:
                await project_data.add_dead_end(
                    db,
                    workspace_id=workspace_id,
                    project_id=project_id,
                    body=ded,
                )
                existing_vars.add(ded.variable)
                added_dead += 1
            ax = section_as_axiom(section, project_id=project_id)
            if ax and ax["law_id"] not in existing_laws:
                ax["workspace_id"] = workspace_id
                await pdb.axioms.insert_one(ax)
                existing_laws.add(ax["law_id"])
                added_ax += 1
    return {
        "ok": True,
        "dead_ends_added": added_dead,
        "axioms_added": added_ax,
        "skipped_paths": skipped,
        "project_id": project_id,
        "persisted": "mongo",
    }
