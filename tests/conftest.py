"""Shared fixtures that build repos for the tests."""

import shutil
from collections.abc import Callable
from pathlib import Path

import pytest

from devstandards.layout import STANDARDS_DIR
from repos import CHECKOUT, MINIMAL_PYPROJECT, SETUPTOOLS_PYPROJECT, write_repo


@pytest.fixture
def new_repo(tmp_path: Path) -> Path:
    """A new repo with nothing from dev-standards applied."""
    return write_repo(tmp_path / "repo", MINIMAL_PYPROJECT)


@pytest.fixture
def setuptools_repo(tmp_path: Path) -> Path:
    """An established setuptools repo with its own tox.ini and pinned Pythons."""
    root = write_repo(tmp_path / "repo", SETUPTOOLS_PYPROJECT)
    (root / "tox.ini").write_text("[tox]\nenv_list = py312\n", encoding="utf-8")
    (root / ".python-version").write_text("3.13.1\n3.12.4\n", encoding="utf-8")
    (root / "AGENTS.md").write_text("# Rules\n\nUse pip.\n", encoding="utf-8")
    workflows = root / ".github" / "workflows"
    workflows.mkdir(parents=True)
    (workflows / "ci.yml").write_text("jobs: {lint: {}, test: {}}\n", encoding="utf-8")
    return root


@pytest.fixture
def install_standards() -> Callable[[Path], Path]:
    """Return a function that copies this checkout into a repo as its submodule."""

    def install(root: Path) -> Path:
        destination = root / CHECKOUT
        for name in ("bootstrap.py", "ruff.toml", "STANDARDS.md"):
            destination.mkdir(parents=True, exist_ok=True)
            shutil.copy2(STANDARDS_DIR / name, destination / name)
        for name in ("devstandards", "templates"):
            shutil.copytree(
                STANDARDS_DIR / name,
                destination / name,
                ignore=shutil.ignore_patterns("__pycache__"),
            )
        return destination

    return install
