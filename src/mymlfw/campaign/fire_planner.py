"""Kaggle fire / quota planner (daily submits, GPU sessions, L1→L3)."""

from __future__ import annotations

import json
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

from mymlfw.errors import MymlfwError

DEFAULT_DAILY_SUBMITS = 5
DEFAULT_CASMI_GPU_SESSIONS = 2
STAGES = ("L1_verbatim", "L2_margin079", "L3_gated_hold")


def _utc_today() -> str:
    return datetime.now(timezone.utc).date().isoformat()


def default_state() -> dict[str, Any]:
    return {
        "schema_version": 1,
        "day": _utc_today(),
        "submits_today": 0,
        "gpu_sessions_today": 0,
        "last_kernel_id": None,
        "live_pin_sha": None,
        "stage": "L1_verbatim",
        "armed_utc_daemon": False,
        "history": [],
    }


def load_fire_state(path) -> dict[str, Any]:
    p = Path(path)
    if not p.exists():
        return default_state()
    data = json.loads(p.read_text())
    if not isinstance(data, dict):
        raise MymlfwError("FIRE_STATE", "Fire planner state must be a JSON object.")
    state = default_state()
    state.update(data)
    if state.get("day") != _utc_today():
        state["day"] = _utc_today()
        state["submits_today"] = 0
        state["gpu_sessions_today"] = 0
    return state


def save_fire_state(path, state: dict[str, Any]) -> Path:
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(state, indent=2, sort_keys=True) + "\n")
    return out


def plan_snapshot(state: dict[str, Any]) -> dict[str, Any]:
    stage = str(state.get("stage") or "L1_verbatim")
    try:
        idx = STAGES.index(stage)
    except ValueError:
        idx = 0
        stage = STAGES[0]
    next_stage = STAGES[min(idx + 1, len(STAGES) - 1)]
    return {
        "stage": stage,
        "next_stage": next_stage,
        "plan": list(STAGES),
        "submits_today": int(state.get("submits_today") or 0),
        "gpu_sessions_today": int(state.get("gpu_sessions_today") or 0),
        "daily_submit_cap": DEFAULT_DAILY_SUBMITS,
        "casmi_gpu_cap": DEFAULT_CASMI_GPU_SESSIONS,
        "last_kernel_id": state.get("last_kernel_id"),
        "live_pin_sha": state.get("live_pin_sha"),
        "armed_utc_daemon": bool(state.get("armed_utc_daemon")),
        "n_rem_submits": max(0, DEFAULT_DAILY_SUBMITS - int(state.get("submits_today") or 0)),
        "n_rem_gpu": max(0, DEFAULT_CASMI_GPU_SESSIONS - int(state.get("gpu_sessions_today") or 0)),
    }


def assert_can_fire(
    state: dict[str, Any],
    *,
    kernel_id: str,
    code_sha: str | None = None,
    identical_to_live: bool = False,
) -> dict[str, Any]:
    if identical_to_live or (
        code_sha and state.get("live_pin_sha") and code_sha == state.get("live_pin_sha")
    ):
        raise MymlfwError(
            "FIRE_IDENTICAL_TO_LIVE",
            "Refuse fire: notebook/code SHA identical to LIVE pin.",
            kernel_id=kernel_id,
            live_pin_sha=state.get("live_pin_sha"),
        )
    if state.get("last_kernel_id") and str(kernel_id) == str(state["last_kernel_id"]):
        raise MymlfwError(
            "FIRE_KERNEL_RESUBMIT",
            "Refuse re-submit of the same kernel id.",
            kernel_id=kernel_id,
        )
    if int(state.get("submits_today") or 0) >= DEFAULT_DAILY_SUBMITS:
        raise MymlfwError(
            "FIRE_DAILY_CAP",
            f"Daily Kaggle submit cap ({DEFAULT_DAILY_SUBMITS}) reached.",
        )
    return plan_snapshot(state)


def assert_can_gpu_session(state: dict[str, Any]) -> dict[str, Any]:
    if int(state.get("gpu_sessions_today") or 0) >= DEFAULT_CASMI_GPU_SESSIONS:
        raise MymlfwError(
            "FIRE_GPU_CAP",
            f"CASMI GPU session cap ({DEFAULT_CASMI_GPU_SESSIONS}) reached today.",
        )
    return plan_snapshot(state)


def assert_daemon_safe(state: dict[str, Any], *, action: str) -> None:
    if state.get("armed_utc_daemon") and action in {"kill_daemon", "restart_daemon", "stop_daemon"}:
        raise MymlfwError(
            "FIRE_DAEMON_ARMED",
            "Autopilot must not kill/restart an armed UTC fire daemon.",
            action=action,
        )


def record_submit(state: dict[str, Any], *, kernel_id: str, code_sha: str | None = None) -> dict[str, Any]:
    state = dict(state)
    if state.get("day") != _utc_today():
        state["day"] = _utc_today()
        state["submits_today"] = 0
        state["gpu_sessions_today"] = 0
    state["submits_today"] = int(state.get("submits_today") or 0) + 1
    state["last_kernel_id"] = str(kernel_id)
    if code_sha:
        state.setdefault("history", []).append(
            {"day": state["day"], "kernel_id": kernel_id, "code_sha": code_sha}
        )
    return state


def record_gpu_session(state: dict[str, Any]) -> dict[str, Any]:
    state = dict(state)
    if state.get("day") != _utc_today():
        state["day"] = _utc_today()
        state["submits_today"] = 0
        state["gpu_sessions_today"] = 0
    state["gpu_sessions_today"] = int(state.get("gpu_sessions_today") or 0) + 1
    return state
