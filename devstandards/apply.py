"""Bring a repo's files in line with the templates.

Edits are limited to what the standard owns: missing tables and keys are added,
setuptools is replaced by hatchling, and managed files are overwritten. Anything that
needs judgement is left alone and reported by the checks instead.
"""

import logging
import re
import tomllib
from collections.abc import Callable
from pathlib import Path
from typing import Any

from devstandards import dependency_groups, gitignore
from devstandards.errors import BootstrapError
from devstandards.layout import (
    AGENTS_FILE,
    AGENTS_IMPORT,
    CLAUDE_FILE,
    COPIED_FILES,
    MANAGED_FILES,
    PYPROJECT_FILE,
    PYPROJECT_TEMPLATE,
    PYTHON_VERSION_FILE,
    SEEDED_FILES,
    STANDARDS_IMPORT,
    minor_version,
    package_name,
    read_pyproject,
    read_text,
    render_template,
)
from devstandards.toml_text import (
    add_lines,
    append_table,
    lookup,
    lookup_table,
    remove_tables,
    rename_key,
    replace_table,
    section_text,
    split_sections,
    table_names,
    toml_key,
    toml_value,
)

LOGGER = logging.getLogger(__name__)

SETUPTOOLS = "setuptools"
SETUPTOOLS_TABLE = "tool.setuptools"
BUILD_SYSTEM_TABLE = "build-system"
RUFF_TABLES = ("tool.ruff.lint", "tool.ruff")  # select may sit in either
PER_FILE_IGNORES = "tool.ruff.lint.per-file-ignores"
INDENT = re.compile(r"^([ \t]+)\S", re.MULTILINE)  # reuse the repo's array indent

# Each takes (repo pyproject text, rendered template text) and returns the new text.
type Transform = Callable[[str, str], str]


# --- pyproject.toml ---------------------------------------------------------------


def add_missing_tables(text: str, template: str) -> str:
    """Append template tables the repo lacks, leaving existing tables untouched."""
    parsed = tomllib.loads(text)
    added: list[str] = []
    for section in split_sections(template)[1:]:
        if lookup(parsed, section.name) is None:
            text = append_table(text, section.text)
            added.append(section.name)
    LOGGER.info("pyproject.toml: added %s", ", ".join(added) or "no tables")
    return text


def use_hatchling(text: str, template: str) -> str:
    """Replace a setuptools build backend, and its configuration, with hatchling.

    Hatchling finds a src-layout package by its project name, so the setuptools
    package-discovery tables have no replacement.
    """
    backend = lookup(tomllib.loads(text), f"{BUILD_SYSTEM_TABLE}.build-backend")
    if not (isinstance(backend, str) and backend.startswith(SETUPTOOLS)):
        return text
    build_system = section_text(template, BUILD_SYSTEM_TABLE)
    if build_system is None:  # pragma: no cover - the template always has one
        msg = f"{PYPROJECT_TEMPLATE} has no [{BUILD_SYSTEM_TABLE}] table"
        raise BootstrapError(msg)
    text = replace_table(text, BUILD_SYSTEM_TABLE, build_system)
    stale = [
        name
        for name in table_names(text)
        if name == SETUPTOOLS_TABLE or name.startswith(f"{SETUPTOOLS_TABLE}.")
    ]
    LOGGER.info("pyproject.toml: replaced %s with hatchling", backend)
    return remove_tables(text, stale)


def merge_dependency_groups(text: str, template: str) -> str:
    """Add the groups, tools and includes the tox environments need."""
    if dependency_groups.TABLE not in table_names(text):
        return text  # absent, or written as dotted keys the table editor cannot reach
    actual = lookup_table(tomllib.loads(text), dependency_groups.TABLE)
    expected = lookup_table(tomllib.loads(template), dependency_groups.TABLE)
    merged = dependency_groups.merge(actual, expected)
    if merged == actual:
        return text
    LOGGER.info("pyproject.toml: added missing tools to [dependency-groups]")
    existing = section_text(text, dependency_groups.TABLE) or ""
    indent = INDENT.search(existing)
    rendered = dependency_groups.render(
        merged, indent.group(1) if indent else dependency_groups.DEFAULT_INDENT
    )
    return replace_table(text, dependency_groups.TABLE, rendered)


def configure_ruff(text: str, template: str) -> str:
    """Point ruff at the shared rules, and make local rules add to them."""
    parsed = tomllib.loads(text)
    expected = tomllib.loads(template)
    if lookup(parsed, "tool.ruff.extend") is None:
        line = f"extend = {toml_value(lookup(expected, 'tool.ruff.extend'))}"
        text = add_lines(text, "tool.ruff", [line], first=True)
        LOGGER.info("pyproject.toml: ruff now extends the shared rules")
    for table in RUFF_TABLES:
        has_select = lookup(parsed, f"{table}.select") is not None
        if has_select and lookup(parsed, f"{table}.extend-select") is None:
            text = rename_key(text, table, "select", "extend-select")
            LOGGER.info("pyproject.toml: [%s] select is now extend-select", table)
    return _add_per_file_ignores(text, expected)


def _add_per_file_ignores(text: str, expected: dict[str, Any]) -> str:
    """Add the template's per-file-ignores for paths the repo does not configure."""
    wanted = lookup_table(expected, PER_FILE_IGNORES)
    present = lookup_table(tomllib.loads(text), PER_FILE_IGNORES)
    lines = [
        f"{toml_key(path)} = {toml_value(codes)}"
        for path, codes in wanted.items()
        if path not in present
    ]
    if not lines:
        return text
    LOGGER.info("pyproject.toml: added per-file-ignores for %d paths", len(lines))
    return add_lines(text, PER_FILE_IGNORES, lines)


PYPROJECT_TRANSFORMS: tuple[Transform, ...] = (
    add_missing_tables,
    use_hatchling,
    merge_dependency_groups,
    configure_ruff,
)


def update_pyproject(root: Path, checkout: str, package: str) -> None:
    """Apply every pyproject transform, writing only a valid result."""
    path = root / PYPROJECT_FILE
    original = read_text(path)
    template = render_template(PYPROJECT_TEMPLATE, checkout, package)
    text = original
    try:
        for transform in PYPROJECT_TRANSFORMS:
            text = transform(text, template)
        tomllib.loads(text)
    except tomllib.TOMLDecodeError as error:
        msg = (
            f"editing {PYPROJECT_FILE} produced invalid TOML ({error}); left unchanged"
        )
        raise BootstrapError(msg) from error
    if text != original:
        path.write_text(text, encoding="utf-8")


# --- Other files ------------------------------------------------------------------


def copy_template(
    root: Path, name: str, checkout: str, package: str, *, overwrite: bool
) -> None:
    """Write one template into the repo, replacing an existing copy only if asked."""
    destination = root / name
    rendered = render_template(name, checkout, package)
    if destination.exists() and (not overwrite or read_text(destination) == rendered):
        LOGGER.info("kept existing %s", name)
        return
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(rendered, encoding="utf-8")
    LOGGER.info("wrote %s", name)


def pin_minor_versions(root: Path) -> None:
    """Reduce .python-version patch pins to minor versions so any patch fits."""
    path = root / PYTHON_VERSION_FILE
    original = read_text(path)
    lines = dict.fromkeys(minor_version(line) for line in original.splitlines())
    text = "".join(f"{line}\n" for line in lines)
    if original and text != original:
        path.write_text(text, encoding="utf-8")
        LOGGER.info("%s: pinned minor versions only", PYTHON_VERSION_FILE)


def ensure_import(root: Path, name: str, import_line: str, checkout: str) -> None:
    """Make sure an agent file contains an import line, preserving existing content."""
    destination = root / name
    if not destination.exists():
        destination.write_text(render_template(name, checkout, ""), "utf-8")
        LOGGER.info("wrote %s", name)
        return
    existing = destination.read_text(encoding="utf-8")
    if import_line in existing:
        LOGGER.info("%s already contains %s", name, import_line)
        return
    destination.write_text(f"{import_line}\n\n{existing}", encoding="utf-8")
    LOGGER.warning(
        "prepended %s to existing %s: remove any rules there that repeat or "
        "contradict it, keeping only repo-specific ones",
        import_line,
        name,
    )


def apply_templates(root: Path, checkout: str, *, force: bool) -> None:
    """Write or merge every template into the repo."""
    package = package_name(root, read_pyproject(root))
    update_pyproject(root, checkout, package)
    pin_minor_versions(root)
    for name in COPIED_FILES:
        copy_template(root, name, checkout, package, overwrite=force)
    for name in MANAGED_FILES:
        copy_template(root, name, checkout, package, overwrite=True)
    for name in SEEDED_FILES:
        copy_template(root, name, checkout, package, overwrite=False)
    gitignore.merge(root)
    ensure_import(root, AGENTS_FILE, STANDARDS_IMPORT.format(path=checkout), checkout)
    ensure_import(root, CLAUDE_FILE, AGENTS_IMPORT, checkout)
