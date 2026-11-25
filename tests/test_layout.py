from pathlib import Path

import pytest

from devstandards.errors import BootstrapError
from devstandards.layout import (
    minor_version,
    module_name,
    package_name,
    read_pyproject,
    read_text,
    render,
)


def test_render_fills_every_placeholder() -> None:
    text = (
        "extend = '.dev-standards/ruff.toml'\nname = 'your-package'\n"
        "pkg = 'your_package'"
    )
    assert render(text, "vendor/standards", "my-tool") == (
        "extend = 'vendor/standards/ruff.toml'\nname = 'my-tool'\npkg = "
        "'my_tool'"
    )


def test_package_name_prefers_project_name(tmp_path: Path) -> None:
    assert package_name(tmp_path, {"project": {"name": "a-b"}}) == "a-b"


def test_package_name_falls_back_to_directory(tmp_path: Path) -> None:
    assert package_name(tmp_path / "My_Repo", {}) == "my-repo"


@pytest.mark.parametrize(
    ("package", "module"), [("nas-sync", "nas_sync"), ("A.b", "a_b")]
)
def test_module_name(package: str, module: str) -> None:
    assert module_name(package) == module


@pytest.mark.parametrize(
    ("line", "expected"),
    [
        ("3.12.4", "3.12"),
        (" 3.15.0 ", "3.15"),
        ("3.13", "3.13"),
        ("pypy3.10", "pypy3.10"),
    ],
)
def test_minor_version(line: str, expected: str) -> None:
    assert minor_version(line) == expected


def test_read_text_treats_missing_as_empty(tmp_path: Path) -> None:
    assert read_text(tmp_path / "absent") == ""


def test_read_pyproject_reports_invalid_toml(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text("[broken", encoding="utf-8")
    with pytest.raises(BootstrapError, match="not valid TOML"):
        read_pyproject(tmp_path)
