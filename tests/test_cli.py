import logging
import os
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path

import pytest

from devstandards.cli import (
    Options,
    discover_repo,
    install_environment,
    main,
    parse_args,
    report,
    run,
)
from devstandards.errors import BootstrapError
from devstandards.layout import STANDARDS_DIR
from repos import CHECKOUT, MINIMAL_PYPROJECT, SETUPTOOLS_PYPROJECT, write_repo

GIT = ["git", "-c", "init.defaultBranch=main"]


def git_init(root: Path) -> None:
    subprocess.run([*GIT, "init", "-q", str(root)], check=True)


def fake_uv(tmp_path: Path, exit_code: int) -> str:
    script = tmp_path / "uv"
    script.write_text(f"#!/bin/sh\nexit {exit_code}\n", encoding="utf-8")
    script.chmod(0o755)
    return str(script)


def bootstrap(root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    env = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1"}
    return subprocess.run(
        [sys.executable, f"{CHECKOUT}/bootstrap.py", *args],
        cwd=root,
        capture_output=True,
        text=True,
        check=False,
        env=env,
    )


class TestDiscoverRepo:
    def test_finds_this_checkout(self) -> None:
        assert discover_repo(STANDARDS_DIR) == (STANDARDS_DIR, ".")

    def test_rejects_directory_outside_git(self, tmp_path: Path) -> None:
        with pytest.raises(BootstrapError, match="inside the git repo"):
            discover_repo(tmp_path)

    def test_rejects_repo_without_the_submodule(self, tmp_path: Path) -> None:
        git_init(tmp_path)
        with pytest.raises(BootstrapError, match="add it as a submodule first"):
            discover_repo(tmp_path)

    def test_needs_git(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("PATH", str(tmp_path))
        with pytest.raises(BootstrapError, match="git is required"):
            discover_repo(tmp_path)


class TestInstallEnvironment:
    def test_reports_missing_uv(self, tmp_path: Path) -> None:
        assert "uv not found" in install_environment(tmp_path, None)[0]

    def test_succeeds(self, tmp_path: Path) -> None:
        assert install_environment(tmp_path, fake_uv(tmp_path, 0)) == []

    def test_reports_failure_without_raising(self, tmp_path: Path) -> None:
        problems = install_environment(tmp_path, fake_uv(tmp_path, 2))
        assert problems == ["'uv sync' failed (exit 2); fix it and rerun"]


class TestRun:
    def test_check_changes_nothing(self, new_repo: Path) -> None:
        before = sorted(new_repo.rglob("*"))
        actions = run(new_repo, CHECKOUT, Options(check=True), uv=None)
        assert "tox.toml is missing" in actions
        assert sorted(new_repo.rglob("*")) == before

    def test_apply_then_install(self, new_repo: Path, tmp_path: Path) -> None:
        assert run(new_repo, CHECKOUT, Options(), uv=fake_uv(tmp_path, 0)) == []

    def test_apply_without_install(self, new_repo: Path) -> None:
        assert run(new_repo, CHECKOUT, Options(install=False), uv=None) == []


class TestCommandLine:
    @pytest.mark.parametrize(
        ("argv", "expected"),
        [
            ([], Options()),
            (["--check"], Options(check=True)),
            (["--force", "--no-install"], Options(force=True, install=False)),
        ],
    )
    def test_parse_args(self, argv: list[str], expected: Options) -> None:
        assert parse_args(argv) == expected

    def test_check_and_force_are_exclusive(self) -> None:
        with pytest.raises(SystemExit):
            parse_args(["--check", "--force"])

    def test_report(self, caplog: pytest.LogCaptureFixture) -> None:
        caplog.set_level(logging.INFO)
        report([])
        report(["fix a"])
        assert "nothing to do" in caplog.text
        assert "ACTION NEEDED (1):" in caplog.text
        assert "  - fix a" in caplog.text

    def test_main_reports_errors(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        assert main(["--check"], cwd=tmp_path) == 1
        assert "inside the git repo" in caplog.text

    def test_main_check_fails_on_gaps(self) -> None:
        # This checkout is not itself a consuming repo, so it has gaps.
        assert main(["--check"], cwd=STANDARDS_DIR) == 1


class TestEndToEnd:
    """Run bootstrap.py as a user would, from a copy inside a fresh git repo."""

    def test_new_repo_conforms_after_bootstrap(
        self, tmp_path: Path, install_standards: Callable[[Path], Path]
    ) -> None:
        root = write_repo(tmp_path / "repo", MINIMAL_PYPROJECT)
        git_init(root)
        standards = install_standards(root)
        assert bootstrap(root, "--check").returncode == 1
        applied = bootstrap(root, "--no-install")
        assert applied.returncode == 0, applied.stderr
        checked = bootstrap(root, "--check")
        assert checked.returncode == 0, checked.stderr
        assert "nothing to do" in checked.stderr
        assert not any(standards.rglob("__pycache__"))

    def test_setuptools_repo_is_converted(
        self, tmp_path: Path, install_standards: Callable[[Path], Path]
    ) -> None:
        root = write_repo(tmp_path / "repo", SETUPTOOLS_PYPROJECT)
        git_init(root)
        install_standards(root)
        applied = bootstrap(root, "--no-install")
        assert applied.returncode == 0, applied.stderr
        assert "replaced setuptools.build_meta with hatchling" in applied.stderr
        assert "ACTION NEEDED (2):" in applied.stderr  # the two thresholds
