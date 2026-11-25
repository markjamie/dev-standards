"""Find every gap between a repo and the standard.

Each check yields one message per gap. Checks only read, so they run both after the
templates are applied and on their own with --check.
"""

import re
import tomllib
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from devstandards import dependency_groups, gitignore, ruff_config
from devstandards.layout import (
    AGENTS_FILE,
    AGENTS_IMPORT,
    CLAUDE_FILE,
    COPIED_FILES,
    GITIGNORE_FILE,
    MANAGED_FILES,
    PYPROJECT_TEMPLATE,
    PYTHON_VERSION_FILE,
    SEEDED_FILES,
    STANDARDS_IMPORT,
    minor_version,
    module_name,
    package_name,
    read_pyproject,
    read_text,
    render_for_repo,
    render_template,
)
from devstandards.toml_text import lookup, lookup_list, lookup_table, split_sections

# Template settings that are the standard itself.
# Numbers are minimums; other values must match exactly.
ENFORCED_SETTINGS = (
    "build-system.build-backend",
    "tool.pyright.typeCheckingMode",
    "tool.coverage.report.fail_under",
    "tool.interrogate.fail-under",
)
HATCHLING_BACKEND = "hatchling.build"
SETUPTOOLS_FILES = ("setup.py", "setup.cfg")
SETUPTOOLS_TABLES = ("tool.setuptools", "tool.setuptools_scm")
HATCH_PACKAGE_KEYS = (
    "tool.hatch.build.targets.wheel.packages",
    "tool.hatch.build.targets.wheel.only-include",
)
PER_FILE_IGNORES = "tool.ruff.lint.per-file-ignores"
PYRIGHT_TABLE = "tool.pyright"
PYRIGHT_VENV_KEYS = ("venvPath", "venv")
TOX_INI = "tox.ini"
TOX_FILE = "tox.toml"
# The parts of tox.toml a repo may extend: it adds environments and lists them.
TOX_ENV_LIST = "env_list"
TOX_ENVS = "env"


@dataclass(frozen=True)
class RepoState:
    """Everything the checks need to know about the target repo."""

    root: Path
    checkout: str  # where dev-standards sits, relative to root
    package: str
    pyproject: dict[str, Any]
    template_text: str  # the rendered pyproject template
    template: dict[str, Any]


type Check = Callable[[RepoState], Iterator[str]]


def load_state(root: Path, checkout: str) -> RepoState:
    """Parse the repo's pyproject and the matching rendered template."""
    pyproject = read_pyproject(root)
    package = package_name(root, pyproject)
    template_text = render_template(PYPROJECT_TEMPLATE, checkout, package)
    template = tomllib.loads(template_text)
    return RepoState(root, checkout, package, pyproject, template_text, template)


def check_pyproject_tables(state: RepoState) -> Iterator[str]:
    """Report template tables missing from pyproject.toml."""
    for section in split_sections(state.template_text)[1:]:
        if lookup(state.pyproject, section.name) is None:
            yield f"pyproject.toml lacks [{section.name}]"


def check_ruff(state: RepoState) -> Iterator[str]:
    """Report ruff config that would stop the shared rules applying in full."""
    expected = lookup(state.template, "tool.ruff.extend")
    if lookup(state.pyproject, "tool.ruff.extend") != expected:
        yield f'add extend = "{expected}" to [tool.ruff] to apply the shared rules'
    for key in ("tool.ruff.select", "tool.ruff.lint.select"):
        if lookup(state.pyproject, key) is not None:
            yield f"{key} replaces the shared rule list: use extend-select instead"
    wanted = lookup_table(state.template, PER_FILE_IGNORES)
    present = lookup_table(state.pyproject, PER_FILE_IGNORES)
    for path in wanted:
        if path not in present:
            yield f'[{PER_FILE_IGNORES}] lacks the template entry for "{path}"'


def check_ruff_redundancy(state: RepoState) -> Iterator[str]:
    """Report ruff settings that repeat the shared ruff.toml."""
    shared = ruff_config.load_shared()
    for found in ruff_config.redundant_settings(state.pyproject, shared):
        yield found.describe()


def check_ruff_ignores(state: RepoState) -> Iterator[str]:
    """Report repo-wide ruff ignores that AGENTS.md does not justify."""
    agents = read_text(state.root / AGENTS_FILE)
    codes = ruff_config.repo_wide_ignores(state.pyproject, ruff_config.load_shared())
    unrecorded = [
        code for code in codes if not re.search(rf"\b{re.escape(code)}\b", agents)
    ]
    if unrecorded:
        yield (
            f"ruff ignores {', '.join(unrecorded)} in every file: fix the code, use "
            f"per-file-ignores or a targeted noqa, or give the reason in {AGENTS_FILE}"
        )


def check_pyright_venv(state: RepoState) -> Iterator[str]:
    """Report pyright settings that pin it to one virtual environment."""
    for key in PYRIGHT_VENV_KEYS:
        if lookup(state.pyproject, f"{PYRIGHT_TABLE}.{key}") is not None:
            yield (
                f"{PYRIGHT_TABLE}.{key} points pyright at one environment, so "
                "tox -e type would not check its own: remove it"
            )


def check_enforced_settings(state: RepoState) -> Iterator[str]:
    """Report settings weaker than, or different from, the standard."""
    for key in ENFORCED_SETTINGS:
        expected = lookup(state.template, key)
        actual = lookup(state.pyproject, key)
        if isinstance(expected, int | float) and isinstance(actual, int | float):
            if actual < expected:
                yield (
                    f"{key} is {actual}; the standard is at least {expected} "
                    "(record the reason in AGENTS.md if deliberate)"
                )
        elif actual is None:
            yield f"{key} is not set; the standard is {expected!r}"
        elif actual != expected:
            yield f"{key} is {actual!r}; the standard is {expected!r}"


def check_build(state: RepoState) -> Iterator[str]:
    """Report setuptools leftovers, and hatchling settings it cannot infer."""
    for name in SETUPTOOLS_FILES:
        if (state.root / name).exists():
            yield f"{name} is unused under hatchling: move its contents, then delete it"
    for table in SETUPTOOLS_TABLES:
        if lookup(state.pyproject, table) is not None:
            yield f"[{table}] is unused under hatchling: replace it with [tool.hatch]"
    if lookup(state.pyproject, "build-system.build-backend") != HATCHLING_BACKEND:
        return
    dynamic = lookup_list(state.pyproject, "project.dynamic")
    if "version" in dynamic and lookup(state.pyproject, "tool.hatch.version") is None:
        yield "project.dynamic includes version: add [tool.hatch.version] to set it"
    module = module_name(state.package)
    has_package = (state.root / "src" / module / "__init__.py").exists()
    if not has_package and all(
        lookup(state.pyproject, k) is None for k in HATCH_PACKAGE_KEYS
    ):
        yield (
            f"hatchling looks for src/{module}/: move the package there, or set "
            "[tool.hatch.build.targets.wheel] packages"
        )


def check_dependency_groups(state: RepoState) -> Iterator[str]:
    """Report dependency groups lacking the tools or includes the template has."""
    expected_groups = lookup_table(state.template, dependency_groups.TABLE)
    actual_groups = lookup_table(state.pyproject, dependency_groups.TABLE)
    if dependency_groups.TABLE not in state.pyproject:
        return  # reported by check_pyproject_tables
    for group in expected_groups:
        if group not in actual_groups:
            yield f"dependency group '{group}' is missing"
            continue
        # Includes are compared directly, so a tool missing from an included group is
        # reported once, against that group, rather than again for every includer.
        packages, includes = dependency_groups.group_entries(expected_groups, group)
        missing = packages - dependency_groups.resolved_packages(actual_groups, group)
        _, actual_includes = dependency_groups.group_entries(actual_groups, group)
        if missing:
            yield f"dependency group '{group}' lacks {', '.join(sorted(missing))}"
        if includes - actual_includes:
            names = ", ".join(sorted(includes - actual_includes))
            yield f"dependency group '{group}' does not include {names}"


def check_tox_config(state: RepoState) -> Iterator[str]:
    """Report tox config that tox reads ahead of tox.toml, which hides it."""
    competing: list[str] = []
    if (state.root / TOX_INI).exists():
        competing.append(TOX_INI)
    if "[tox:tox]" in read_text(state.root / "setup.cfg"):
        competing.append("setup.cfg [tox:tox]")
    if lookup(state.pyproject, "tool.tox") is not None:
        competing.append("pyproject.toml [tool.tox]")
    if competing:
        yield (
            f"tox reads {' and '.join(competing)} instead of tox.toml: port any "
            "repo-specific environments into tox.toml, then remove it"
        )


def tox_departures(repo: dict[str, Any], template: dict[str, Any]) -> list[str]:
    """Return the template settings a repo's tox config changes or drops.

    A repo may add its own environments and append them to env_list, so only what
    the template sets is compared. Comments and layout are not.
    """
    departures = [
        key
        for key, value in template.items()
        if key not in (TOX_ENV_LIST, TOX_ENVS) and repo.get(key) != value
    ]
    repo_envs = lookup_table(repo, TOX_ENVS)
    departures += [
        f"{TOX_ENVS}.{name}"
        for name, settings in lookup_table(template, TOX_ENVS).items()
        if repo_envs.get(name) != settings
    ]
    if not set(lookup_list(template, TOX_ENV_LIST)) <= set(
        lookup_list(repo, TOX_ENV_LIST)
    ):
        departures.append(TOX_ENV_LIST)
    return departures


def _tox_gaps(text: str, template_text: str, remedy: str) -> Iterator[str]:
    """Report where tox.toml departs from the template, ignoring repo additions."""
    try:
        repo = tomllib.loads(text)
    except tomllib.TOMLDecodeError as error:
        yield f"{TOX_FILE} is not valid TOML: {error}"
        return
    departures = tox_departures(repo, tomllib.loads(template_text))
    if departures:
        yield (
            f"{TOX_FILE} differs from the template in {', '.join(departures)}: {remedy}"
        )


def check_template_files(state: RepoState) -> Iterator[str]:
    """Report copied or managed files that are missing or differ from the template."""
    remedies = dict.fromkeys(COPIED_FILES, "merge by hand, or use --force")
    remedies |= dict.fromkeys(MANAGED_FILES, "rerun bootstrap.py to replace it")
    for name, remedy in remedies.items():
        path = state.root / name
        expected = render_for_repo(name, state.checkout, state.package, state.pyproject)
        if not path.exists():
            yield f"{name} is missing"
        elif name == TOX_FILE:
            yield from _tox_gaps(read_text(path), expected, remedy)
        elif read_text(path) != expected:
            yield f"{name} differs from the template: {remedy}"


def check_seeded_files(state: RepoState) -> Iterator[str]:
    """Report seeded files the repo does not have."""
    for name in SEEDED_FILES:
        if not (state.root / name).exists():
            yield f"{name} is missing"


def check_gitignore(state: RepoState) -> Iterator[str]:
    """Report template ignore patterns missing from .gitignore."""
    missing = gitignore.missing_entries(state.root)
    if missing:
        yield f"{GITIGNORE_FILE} lacks {' '.join(missing)}"


def check_agent_files(state: RepoState) -> Iterator[str]:
    """Report agent files that do not import the standards as intended."""
    standards_import = STANDARDS_IMPORT.format(path=state.checkout)
    if standards_import not in read_text(state.root / AGENTS_FILE):
        yield f"{AGENTS_FILE} does not import {standards_import}"
    claude_path = state.root / CLAUDE_FILE
    if not claude_path.exists():
        yield f"{CLAUDE_FILE} is missing"
    elif read_text(claude_path).split() != [AGENTS_IMPORT]:
        yield f"move rules from {CLAUDE_FILE} to {AGENTS_FILE}; keep the shim only"


def check_python_version_file(state: RepoState) -> Iterator[str]:
    """Report a .python-version that pins patch releases."""
    lines = read_text(state.root / PYTHON_VERSION_FILE).split()
    pins = [line for line in lines if minor_version(line) != line]
    if pins:
        yield (
            f"{PYTHON_VERSION_FILE} pins {' '.join(pins)}; use minor versions "
            "so any installed patch release satisfies uv"
        )


CHECKS: tuple[Check, ...] = (
    check_pyproject_tables,
    check_ruff,
    check_ruff_redundancy,
    check_ruff_ignores,
    check_pyright_venv,
    check_enforced_settings,
    check_build,
    check_dependency_groups,
    check_tox_config,
    check_template_files,
    check_seeded_files,
    check_gitignore,
    check_agent_files,
    check_python_version_file,
)


def run_checks(state: RepoState) -> list[str]:
    """Run every check and collect the gaps found."""
    return [message for check in CHECKS for message in check(state)]
