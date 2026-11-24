"""Phase D/E MCP tools — thin wrappers, no Mongo."""

from __future__ import annotations

from typing import Any

from mymlfw.mcp.auth import auth_error_payload
from mymlfw.mcp.tools import _auth, _err, _require_project
from mymlfw.saas.elicitation import ElicitationError, confirm_elicitation
from mymlfw.saas.lever_verifier import verify_lever_mutation
from mymlfw.saas.pats import PatStore
from mymlfw.saas.provenance import (
    CreditAsset,
    ProjectLicensePolicy,
    evaluate_license_compatibility,
    verify_project_licenses,
)
from mymlfw.saas.ids import new_credit_id


async def _ws(pats: PatStore, headers, pat, project_id: str):
    auth = await _auth(pats=pats, headers=headers, pat=pat, scopes=("mcp:worker",))
    if isinstance(auth, dict):
        return auth, None
    try:
        workspace_id = _require_project(auth, project_id)
    except PermissionError as exc:
        return auth_error_payload(exc) or _err("permission_denied", str(exc)), None
    return None, workspace_id


async def tool_propose_lever_execution(
    *,
    project_id: str,
    variable: str,
    pats: PatStore,
    headers: dict[str, str] | None = None,
    pat: str | None = None,
    mongo_client: Any | None = None,
) -> dict[str, Any]:
    err, workspace_id = await _ws(pats, headers, pat, project_id)
    if err:
        return err
    # Auto-kill: refuse variables already recorded as Project Brain dead ends
    from mymlfw.mcp.casmi_tools import lever_matches_dead_end
    from mymlfw.saas.brain_store import BRAIN_STORE

    dead_rows: list[dict[str, Any]] = []
    if mongo_client is not None and workspace_id:
        import os

        try:
            from mymlfw.saas.db import project_data
            from mymlfw.saas.db.client import get_saas_database

            db = get_saas_database(
                mongo_client, os.environ.get("MYMLFW_MONGO_DB", "mymlfw")
            )
            listed = await project_data.list_dead_ends(db, workspace_id, project_id)
            dead_rows = [
                d.model_dump(mode="json") if hasattr(d, "model_dump") else dict(d)
                for d in listed
            ]
        except Exception:  # noqa: BLE001 — fall back to memory store
            dead_rows = list(BRAIN_STORE.dead_ends.get(project_id, []))
    else:
        dead_rows = list(BRAIN_STORE.dead_ends.get(project_id, []))

    for ded in dead_rows:
        dead_var = str(ded.get("variable") or "")
        if lever_matches_dead_end(variable, dead_var):
            return {
                "allowed": False,
                "status": "killed",
                "reason": f"Dead end in Project Brain: {dead_var}",
                "project_id": project_id,
                "lesson": ded.get("lesson"),
            }
    gate = verify_lever_mutation(variable=variable)
    return {
        "allowed": gate.allowed,
        "status": gate.status,
        "reason": gate.reason,
        "project_id": project_id,
        "workspace_id": workspace_id,
    }


async def tool_register_external_asset(
    *,
    project_id: str,
    name: str,
    spdx: str,
    pats: PatStore,
    headers: dict[str, str] | None = None,
    pat: str | None = None,
    authors: list[str] | None = None,
) -> dict[str, Any]:
    err, workspace_id = await _ws(pats, headers, pat, project_id)
    if err:
        return err
    policy = ProjectLicensePolicy()
    status = evaluate_license_compatibility(
        spdx,
        outbound_spdx=policy.outbound_spdx,
        commercial_kaggle=policy.enforce_kaggle_commercial_winner_rule,
    )
    asset = CreditAsset(
        id=new_credit_id(),
        workspace_id=workspace_id or "",
        project_id=project_id,
        name=name,
        spdx=spdx if spdx else "UNVERIFIED_LICENSE",
        source="register_external_asset",
        authors=list(authors or []),
        status=status,
    )
    return asset.to_doc()


async def tool_verify_project_licenses(
    *,
    project_id: str,
    credits: list[dict[str, Any]],
    gate: str,
    pats: PatStore,
    headers: dict[str, str] | None = None,
    pat: str | None = None,
) -> dict[str, Any]:
    err, _wsid = await _ws(pats, headers, pat, project_id)
    if err:
        return err
    return verify_project_licenses(credits, gate=gate)


async def tool_get_next_autopilot_probe(
    *,
    project_id: str,
    pats: PatStore,
    headers: dict[str, str] | None = None,
    pat: str | None = None,
) -> dict[str, Any]:
    err, workspace_id = await _ws(pats, headers, pat, project_id)
    if err:
        return err
    from mymlfw.saas.autopilot import AutopilotError, get_next_autopilot_probe

    try:
        return get_next_autopilot_probe(
            project_id=project_id, workspace_id=workspace_id or ""
        )
    except AutopilotError as exc:
        return _err(exc.code, exc.message)


async def tool_complete_autopilot_rung(
    *,
    project_id: str,
    session_id: str,
    fencing_token: int,
    variable: str,
    pats: PatStore,
    headers: dict[str, str] | None = None,
    pat: str | None = None,
    idempotency_key: str | None = None,
) -> dict[str, Any]:
    if not idempotency_key:
        return _err("idempotency_key_required", "Pass idempotency_key")
    err, workspace_id = await _ws(pats, headers, pat, project_id)
    if err:
        return err
    from mymlfw.saas.autopilot import AutopilotError, complete_autopilot_rung

    try:
        return complete_autopilot_rung(
            project_id=project_id,
            workspace_id=workspace_id or "",
            session_id=session_id,
            fencing_token=fencing_token,
            variable=variable,
        )
    except AutopilotError as exc:
        return _err(exc.code, exc.message)


async def tool_confirm_elicitation(
    *,
    action: str,
    actor: str,
    pats: PatStore,
    headers: dict[str, str] | None = None,
    pat: str | None = None,
    project_id: str = "",
) -> dict[str, Any]:
    # PAT/agent tokens cannot confirm destructive ops.
    if pat or actor in {"agent", "pat", "mcp"}:
        return _err(
            "human_only",
            "Elicitation confirm requires a human web session",
            suggested_fix="Confirm in the web console as owner/member",
        )
    err, _wsid = (await _ws(pats, headers, pat, project_id)) if project_id else (None, None)
    if err:
        return err
    try:
        return confirm_elicitation(actor=actor or "human", action=action)
    except ElicitationError as exc:
        return _err(exc.code, "human session required")
