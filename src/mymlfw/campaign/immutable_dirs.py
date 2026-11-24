"""Refuse overwrite of pushed experiment dirs; require vN+1 clones."""

from __future__ import annotations

import re
from pathlib import Path

from mymlfw.errors import MymlfwError

_VN = re.compile(r"^(?P<prefix>.*?)(?P<ver>v)(?P<num>\d+)(?P<suffix>.*)$", re.I)
_PUSHED = re.compile(r"casmi26_v\d+", re.I)


def next_version_name(name: str) -> str:
    match = _VN.match(name)
    if not match:
        return f"{name}_v2"
    num = int(match.group("num")) + 1
    return f"{match.group('prefix')}{match.group('ver')}{num}{match.group('suffix')}"


def assert_immutable_experiment_dir(
    path,
    *,
    allow_empty: bool = True,
    pushed_pattern: re.Pattern[str] | None = None,
) -> Path:
    """Refuse creating/writing into a non-empty pushed kernel/experiment dir."""
    target = Path(path)
    pat = pushed_pattern or _PUSHED
    if target.exists() and any(target.iterdir() if target.is_dir() else [target]):
        if pat.search(target.name) or (target.is_dir() and any(pat.search(p.name) for p in target.iterdir())):
            raise MymlfwError(
                "IMMUTABLE_EXPERIMENT_DIR",
                "Refuse overwrite of pushed experiment dir — clone as vN+1.",
                path=str(target),
                suggested_name=next_version_name(target.name),
            )
        if not allow_empty:
            raise MymlfwError(
                "EXPERIMENT_DIR_EXISTS",
                "Directory exists; use a new vN+1 name.",
                path=str(target),
                suggested_name=next_version_name(target.name),
            )
    return target


def allocate_version_dir(parent, stem: str) -> Path:
    """Return parent/stem or parent/stem_vN that does not exist yet."""
    root = Path(parent)
    candidate = root / stem
    while candidate.exists():
        stem = next_version_name(stem)
        candidate = root / stem
    return candidate
