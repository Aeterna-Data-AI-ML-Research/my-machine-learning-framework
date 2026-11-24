"""Contest-enforcer spine: scorers, debiased gate, pin laws, fire, notebook SHA, multitask."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from mymlfw.campaign.fire_planner import (
    assert_can_fire,
    default_state,
    plan_snapshot,
    record_submit,
)
from mymlfw.campaign.ledger import (
    record_public_score,
    register_probe,
    set_code_sha,
    update_cv,
)
from mymlfw.campaign.multitask import assert_promote_gates, set_task_score
from mymlfw.errors import MymlfwError
from mymlfw.gates.cloud import assert_local_champion_gate
from mymlfw.gates.debiased import debiased_promote
from mymlfw.gates.pin import check_ntl_pin_laws
from mymlfw.kaggle_notebook import notebook_code_sha, verify_notebook
from mymlfw.metrics.registry import list_scorers, ocf_equal_mean, resolve_scorer
from mymlfw.playbook import modality_strategies
from mymlfw.saas.ntl_status import read_ntl_status


def test_scorer_registry_builtins() -> None:
    assert "log_loss" in list_scorers()
    assert "ocf_equal_mean" in list_scorers()
    assert ocf_equal_mean([0.1, 0.2, 0.3]) == pytest.approx(0.2)
    resolve_scorer("balanced_accuracy")


def test_debiased_promote_min_bp(tmp_path: Path) -> None:
    classes = ["a", "b"]
    y = np.array(["a", "b", "a", "b"])
    pred_good = np.array(["a", "b", "a", "b"])
    pred_bad = np.array(["b", "a", "b", "a"])
    full = tmp_path / "full.npz"
    imb = tmp_path / "imb.npz"
    np.savez(full, y_true=y, y_pred=pred_good, classes=classes)
    np.savez(imb, y_true=y, y_pred=pred_good, classes=classes)
    ok = debiased_promote(
        full_panel=full,
        imb_panel=imb,
        baseline_full=0.0,
        baseline_imb=0.0,
        min_bp=100.0,
    )
    assert ok["promote"] is True
    np.savez(imb, y_true=y, y_pred=pred_bad, classes=classes)
    bad = debiased_promote(
        full_panel=full,
        imb_panel=imb,
        baseline_full=0.5,
        baseline_imb=0.5,
        min_bp=100.0,
    )
    assert bad["promote"] is False


def test_pin_laws_ban_mount_and_post(tmp_path: Path) -> None:
    (tmp_path / "FIRE_KERNEL_VERSIONS.json").write_text("{}\n")
    report = check_ntl_pin_laws(
        contest_dir=tmp_path,
        mount_specs=["meta-llama/bad-copy"],
        post_mode="hungarian",
        post_value=1.0,
        overwrite_paths=["FIRE_KERNEL_VERSIONS.json"],
    )
    codes = {v["code"] for v in report["violations"]}
    assert "MOUNT_ALLOWLIST" in codes or "BANNED_MOUNT_PATTERN" in codes
    assert "BANNED_POST" in codes
    assert "PROTECTED_PIN_OVERWRITE" in codes
    assert report["ok"] is False


def test_noise_band_and_duplicate_code(tmp_path: Path) -> None:
    ledger = tmp_path / "experiments.csv"
    register_probe(
        ledger,
        experiment_id="exp_a",
        baseline_id="base",
        variable="v1",
        expected_band_low=0.7,
        expected_band_high=0.8,
    )
    # baseline row for delta
    register_probe(
        ledger,
        experiment_id="base",
        baseline_id="base",
        variable="baseline",
        expected_band_low=0.7,
        expected_band_high=0.8,
    )
    update_cv(ledger, "exp_a", 0.72)
    row = record_public_score(ledger, "exp_a", 0.721, noise_band=0.005)
    assert row["verdict"] == "noise"
    set_code_sha(ledger, "exp_a", "abc123")
    register_probe(
        ledger,
        experiment_id="exp_b",
        baseline_id="base",
        variable="v2",
        expected_band_low=0.7,
        expected_band_high=0.8,
    )
    row_b = set_code_sha(ledger, "exp_b", "abc123")
    assert row_b["verdict"] == "DUPLICATE_CODE"


def test_fire_planner_identical_and_resubmit(tmp_path: Path) -> None:
    state = default_state()
    state["live_pin_sha"] = "deadbeef"
    with pytest.raises(MymlfwError) as exc:
        assert_can_fire(state, kernel_id="k1", code_sha="deadbeef")
    assert exc.value.error_code == "FIRE_IDENTICAL_TO_LIVE"
    state = record_submit(state, kernel_id="k1", code_sha="other")
    with pytest.raises(MymlfwError) as exc2:
        assert_can_fire(state, kernel_id="k1")
    assert exc2.value.error_code == "FIRE_KERNEL_RESUBMIT"
    snap = plan_snapshot(state)
    assert snap["n_rem_submits"] == 4


def test_notebook_verify_identical(tmp_path: Path) -> None:
    nb = {
        "cells": [
            {"cell_type": "code", "source": ["print(1)\n"]},
            {"cell_type": "markdown", "source": ["# hi\n"]},
        ]
    }
    a = tmp_path / "a.ipynb"
    b = tmp_path / "b.ipynb"
    a.write_text(json.dumps(nb))
    b.write_text(json.dumps(nb))
    assert notebook_code_sha(a) == notebook_code_sha(b)
    report = verify_notebook(ref_path=a, cand_path=b)
    assert report["status"] == "IDENTICAL"
    nb2 = {
        "cells": [
            {"cell_type": "code", "source": ["print(2)\n"]},
        ]
    }
    b.write_text(json.dumps(nb2))
    report2 = verify_notebook(ref_path=a, cand_path=b)
    assert report2["status"] in {"FACTORIAL_DIFF", "UNRELATED"}


def test_multitask_equal_mean_and_gate() -> None:
    data = {"schema_version": 1, "tasks": {}}
    data = set_task_score(data, task_id="t1", score=0.5, n=1000)
    data = set_task_score(data, task_id="t2", score=0.7, n=1000)
    data = set_task_score(data, task_id="t3", score=0.6, n=1000)
    assert data["equal_mean"] == pytest.approx(0.6)
    ok = assert_promote_gates(data, baseline_equal_mean=0.55, min_delta=0.01, require_full_fold_n=500)
    assert ok["ok"] is True
    with pytest.raises(MymlfwError):
        assert_promote_gates(data, baseline_equal_mean=0.55, min_delta=0.2)


def test_cloud_champion_gate(tmp_path: Path) -> None:
    good = {
        "device": "mps",
        "fold0": True,
        "subsampled": False,
        "trainable_params": 400_000,
        "loss_decreasing": True,
        "delta_vs_champion": 0.6,
    }
    path = tmp_path / "probe.json"
    path.write_text(json.dumps(good))
    assert assert_local_champion_gate(path)["ok"] is True
    good["delta_vs_champion"] = 0.1
    with pytest.raises(MymlfwError) as exc:
        assert_local_champion_gate(good)
    assert exc.value.error_code == "CLOUD_BLOCKED"


def test_ntl_status_and_neural_playbook(tmp_path: Path) -> None:
    (tmp_path / "artifacts").mkdir()
    (tmp_path / "artifacts" / "CURRENT_PIN.txt").write_text("pin_live\n")
    (tmp_path / "candidates").mkdir()
    (tmp_path / "candidates" / "held1").mkdir()
    status = read_ntl_status(contest_dir=str(tmp_path))
    assert status["pin_id"] == "pin_live"
    assert "held1" in status["held_candidates"]
    ladder = modality_strategies("neural")
    assert ladder[0]["id"] == "neu_psth"
