"""Kaggle PNG-in-CSV zip submission checks (SiClink 14-point subset)."""

from __future__ import annotations

import base64
import io
import zipfile
from pathlib import Path
from typing import Any

import pandas as pd

from mymlfw.errors import MymlfwError

DEFAULT_N_IDS = 30_200
DEFAULT_SIZE = (64, 64)


def _decode_png(b64: str):
    try:
        from PIL import Image
    except ImportError as exc:  # pragma: no cover
        raise MymlfwError(
            "PNG_DEPS",
            "Pillow is required for kaggle_png_csv_zip checks.",
            suggested_fix="pip install pillow",
        ) from exc
    raw = base64.b64decode(b64)
    img = Image.open(io.BytesIO(raw))
    return img, raw


def check_kaggle_png_csv_zip(
    path,
    *,
    n_ids: int = DEFAULT_N_IDS,
    size: tuple[int, int] = DEFAULT_SIZE,
    id_col: str = "id",
    png_col: str = "prediction",
    min_ink_frac: float = 0.001,
    max_ink_frac: float = 0.95,
) -> dict[str, Any]:
    """Validate a submission zip (or CSV) of base64 PNG rows."""
    p = Path(path)
    if not p.is_file():
        raise MymlfwError("BAD_SUBMIT", "Submission path missing.", path=str(p))
    # AppleDouble / resource-fork junk
    if p.name.startswith("._") or "/__MACOSX/" in str(p):
        raise MymlfwError("APPLEDOUBLE", "Refuse AppleDouble / __MACOSX submission artifacts.")

    csv_bytes: bytes
    member = None
    if p.suffix.lower() == ".zip":
        with zipfile.ZipFile(p) as zf:
            names = zf.namelist()
            if any(n.startswith("__MACOSX/") or Path(n).name.startswith("._") for n in names):
                raise MymlfwError("APPLEDOUBLE", "Zip contains AppleDouble / __MACOSX members.")
            csvs = [n for n in names if n.lower().endswith(".csv")]
            if len(csvs) != 1:
                raise MymlfwError(
                    "BAD_SUBMIT",
                    "Zip must contain exactly one CSV.",
                    members=csvs,
                )
            member = csvs[0]
            csv_bytes = zf.read(member)
    else:
        csv_bytes = p.read_bytes()

    frame = pd.read_csv(io.BytesIO(csv_bytes))
    if id_col not in frame.columns or png_col not in frame.columns:
        raise MymlfwError(
            "BAD_COLUMNS",
            f"CSV needs {id_col!r} and {png_col!r} columns.",
            columns=list(frame.columns),
        )
    if len(frame) != int(n_ids):
        raise MymlfwError(
            "ID_COUNT",
            f"Expected {n_ids} rows.",
            rows=len(frame),
        )
    ids = frame[id_col].astype(str)
    if ids.duplicated().any() or frame[id_col].isna().any():
        raise MymlfwError("ID_MISMATCH", "Submission ids must be unique and non-null.")

    w, h = size
    ink_fracs = []
    for i, b64 in enumerate(frame[png_col].astype(str)):
        img, _raw = _decode_png(b64)
        if img.mode != "L":
            raise MymlfwError("PNG_MODE", "PNG must be mode L (grayscale).", row=i, mode=img.mode)
        if img.size != (w, h):
            raise MymlfwError(
                "PNG_SIZE",
                f"PNG must be {w}x{h}.",
                row=i,
                size=list(img.size),
            )
        arr = list(img.get_flattened_data()) if hasattr(img, "get_flattened_data") else list(img.getdata())
        ink = sum(1 for px in arr if px >= 128) / float(len(arr))
        if ink < min_ink_frac or ink > max_ink_frac:
            raise MymlfwError(
                "PNG_INK",
                "Ink density out of band.",
                row=i,
                ink_frac=ink,
            )
        ink_fracs.append(ink)

    return {
        "ok": True,
        "kind": "kaggle_png_csv_zip",
        "path": str(p),
        "member": member,
        "n_ids": int(n_ids),
        "size": [w, h],
        "mean_ink_frac": float(sum(ink_fracs) / len(ink_fracs)),
    }
