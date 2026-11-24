"""CASMI dual-canary, immutable dirs, vault brain, lever registry."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest


def _write_panel(path: Path, rows: list[tuple[str, str]]) -> None:
    frame = pd.DataFrame(rows, columns=["id", "label"])
    if path.suffix.lower() in {".parquet", ".pq"}:
        frame.to_parquet(path, index=False)
    else:
        frame.to_csv(path, index=False)


def _write_ranked(path: Path, rows: list[tuple[str, str]]) -> None:
    path.write_text(
        "id,candidates\n" + "".join(f"{i},{c}\n" for i, c in rows),
        encoding="utf-8",
    )


def test_dual_canary_ship_and_fail(tmp_path: Path) -> None:
    from mymlfw.errors import MymlfwError
    from mymlfw.gates.canary import dual_canary

    panel = tmp_path / "Panel120.csv"
    hubs = tmp_path / "HUBS19.csv"
    _write_panel(panel, [("a", "X"), ("b", "Y")])
    _write_panel(hubs, [("a", "X"), ("c", "Z")])
    good = tmp_path / "ranked.csv"
    _write_ranked(
        good,
        [
            ("a", "X;P;Q"),
            ("b", "Y;P;Q"),
            ("c", "Z;P;Q"),
        ],
    )
    ship = dual_canary(
        panel_path=panel,
        hubs_path=hubs,
        submission_path=good,
        baseline_panel_mrr=0.5,
        baseline_hubs_mrr=0.5,
    )
    assert ship["verdict"] == "SHIP"
    assert ship["panel"]["r1_losses"] == 0
    assert ship["hubs"]["r1_losses"] == 0

    bad = tmp_path / "bad.csv"
    _write_ranked(
        bad,
        [
            ("a", "P;X;Q"),  # R1 miss
            ("b", "Y;P;Q"),
            ("c", "Z;P;Q"),
        ],
    )
    fail = dual_canary(
        panel_path=panel,
        hubs_path=hubs,
        submission_path=bad,
        baseline_panel_mrr=0.0,
        baseline_hubs_mrr=0.0,
    )
    assert fail["verdict"] == "FAIL"
    assert fail["panel"]["r1_losses"] >= 1

    partial = tmp_path / "partial.csv"
    _write_ranked(partial, [("a", "X;P")])  # missing b and c
    with pytest.raises(MymlfwError) as exc:
        dual_canary(panel_path=panel, hubs_path=hubs, submission_path=partial)
    assert exc.value.error_code == "CANARY_COVERAGE"


def test_diff_ranked_r1_r2_churn(tmp_path: Path) -> None:
    from mymlfw.gates.canary import diff_ranked_submissions

    a = tmp_path / "a.csv"
    b = tmp_path / "b.csv"
    _write_ranked(a, [("1", "A;B;C"), ("2", "X;Y;Z")])
    _write_ranked(b, [("1", "B;A;C"), ("2", "X;Z;Y")])
    d = diff_ranked_submissions(a, b)
    assert d["r1_churn"] == 1
    assert d["r2_churn"] == 2


def test_immutable_experiment_dir(tmp_path: Path) -> None:
    from mymlfw.campaign.immutable_dirs import (
        allocate_version_dir,
        assert_immutable_experiment_dir,
        next_version_name,
    )
    from mymlfw.errors import MymlfwError

    assert next_version_name("casmi26_v12_fuse") == "casmi26_v13_fuse"
    pushed = tmp_path / "casmi26_v12_run"
    pushed.mkdir()
    (pushed / "kernel.ipynb").write_text("x")
    with pytest.raises(MymlfwError) as exc:
        assert_immutable_experiment_dir(pushed)
    assert exc.value.error_code == "IMMUTABLE_EXPERIMENT_DIR"
    nxt = allocate_version_dir(tmp_path, "casmi26_v12_run")
    assert nxt.name == "casmi26_v13_run"


def test_lever_registry_sync_kills(tmp_path: Path) -> None:
    from mymlfw.campaign.lever_registry import (
        load_lever_registry,
        register_lever,
        save_lever_registry,
        sync_kills_from_ledger,
    )
    from mymlfw.campaign.ledger import register_probe, set_verdict
    from mymlfw.errors import MymlfwError

    ledger = tmp_path / "ledger.csv"
    register_probe(
        ledger,
        experiment_id="exp1",
        baseline_id="base",
        variable="_AP_KEEP1",
        expected_band_low=0.0,
        expected_band_high=1.0,
    )
    set_verdict(ledger, "exp1", "confirmed-large-gap", note="noise ±0.002")
    reg_path = tmp_path / "levers.json"
    data = load_lever_registry(reg_path)
    data = register_lever(data, variable="_AP_KEEP1", band_low=0.0, band_high=1.0)
    data = sync_kills_from_ledger(data, ledger)
    save_lever_registry(reg_path, data)
    assert "_AP_KEEP1" in data["killed"]
    with pytest.raises(MymlfwError):
        register_lever(data, variable="_AP_KEEP1", band_low=0.0, band_high=1.0)


def test_vault_brain_ingest(tmp_path: Path) -> None:
    from mymlfw.saas.brain_store import CampaignBrainStore
    from mymlfw.saas.vault_brain import discover_vault_files, ingest_vault_paths

    vault = tmp_path / "PROPRIETARY_KNOWLEDGE_VAULT.md"
    vault.write_text(
        "# Vault\n\n## L10 SpecFold mid-only\n\n"
        "Do not ship SpecFold mid-only — confirmed dead end.\n\n"
        "## L18 metabolic kill\n\nNever reopen metabolic pathway.\n"
        "## iso_v5\n\niso_v5 −0.006 noise fork.\n",
        encoding="utf-8",
    )
    (tmp_path / "WAVE_REPORT.md").write_text(
        "## AP_LAM0.65\n\nAP_LAM0.65 → 0.499 dead end.\n",
        encoding="utf-8",
    )
    files = discover_vault_files(tmp_path)
    assert any(p.name == "PROPRIETARY_KNOWLEDGE_VAULT.md" for p in files)
    store = CampaignBrainStore()
    org = "org_01HTESTORG000000000000000"
    prj = "prj_01HTESTPROJECT00000000000"
    assert store.ensure_org_project(org, prj, name="CASMI") is not None
    out = ingest_vault_paths(store, workspace_id=org, project_id=prj, paths=files)
    assert out["dead_ends_added"] >= 1
    assert out["axioms_added"] >= 1
    assert store.list_dead_ends(org, prj)


def test_dummy_kernel_and_badge() -> None:
    from mymlfw.saas.casmi_ops import (
        detect_dummy_kernel_run,
        inspect_kernel_source,
        public_code_badge_note,
        scrub_casmi_credits,
    )

    bad = "IS_RERUN = True\nFAST_COMMIT = True\nenable_gpu = False\n"
    d = detect_dummy_kernel_run(bad)
    assert d["dummy_risk"]
    ins = inspect_kernel_source(bad)
    assert ins["ship_ok"] is False
    # Absence of enable_gpu=True is OK; only explicit False or dummies refuse
    assert inspect_kernel_source("print('train')\n")["ship_ok"] is True
    assert inspect_kernel_source("enable_gpu = False\n")["ship_ok"] is False
    badge = public_code_badge_note(title_score=0.505, observed_score=0.501)
    assert badge["badge_ne_score"] is True
    scrub = scrub_casmi_credits([{"name": "GNPS_lib", "status": "OK"}])
    assert scrub["n_flagged"] == 1


def test_lever_matches_dead_end_token_not_substring() -> None:
    from mymlfw.mcp.casmi_tools import lever_matches_dead_end

    assert lever_matches_dead_end("_AP_KEEP1", "_AP_KEEP1")
    assert lever_matches_dead_end("_AP_KEEP1", "L10 _AP_KEEP1 mid-only")
    assert not lever_matches_dead_end("_AP", "_AP_KEEP1")
    assert not lever_matches_dead_end("KEEP", "_AP_KEEP1")


def test_append_vault_law_refuses_bad_path(tmp_path: Path) -> None:
    from mymlfw.errors import MymlfwError
    from mymlfw.saas.casmi_ops import append_vault_law

    with pytest.raises(MymlfwError) as exc:
        append_vault_law(tmp_path / "secrets.env", law_id="L1", text="x")
    assert exc.value.error_code == "VAULT_PATH"
    with pytest.raises(MymlfwError):
        append_vault_law(tmp_path / "VAULT.md", law_id="../etc", text="x")
    ok = append_vault_law(
        tmp_path / "PROPRIETARY_KNOWLEDGE_VAULT.md", law_id="L99", text="never"
    )
    assert ok["ok"] is True


def test_night_shift_score_only(tmp_path: Path) -> None:
    from mymlfw.campaign.night_shift_score import run_score_only_canary

    panel = tmp_path / "p.csv"
    hubs = tmp_path / "h.csv"
    _write_panel(panel, [("a", "X")])
    _write_panel(hubs, [("a", "X")])
    sub = tmp_path / "s.csv"
    _write_ranked(sub, [("a", "X;Y")])
    out = tmp_path / "digests"
    digest = run_score_only_canary(
        panel_path=panel,
        hubs_path=hubs,
        submission_path=sub,
        out_dir=out,
        label="R0",
    )
    assert digest["submit"] is False
    assert Path(digest["path"]).is_file()
    assert "SHIP" in digest["morning_digest"] or "FAIL" in digest["morning_digest"]


@pytest.mark.asyncio
async def test_mcp_casmi_tools_registered_and_record_dead_end() -> None:
    pytest.importorskip("mcp")
    from mymlfw.mcp.casmi_tools import tool_record_dead_end
    from mymlfw.mcp.server import build_mcp_server
    from mymlfw.saas.brain_store import BRAIN_STORE, CampaignBrainStore
    from mymlfw.saas.missions import MissionService
    from mymlfw.saas.pats import PatStore

    org = "org_01HTESTWORKSPACE0000000000"
    prj = "prj_01HCASMI00000000000000000"
    BRAIN_STORE.projects.clear()
    BRAIN_STORE.by_org.clear()
    BRAIN_STORE.dead_ends.clear()
    BRAIN_STORE.axioms.clear()
    assert BRAIN_STORE.ensure_org_project(org, prj, name="CASMI") is not None

    pats = PatStore()
    minted = pats.create(workspace_id=org, project_id=prj)
    headers = {"Authorization": f"Bearer {minted.token}"}
    created = await tool_record_dead_end(
        project_id=prj,
        variable="L10 SpecFold mid-only",
        lesson="Do not ship SpecFold mid-only",
        pats=pats,
        headers=headers,
        idempotency_key="ded-1",
    )
    assert created.get("variable") == "L10 SpecFold mid-only"

    brain = CampaignBrainStore()
    server = build_mcp_server(missions=MissionService(brain=brain), pats=pats)
    names = {t.name for t in server._tool_manager.list_tools()}
    for required in (
        "kaggle_refresh",
        "kaggle_submit_lifecycle",
        "record_dead_end",
        "append_vault_law",
        "diff_ranked_submissions",
        "dual_canary",
        "ingest_vault_brain",
        "public_code_badge",
    ):
        assert required in names, required


def test_cli_canary_dual(tmp_path: Path) -> None:
    from mymlfw.__main__ import main

    panel = tmp_path / "p.csv"
    hubs = tmp_path / "h.csv"
    _write_panel(panel, [("a", "X")])
    _write_panel(hubs, [("a", "X")])
    sub = tmp_path / "s.csv"
    _write_ranked(sub, [("a", "X")])
    code = main(
        [
            "canary",
            "dual",
            "--panel",
            str(panel),
            "--hubs",
            str(hubs),
            "--submission",
            str(sub),
            "--baseline-panel-mrr",
            "0",
            "--baseline-hubs-mrr",
            "0",
        ]
    )
    assert code == 0
