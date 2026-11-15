import tomllib
from typing import Any

import pytest

from devstandards.dependency_groups import (
    merge,
    normalise,
    render,
    resolved_packages,
)

TEMPLATE: dict[str, list[Any]] = {
    "test": ["pytest>=8"],
    "lint": ["ruff>=0.8", "pip-audit>=2.7"],
    "typecheck": ["pyright>=1.1.390"],
    "dev": [{"include-group": "test"}, {"include-group": "typecheck"}, "pre-commit>=4"],
}


@pytest.mark.parametrize(
    ("requirement", "expected"),
    [
        ("pytest>=8", "pytest"),
        ("Pip_Audit >= 2", "pip-audit"),
        ("coverage[toml]>=7", "coverage"),
        ("zope.interface", "zope-interface"),
        ("!!", "!!"),
    ],
)
def test_normalise(requirement: str, expected: str) -> None:
    assert normalise(requirement) == expected


def test_resolved_packages_follow_includes() -> None:
    groups: dict[str, list[Any]] = {
        "a": ["x"],
        "b": [{"include-group": "a"}, "y"],
        "c": [{"include-group": "b"}, {"other": 1}],
    }
    assert resolved_packages(groups, "c") == {"x", "y"}
    assert resolved_packages(groups, "missing") == set()


def test_merge_adds_missing_groups_tools_and_includes() -> None:
    actual: dict[str, list[Any]] = {
        "test": ["pytest>=8.3"],
        "lint": ["ruff>=0.9", "pyright>=1.1.408"],
        "dev": [{"include-group": "test"}],
    }
    merged = merge(actual, TEMPLATE)
    assert merged["test"] == ["pytest>=8.3"]  # existing bounds are kept
    assert merged["lint"] == ["ruff>=0.9", "pyright>=1.1.408", "pip-audit>=2.7"]
    assert merged["typecheck"] == ["pyright>=1.1.408"]  # reuses the repo's bound
    assert merged["dev"] == [
        {"include-group": "test"},
        {"include-group": "typecheck"},
        "pre-commit>=4",
    ]
    assert actual["dev"] == [{"include-group": "test"}]  # input not mutated


def test_merge_reuses_the_repos_bound_for_a_known_tool() -> None:
    actual: dict[str, list[Any]] = {"lint": ["pyright>=1.1.408"]}
    merged = merge(actual, {"typecheck": ["pyright>=1.1.390"]})
    assert merged["typecheck"] == ["pyright>=1.1.408"]


def test_merge_skips_tools_reachable_through_includes() -> None:
    actual: dict[str, list[Any]] = {
        "base": ["pre-commit"],
        "dev": [{"include-group": "base"}],
    }
    merged = merge(actual, {"dev": ["pre-commit>=4"]})
    assert merged["dev"] == [{"include-group": "base"}]


def test_merge_of_conforming_groups_changes_nothing() -> None:
    assert merge(TEMPLATE, TEMPLATE) == TEMPLATE


def test_render_round_trips() -> None:
    parsed = tomllib.loads(render(TEMPLATE))
    assert parsed["dependency-groups"] == TEMPLATE


def test_render_uses_given_indent() -> None:
    assert render({"test": ["pytest"]}, indent="  ") == (
        '[dependency-groups]\ntest = [\n  "pytest",\n]\n'
    )
