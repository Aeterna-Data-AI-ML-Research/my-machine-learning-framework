"""CASMI / ranked-contest MCP tools — thin wrappers over saas (no Mongo queries here)."""

from __future__ import annotations

import re
from typing import Any

from mymlfw.errors import MymlfwError
from mymlfw.mcp.auth import auth_error_payload
from mymlfw.mcp.tools import _auth, _err, _require_idempotency, _require_project
from mymlfw.saas.pats import PatStore
from mymlfw.saas.schemas import DeadEndCreate, DeadEndStatus

_VAR_TOKEN = re.compile(r"[A-Za-z_][A-Za-z0-9_.\-]*")


def _mongo_db(mongo_client: Any | None):
    if mongo_client is None:
        return None
    import os

    name = os.environ.get("MYMLFW_MONGO_DB", "mymlfw")
    try:
        from mymlfw.saas.db.client import get_saas_database

        return get_saas_database(mongo_client, name)
    except Exception:  # noqa: BLE001
        return None


async def tool_kaggle_refresh(
    *,
    project_id: str,
    pats: PatStore,
    competition: str,
    headers: dict[str, str] | None = None,
    pat: str | None = None,
    live: bool = True,
    idempotency_key: str | None = None,
    discussions: list[dict[str, Any]] | None = None,
    kernels: list[dict[str, Any]] | None = None,
    mongo_client: Any | None = None,
) -> dict[str, Any]:
    key = _require_idempotency(headers, idempotency_key)
    if isinstance(key, dict):
        return key
    auth = await _auth(pats=pats, headers=headers, pat=pat, scopes=("mcp:worker",))
    if isinstance(auth, dict):
        return auth
    try:
        workspace_id = _require_project(auth, project_id)
    except PermissionError as exc:
        return auth_error_payload(exc) or _err("permission_denied", str(exc))
    from mymlfw.saas.brain_store import BRAIN_STORE
    from mymlfw.saas.casmi_ops import refresh_kaggle_intel_for_project

    try:
        panel = refresh_kaggle_intel_for_project(
            BRAIN_STORE,
            workspace_id=workspace_id,
            project_id=project_id,
            competition=competition,
            live=live,
            discussions=discussions,
            kernels=kernels,
        )
    except MymlfwError as exc:
        return _err(
            exc.error_code,
            exc.suggested_fix or exc.error_code,
            suggested_fix=exc.suggested_fix,
        )
    db = _mongo_db(mongo_client)
    if db is not None:
        from mymlfw.saas.db import project_data

        panel = await project_data.store_project_kaggle_intel(
            db, workspace_id=workspace_id, project_id=project_id, panel=panel
        )
        panel = {k: v for k, v in panel.items() if not str(k).startswith("_")}
    return {"ok": True, "project_id": project_id, "intel": panel}


async def tool_kaggle_submit_lifecycle(
    *,
    project_id: str,
    pats: PatStore,
    headers: dict[str, str] | None = None,
    pat: str | None = None,
    competition: str = "",
    kernel_source: str | None = None,
    submissions: list[dict[str, Any]] | None = None,
    kernels: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Poll submissions/LB shape + detect IS_RERUN/FAST_COMMIT/enable_gpu dummies."""
    auth = await _auth(pats=pats, headers=headers, pat=pat, scopes=("mcp:worker",))
    if isinstance(auth, dict):
        return auth
    try:
        _require_project(auth, project_id)
    except PermissionError as exc:
        return auth_error_payload(exc) or _err("permission_denied", str(exc))
    from mymlfw.saas.casmi_ops import submit_lifecycle_snapshot

    snap = submit_lifecycle_snapshot(
        submissions=submissions,
        kernels=kernels,
        kernel_source=kernel_source,
    )
    if competition and not submissions and not kernels:
        try:
            from mymlfw.saas.kaggle_client import (
                fetch_kernels,
                fetch_submissions,
                resolve_kaggle_token,
            )

            token = resolve_kaggle_token()
            snap = submit_lifecycle_snapshot(
                submissions=fetch_submissions(competition, token=token),
                kernels=fetch_kernels(competition, token=token, page_size=25, mine=True),
                kernel_source=kernel_source,
            )
        except Exception as exc:  # noqa: BLE001
            snap["live_error"] = str(exc)
    snap["project_id"] = project_id
    snap["competition"] = competition
    return snap


async def tool_record_dead_end(
    *,
    project_id: str,
    variable: str,
    lesson: str,
    pats: PatStore,
    headers: dict[str, str] | None = None,
    pat: str | None = None,
    idempotency_key: str | None = None,
    status: str = "active_block",
    mongo_client: Any | None = None,
) -> dict[str, Any]:
    key = _require_idempotency(headers, idempotency_key)
    if isinstance(key, dict):
        return key
    auth = await _auth(pats=pats, headers=headers, pat=pat, scopes=("mcp:worker",))
    if isinstance(auth, dict):
        return auth
    try:
        workspace_id = _require_project(auth, project_id)
    except PermissionError as exc:
        return auth_error_payload(exc) or _err("permission_denied", str(exc))
    try:
        st = DeadEndStatus(status)
    except ValueError:
        st = DeadEndStatus.active_block
    body = DeadEndCreate(variable=variable, lesson=lesson, status=st)
    db = _mongo_db(mongo_client)
    try:
        if db is not None:
            from mymlfw.saas.db import project_data

            created = await project_data.add_dead_end(
                db, workspace_id=workspace_id, project_id=project_id, body=body
            )
        else:
            from mymlfw.saas.brain_store import BRAIN_STORE

            created = BRAIN_STORE.add_dead_end(workspace_id, project_id, body)
    except KeyError:
        return _err(
            "project_not_found",
            "Project not found for this PAT workspace",
            suggested_fix="Call list_projects and pick a valid project_id",
        )
    return created.model_dump(mode="json") if hasattr(created, "model_dump") else dict(created)


async def tool_append_vault_law(
    *,
    vault_path: str,
    law_id: str,
    text: str,
    pats: PatStore,
    headers: dict[str, str] | None = None,
    pat: str | None = None,
    project_id: str | None = None,
    idempotency_key: str | None = None,
) -> dict[str, Any]:
    key = _require_idempotency(headers, idempotency_key)
    if isinstance(key, dict):
        return key
    auth = await _auth(pats=pats, headers=headers, pat=pat, scopes=("mcp:worker",))
    if isinstance(auth, dict):
        return auth
    if project_id:
        try:
            _require_project(auth, project_id)
        except PermissionError as exc:
            return auth_error_payload(exc) or _err("permission_denied", str(exc))
    from mymlfw.saas.casmi_ops import append_vault_law

    try:
        return append_vault_law(vault_path, law_id=law_id, text=text)
    except MymlfwError as exc:
        return _err(
            exc.error_code,
            exc.suggested_fix or exc.error_code,
            suggested_fix=exc.suggested_fix,
        )


async def tool_diff_ranked_submissions(
    *,
    path_a: str,
    path_b: str,
    pats: PatStore,
    headers: dict[str, str] | None = None,
    pat: str | None = None,
    project_id: str | None = None,
) -> dict[str, Any]:
    auth = await _auth(pats=pats, headers=headers, pat=pat, scopes=("mcp:worker",))
    if isinstance(auth, dict):
        return auth
    if project_id:
        try:
            _require_project(auth, project_id)
        except PermissionError as exc:
            return auth_error_payload(exc) or _err("permission_denied", str(exc))
    from mymlfw.saas.casmi_ops import run_diff_ranked

    try:
        return run_diff_ranked(path_a, path_b)
    except MymlfwError as exc:
        return _err(
            exc.error_code,
            exc.suggested_fix or exc.error_code,
            suggested_fix=exc.suggested_fix,
        )


async def tool_dual_canary(
    *,
    panel_path: str,
    hubs_path: str,
    submission_path: str,
    pats: PatStore,
    headers: dict[str, str] | None = None,
    pat: str | None = None,
    baseline_panel_mrr: float | None = None,
    baseline_hubs_mrr: float | None = None,
    project_id: str | None = None,
) -> dict[str, Any]:
    auth = await _auth(pats=pats, headers=headers, pat=pat, scopes=("mcp:worker",))
    if isinstance(auth, dict):
        return auth
    if project_id:
        try:
            _require_project(auth, project_id)
        except PermissionError as exc:
            return auth_error_payload(exc) or _err("permission_denied", str(exc))
    from mymlfw.saas.casmi_ops import run_dual_canary

    try:
        return run_dual_canary(
            panel_path=panel_path,
            hubs_path=hubs_path,
            submission_path=submission_path,
            baseline_panel_mrr=baseline_panel_mrr,
            baseline_hubs_mrr=baseline_hubs_mrr,
        )
    except MymlfwError as exc:
        return _err(
            exc.error_code,
            exc.suggested_fix or exc.error_code,
            suggested_fix=exc.suggested_fix,
        )


async def tool_ingest_vault_brain(
    *,
    project_id: str,
    pats: PatStore,
    contest_dir: str,
    headers: dict[str, str] | None = None,
    pat: str | None = None,
    idempotency_key: str | None = None,
    mongo_client: Any | None = None,
) -> dict[str, Any]:
    key = _require_idempotency(headers, idempotency_key)
    if isinstance(key, dict):
        return key
    auth = await _auth(pats=pats, headers=headers, pat=pat, scopes=("mcp:worker",))
    if isinstance(auth, dict):
        return auth
    try:
        workspace_id = _require_project(auth, project_id)
    except PermissionError as exc:
        return auth_error_payload(exc) or _err("permission_denied", str(exc))
    from mymlfw.saas.brain_store import BRAIN_STORE
    from mymlfw.saas.vault_brain import (
        discover_vault_files,
        ingest_vault_paths,
        ingest_vault_paths_mongo,
    )

    paths = discover_vault_files(contest_dir)
    db = _mongo_db(mongo_client)
    if db is not None:
        try:
            return await ingest_vault_paths_mongo(
                db,
                workspace_id=workspace_id,
                project_id=project_id,
                paths=paths,
            )
        except KeyError:
            return _err(
                "project_not_found",
                "Bind CASMI to an existing Studio project first.",
                suggested_fix="list_projects then create/select project_id",
            )
    if BRAIN_STORE.get_project(workspace_id, project_id) is None:
        return _err(
            "project_not_found",
            "Bind CASMI to an existing Studio project first.",
            suggested_fix="list_projects then create/select project_id",
        )
    out = ingest_vault_paths(
        BRAIN_STORE,
        workspace_id=workspace_id,
        project_id=project_id,
        paths=paths,
    )
    out["persisted"] = "memory"
    return out


async def tool_public_code_badge(
    *,
    pats: PatStore,
    title_score: float,
    observed_score: float,
    headers: dict[str, str] | None = None,
    pat: str | None = None,
) -> dict[str, Any]:
    auth = await _auth(pats=pats, headers=headers, pat=pat, scopes=("mcp:worker",))
    if isinstance(auth, dict):
        return auth
    from mymlfw.saas.casmi_ops import public_code_badge_note

    return public_code_badge_note(title_score=title_score, observed_score=observed_score)


def lever_matches_dead_end(variable: str, dead_var: str) -> bool:
    """Exact or token match — not loose substring (avoids `_AP` blocking `_AP_KEEP1` wrongly the other way)."""
    if not variable or not dead_var:
        return False
    if variable == dead_var:
        return True
    tokens = set(_VAR_TOKEN.findall(dead_var))
    return variable in tokens
