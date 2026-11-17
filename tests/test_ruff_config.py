import tomllib

import pytest

from devstandards.ruff_config import (
    Redundancy,
    load_shared,
    redundant_settings,
    repo_wide_ignores,
)

SHARED = load_shared()


def settings(text: str) -> list[Redundancy]:
    return redundant_settings(tomllib.loads(text), SHARED)


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("[tool.ruff]\nline-length = 88\n", Redundancy("tool.ruff", "line-length")),
        (
            '[tool.ruff]\ntarget-version = "py312"\n',
            Redundancy("tool.ruff", "target-version"),
        ),
        (
            "[tool.ruff.lint.mccabe]\nmax-complexity = 10\n",
            Redundancy("tool.ruff.lint.mccabe", "max-complexity"),
        ),
        (
            '[tool.ruff.lint.pydocstyle]\nconvention = "google"\n',
            Redundancy("tool.ruff.lint.pydocstyle", "convention"),
        ),
        (
            '[tool.ruff.format]\nquote-style = "double"\n',
            Redundancy("tool.ruff.format", "quote-style"),
        ),
        (
            '[tool.ruff.lint]\nextend-select = ["E", "F"]\n',
            Redundancy("tool.ruff.lint", "extend-select"),
        ),
        (
            '[tool.ruff.lint]\nextend-select = ["E", "A"]\n',
            Redundancy("tool.ruff.lint", "extend-select", ("E",)),
        ),
        (
            '[tool.ruff]\nextend-ignore = ["D203", "D105"]\n',
            Redundancy("tool.ruff", "extend-ignore", ("D203",)),
        ),
    ],
)
def test_finds_settings_the_shared_config_provides(
    text: str, expected: Redundancy
) -> None:
    assert settings(text) == [expected]


@pytest.mark.parametrize(
    "text",
    [
        "[tool.ruff]\nline-length = 100\n",
        '[tool.ruff.format]\nquote-style = "single"\n',
        '[tool.ruff.lint]\nextend-select = ["A", "PIE"]\nignore = ["D105"]\n',
        "[project]\nname = 'x'\n",
    ],
)
def test_keeps_local_overrides(text: str) -> None:
    assert settings(text) == []


def test_describes_whole_settings_and_entries() -> None:
    assert Redundancy("tool.ruff", "line-length").describe() == (
        "tool.ruff.line-length repeats the shared ruff config: remove it"
    )
    assert Redundancy("tool.ruff.lint", "ignore", ("D203", "D213")).describe() == (
        "tool.ruff.lint.ignore repeats D203, D213 from the shared rules: remove them"
    )


def test_repo_wide_ignores_skip_the_shared_ones_and_repeats() -> None:
    pyproject = tomllib.loads(
        '[tool.ruff]\nextend-ignore = ["PLR0913"]\n'
        '[tool.ruff.lint]\nignore = ["D203", "D105", "PLR0913"]\n'
    )
    assert repo_wide_ignores(pyproject, SHARED) == ["D105", "PLR0913"]
