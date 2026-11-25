"""Read, merge and write PEP 735 dependency groups."""

import re
from typing import Any

from devstandards.layout import NAME_SEPARATORS
from devstandards.toml_text import toml_key, toml_value

REQUIREMENT_NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]*")
INCLUDE_KEY = "include-group"
TABLE = "dependency-groups"
DEFAULT_INDENT = "    "

# A group's entries: requirement strings and {include-group = "..."} tables.
type Groups = dict[str, list[Any]]


def normalise(requirement: str) -> str:
    """Reduce a requirement string to its PEP 503 normalised project name."""
    match = REQUIREMENT_NAME.match(requirement.strip())
    name = match.group(0) if match else requirement
    return NAME_SEPARATORS.sub("-", name).lower()


def group_entries(groups: Groups, name: str) -> tuple[set[str], set[str]]:
    """Return a group's own (normalised package names, included groups)."""
    packages: set[str] = set()
    includes: set[str] = set()
    for entry in groups.get(name, []):
        if isinstance(entry, str):
            packages.add(normalise(entry))
        elif isinstance(entry, dict) and INCLUDE_KEY in entry:
            includes.add(str(entry[INCLUDE_KEY]))  # pyright: ignore[reportUnknownArgumentType]
    return packages, includes


def resolved_packages(groups: Groups, name: str) -> set[str]:
    """Return every package a group installs, following its includes."""
    packages, includes = group_entries(groups, name)
    for included in includes:
        packages |= resolved_packages(groups, included)
    return packages


def _requirements_by_name(groups: Groups) -> dict[str, str]:
    """Map each package the repo lists to its first requirement string."""
    found: dict[str, str] = {}
    for entries in groups.values():
        for entry in entries:
            if isinstance(entry, str):
                found.setdefault(normalise(entry), entry)
    return found


def merge(actual: Groups, template: Groups) -> Groups:
    """Return the repo's groups plus any groups, tools and includes they lack.

    Existing entries are kept. A tool the repo already lists in another group
    is added with the repo's version bound, not the template's, and a tool
    already reachable through an included group is not added again.
    """
    merged = {name: list(entries) for name, entries in actual.items()}
    known = _requirements_by_name(actual)
    for name, template_entries in template.items():
        entries = merged.setdefault(name, [])
        packages = resolved_packages(merged, name)
        _, includes = group_entries(merged, name)
        for entry in template_entries:
            if isinstance(entry, str) and normalise(entry) not in packages:
                entries.append(known.get(normalise(entry), entry))
            elif isinstance(entry, dict):
                include: dict[str, Any] = entry  # pyright: ignore[reportUnknownVariableType]
                if include.get(INCLUDE_KEY) not in includes:
                    entries.append(dict(include))
    return merged


def render(groups: Groups, indent: str = DEFAULT_INDENT) -> str:
    """Write groups as a [dependency-groups] table, one entry per line."""
    lines = [f"[{TABLE}]"]
    for name, entries in groups.items():
        lines.append(f"{toml_key(name)} = [")
        lines.extend(f"{indent}{toml_value(entry)}," for entry in entries)
        lines.append("]")
    return "\n".join(lines) + "\n"
