"""SiClink smallest slice: png_parity, multitask splice, PNG zip check, CSV SHA."""

from __future__ import annotations

import base64
import io
import json
import zipfile
from pathlib import Path

import numpy as np
import pytest


def test_png_parity_and_registry() -> None:
    from mymlfw.metrics.registry import list_scorers, resolve_scorer, safe_score
    from mymlfw.metrics.siclink import png_parity

    assert "png_parity" in list_scorers()
    gt = np.array([[0, 200], [200, 0]], dtype=float)
    pred = np.array([[10, 250], [240, 5]], dtype=float)
    assert png_parity(gt, pred) == pytest.approx(1.0)
    bad = np.array([[250, 0], [0, 250]], dtype=float)
    assert png_parity(gt, bad) == pytest.approx(0.0)
    scorer = resolve_scorer("png_parity")
    # matching flat layout via bundle-like object
    class _B:
        values = pred

    assert safe_score(scorer, gt, _B()) == pytest.approx(1.0)


def test_png_parity_refuses_class_scores() -> None:
    from mymlfw.errors import MymlfwError
    from mymlfw.metrics.siclink import png_parity_bundle

    class _B:
        values = np.zeros((4, 10))

    with pytest.raises(MymlfwError) as exc:
        png_parity_bundle(np.array([0, 1, 0, 1]), _B())
    assert exc.value.error_code == "SOFT_PROXY"


def test_multitask_splice_equal_mean_not_n_weighted(tmp_path: Path) -> None:
    from mymlfw.campaign.multitask import (
        assert_promote_gates,
        load_multitask,
        save_multitask,
        splice_task_group,
    )

    data = load_multitask(tmp_path / "mt.json")
    # Task1 tiny group high, Task3 many groups lower — equal-mean must not N-weight
    data = splice_task_group(data, task_id="t1", group="a", score=0.9, n=10)
    data = splice_task_group(data, task_id="t2", group="a", score=0.6, n=10)
    data = splice_task_group(data, task_id="t3", group="g1", score=0.3, n=500)
    data = splice_task_group(data, task_id="t3", group="g2", score=0.5, n=500)
    # t3 mean = 0.4; equal mean = (0.9+0.6+0.4)/3 = 0.633…
    assert data["equal_mean"] == pytest.approx((0.9 + 0.6 + 0.4) / 3)
    save_multitask(tmp_path / "mt.json", data)
    ok = assert_promote_gates(
        data, baseline_equal_mean=0.5, min_delta=0.05, require_full_fold_n=10
    )
    assert ok["ok"] is True


def test_kaggle_png_csv_zip(tmp_path: Path) -> None:
    pytest.importorskip("PIL")
    from PIL import Image

    from mymlfw.submit.png_zip import check_kaggle_png_csv_zip

    def _b64_l(ink: int = 200) -> str:
        img = Image.new("L", (64, 64), color=0)
        px = img.load()
        for i in range(32):
            for j in range(32):
                px[i, j] = ink
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        return base64.b64encode(buf.getvalue()).decode("ascii")

    n = 4
    rows = [f"id,prediction\n"] + [f"row{i},{_b64_l()}\n" for i in range(n)]
    csv_path = tmp_path / "sub.csv"
    csv_path.write_text("".join(rows), encoding="utf-8")
    zpath = tmp_path / "sub.zip"
    with zipfile.ZipFile(zpath, "w") as zf:
        zf.writestr("submission.csv", csv_path.read_text())
    report = check_kaggle_png_csv_zip(zpath, n_ids=n)
    assert report["ok"] is True
    assert report["kind"] == "kaggle_png_csv_zip"


def test_prefer_csv_payload_sha(tmp_path: Path) -> None:
    from mymlfw.kaggle_notebook import prefer_csv_payload_sha, payload_sha256

    csv_path = tmp_path / "a.csv"
    csv_path.write_text("id,prediction\n1,x\n")
    zpath = tmp_path / "a.zip"
    with zipfile.ZipFile(zpath, "w") as zf:
        zf.writestr("a.csv", csv_path.read_bytes())
    got = prefer_csv_payload_sha(zpath)
    assert got["kind"] == "zip_csv_payload"
    assert got["sha256"] == payload_sha256(csv_path)
    assert got["sha256"] != payload_sha256(zpath)


def test_preflight_uses_csv_payload_sha(tmp_path: Path) -> None:
    """probe sha and preflight must agree on single-CSV zip digests."""
    from mymlfw.campaign.ledger import register_probe, set_artifact_sha
    from mymlfw.kaggle_notebook import prefer_csv_payload_sha
    from mymlfw.submit.preflight import _sha256

    csv_bytes = b"id,prediction\n1,x\n"
    zpath = tmp_path / "sub.zip"
    with zipfile.ZipFile(zpath, "w") as zf:
        zf.writestr("submission.csv", csv_bytes)
    digest = prefer_csv_payload_sha(zpath)["sha256"]
    assert _sha256(zpath) == digest

    ledger = tmp_path / "experiments.csv"
    register_probe(
        ledger,
        experiment_id="e1",
        baseline_id="b",
        variable="v",
        expected_band_low=0.0,
        expected_band_high=1.0,
    )
    set_artifact_sha(ledger, "e1", digest)
    assert _sha256(zpath) == digest


def test_casmi_scrub_in_license_gate() -> None:
    from mymlfw.saas.provenance import verify_project_licenses

    credits = [
        {
            "_id": "crd_1",
            "name": "GNPS_library",
            "status": "OK",
            "used_in_final_ensemble": True,
        }
    ]
    out = verify_project_licenses(credits, gate="kaggle_submit")
    assert out["ok"] is False
    assert out["error_code"] == "disqualification_risk"
    assert out["casmi_scrub_flagged"]


def test_cli_multitask_and_submit_check(tmp_path: Path) -> None:
    from mymlfw.__main__ import main

    path = tmp_path / "mt.json"
    assert (
        main(
            [
                "multitask",
                "set-score",
                "--path",
                str(path),
                "--task",
                "t1",
                "--score",
                "0.5",
                "--n",
                "1000",
            ]
        )
        == 0
    )
    assert (
        main(
            [
                "multitask",
                "splice",
                "--path",
                str(path),
                "--task",
                "t2",
                "--group",
                "g0",
                "--score",
                "0.7",
                "--n",
                "1000",
            ]
        )
        == 0
    )
    data = json.loads(path.read_text())
    assert "equal_mean" in data
    assert (
        main(
            [
                "multitask",
                "promote-check",
                "--path",
                str(path),
                "--baseline",
                "0.4",
                "--min-delta",
                "0.01",
                "--require-n",
                "100",
            ]
        )
        == 0
    )


def test_ledger_kill_notes(tmp_path: Path) -> None:
    from mymlfw.campaign.ledger import register_probe, set_verdict
    from mymlfw.rag.traps import ledger_kill_notes

    ledger = tmp_path / "experiments.csv"
    register_probe(
        ledger,
        experiment_id="e1",
        baseline_id="b",
        variable="sinkhorn_grid",
        expected_band_low=0.0,
        expected_band_high=1.0,
    )
    set_verdict(ledger, "e1", "kill", note="soft_proxy_vs_exact_metric — never again")
    notes = ledger_kill_notes(ledger)
    assert any("soft_proxy_vs_exact_metric" in n for n in notes)


def test_submit_wait_dry_run(tmp_path: Path) -> None:
    from mymlfw.kaggle_submit_wait import submit_and_wait

    f = tmp_path / "s.csv"
    f.write_text("id,prediction\n1,x\n")
    ledger = tmp_path / "experiments.csv"
    from mymlfw.campaign.ledger import register_probe

    register_probe(
        ledger,
        experiment_id="e1",
        baseline_id="b",
        variable="v",
        expected_band_low=0.0,
        expected_band_high=1.0,
    )
    out = submit_and_wait(
        competition="demo",
        file_path=f,
        ledger_path=ledger,
        experiment_id="e1",
        dry_run=True,
    )
    assert out["dry_run"] is True
    assert "payload_sha" in out
