"""Static + optional smoke checks for the Docker-first CLI toolkit."""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
DOCKERFILE = ROOT / "deploy" / "Dockerfile.cli"
COMPOSE = ROOT / "deploy" / "docker-compose.yml"
RUN_CLI = ROOT / "deploy" / "run-cli.sh"


def test_dockerfile_cli_installs_git() -> None:
    text = DOCKERFILE.read_text(encoding="utf-8")
    assert "git" in text
    assert "ca-certificates" in text
    assert "useradd" in text
    assert "USER mymlfw" in text


def test_compose_cli_mount_and_user() -> None:
    text = COMPOSE.read_text(encoding="utf-8")
    assert "${MYMLFW_WORK:-..}:/work" in text
    assert 'user: "${MYMLFW_UID:-1000}:${MYMLFW_GID:-1000}"' in text
    assert 'profiles: ["cli"]' in text


def test_run_cli_script_is_executable() -> None:
    assert RUN_CLI.is_file()
    assert os.access(RUN_CLI, os.X_OK), "deploy/run-cli.sh must be executable"


def test_docs_agree_on_mymlfw_work_default() -> None:
    saas = (ROOT / "docs/how-to/run-campaign-saas.md").read_text(encoding="utf-8")
    cli = (ROOT / "docs/reference/cli.md").read_text(encoding="utf-8")
    assert "${MYMLFW_WORK:-.}" not in saas
    assert "${MYMLFW_WORK:-.}" not in cli
    assert "${MYMLFW_WORK:-..}" in saas or "MYMLFW_WORK:-.." in saas


@pytest.mark.skipif(shutil.which("docker") is None, reason="docker not installed")
def test_compose_cli_config_renders() -> None:
    env = os.environ.copy()
    env["MYMLFW_WORK"] = str(ROOT)
    env["MYMLFW_UID"] = str(os.getuid())
    env["MYMLFW_GID"] = str(os.getgid())
    proc = subprocess.run(
        [
            "docker",
            "compose",
            "-f",
            str(COMPOSE),
            "--profile",
            "cli",
            "config",
        ],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr
    assert "cli:" in proc.stdout


@pytest.mark.skipif(
    shutil.which("docker") is None or os.environ.get("MYMLFW_DOCKER_SMOKE") != "1",
    reason="set MYMLFW_DOCKER_SMOKE=1 to run image smoke",
)
def test_cli_image_version_and_git() -> None:
    env = os.environ.copy()
    env["MYMLFW_WORK"] = str(ROOT)
    env["MYMLFW_UID"] = str(os.getuid())
    env["MYMLFW_GID"] = str(os.getgid())
    build = subprocess.run(
        ["docker", "compose", "-f", str(COMPOSE), "--profile", "cli", "build", "cli"],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert build.returncode == 0, build.stderr
    version = subprocess.run(
        [str(RUN_CLI), "version"],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert version.returncode == 0, version.stderr
    assert "0.2.0" in version.stdout
    git_probe = subprocess.run(
        [
            "docker",
            "compose",
            "-f",
            str(COMPOSE),
            "--profile",
            "cli",
            "run",
            "--rm",
            "--entrypoint",
            "git",
            "cli",
            "--version",
        ],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert git_probe.returncode == 0, git_probe.stderr
    assert "git version" in git_probe.stdout.lower()
