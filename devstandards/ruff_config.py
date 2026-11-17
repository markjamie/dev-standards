"""Find repo ruff settings that repeat the shared ruff.toml, and repo-wide ignores.

A repo extends the shared ruff.toml and keeps only local overrides, so a setting
equal to the shared one (or to ruff's own default, where the standard leaves it
unset) is dead weight that hides real overrides. Repo-wide ignores weaken the shared
rules for every file, so each must be justified in AGENTS.md.
"""

import tomllib
from dataclasses import dataclass
from typing import Any

from devstandards.layout import STANDARDS_DIR, read_text
from devstandards.toml_text import lookup, lookup_list

SHARED_RUFF_FILE = STANDARDS_DIR / "ruff.toml"

# Repo setting -> where the shared ruff.toml sets it.
SHARED_SCALARS = {
    ("tool.ruff", "target-version"): "target-version",
    ("tool.ruff", "line-length"): "line-length",
    ("tool.ruff.lint.mccabe", "max-complexity"): "lint.mccabe.max-complexity",
    ("tool.ruff.lint.pydocstyle", "convention"): "lint.pydocstyle.convention",
}
# ruff format's own defaults, which the standard leaves unset.
FORMAT_DEFAULTS = {
    ("tool.ruff.format", "quote-style"): "double",
    ("tool.ruff.format", "indent-style"): "space",
}
LINT_TABLES = ("tool.ruff.lint", "tool.ruff")  # rule lists may sit in either
SELECT_KEY = "extend-select"
IGNORE_KEYS = ("ignore", "extend-ignore")


@dataclass(frozen=True)
class Redundancy:
    """A repo setting, or some entries of one, that the shared config already makes."""

    table: str
    key: str
    entries: tuple[str, ...] = ()  # entries to drop; empty means the whole key

    @property
    def setting(self) -> str:
        """Return the setting's dotted name."""
        return f"{self.table}.{self.key}"

    def describe(self) -> str:
        """Say what repeats the shared config, as a check message."""
        if self.entries:
            listed = ", ".join(self.entries)
            return f"{self.setting} repeats {listed} from the shared rules: remove them"
        return f"{self.setting} repeats the shared ruff config: remove it"


def load_shared() -> dict[str, Any]:
    """Parse the shared ruff.toml."""
    return tomllib.loads(read_text(SHARED_RUFF_FILE))


def redundant_settings(
    pyproject: dict[str, Any], shared: dict[str, Any]
) -> list[Redundancy]:
    """Return every repo ruff setting the shared config or ruff's defaults provide."""
    expected = {
        place: lookup(shared, shared_key)
        for place, shared_key in SHARED_SCALARS.items()
    } | FORMAT_DEFAULTS
    found = [
        Redundancy(table, key)
        for (table, key), value in expected.items()
        if value is not None and lookup(pyproject, f"{table}.{key}") == value
    ]
    shared_ignores = frozenset(lookup_list(shared, "lint.ignore"))
    shared_lists = {
        SELECT_KEY: frozenset(lookup_list(shared, "lint.select")),
        **dict.fromkeys(IGNORE_KEYS, shared_ignores),
    }
    for table in LINT_TABLES:
        for key, provided in shared_lists.items():
            entries = lookup_list(pyproject, f"{table}.{key}")
            repeated = tuple(entry for entry in entries if entry in provided)
            if repeated:
                whole = len(repeated) == len(entries)
                found.append(Redundancy(table, key, () if whole else repeated))
    return found


def repo_wide_ignores(pyproject: dict[str, Any], shared: dict[str, Any]) -> list[str]:
    """Return the rule codes a repo ignores everywhere beyond the shared ignores."""
    provided = set(lookup_list(shared, "lint.ignore"))
    codes = [
        code
        for table in LINT_TABLES
        for key in IGNORE_KEYS
        for code in lookup_list(pyproject, f"{table}.{key}")
        if code not in provided
    ]
    return list(dict.fromkeys(codes))
