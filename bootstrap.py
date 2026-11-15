"""Set up a repo to use dev-standards, then report where it still differs.

Run from inside the target repo, with dev-standards added as a submodule:
    python .dev-standards/bootstrap.py            # apply templates, install, report
    python .dev-standards/bootstrap.py --check    # report only; exit 1 on any gap
"""

import argparse
import logging
import re
import shutil
import subprocess
import sys
import tomllib
from collections.abc import Callable, Iterator, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

LOGGER = logging.getLogger(__name__)

STANDARDS_DIR = Path(__file__).resolve().parent
TEMPLATES_DIR = STANDARDS_DIR / "templates"

TEMPLATE_CHECKOUT_PATH = ".dev-standards"  # where the templates assume the submodule is
PLACEHOLDER_DASHED = "your-package"
PLACEHOLDER_MODULE = "your_package"

# Replaced wholesale, and only with --force: repos customise these by hand.
COPIED_FILES = ("tox.toml", ".pre-commit-config.yaml", ".github/workflows/ci.yml")
# Created when missing and never overwritten, because they hold repo content.
SEEDED_FILES = ("CHANGELOG.md",)
GITIGNORE_FILE = ".gitignore"  # merged line by line
GITIGNORE_HEADER = "# Added by dev-standards"
AGENTS_FILE = "AGENTS.md"  # canonical agent instructions
CLAUDE_FILE = "CLAUDE.md"  # thin shim importing AGENTS.md
AGENTS_IMPORT = "@AGENTS.md"
STANDARDS_IMPORT = "@{path}/STANDARDS.md"
PYPROJECT_FILE = "pyproject.toml"
# Not named pyproject.toml, so ruff in a consuming repo never loads it as a config.
PYPROJECT_TEMPLATE = "pyproject.template.toml"
PYTHON_VERSION_FILE = ".python-version"

# Template settings that are the standard itself.
# Numbers are minimums; other values must match exactly.
ENFORCED_SETTINGS = (
    "build-system.build-backend",
    "tool.pyright.typeCheckingMode",
    "tool.coverage.report.fail_under",
    "tool.interrogate.fail-under",
)

TABLE_HEADER = re.compile(r"^\[([^\[\]]+)\]\s*$", re.MULTILINE)
REQUIREMENT_NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]*")
NAME_SEPARATORS = re.compile(r"[-_.]+")
PATCH_PIN = re.compile(r"^\d+\.\d+\.\d+")


class BootstrapError(Exception):
    """Base class for bootstrap failures the user must fix."""


@dataclass(frozen=True)
class RepoState:
    """Everything the checks need to know about the target repo."""

    root: Path
    checkout: str  # where dev-standards sits, relative to root
    package: str
    pyproject: dict[str, Any]
    template: dict[str, Any]  # the rendered pyproject template


type Check = Callable[[RepoState], Iterator[str]]


# --- Repo discovery and rendering -------------------------------------------------


def _repo_root() -> Path:
    """Find the git repo containing the current directory."""
    git = shutil.which("git")
    if git is None:
        msg = "git is required but was not found on PATH"
        raise BootstrapError(msg)
    result = subprocess.run(  # noqa: S603  # fixed argv, no user input
        [git, "rev-parse", "--show-toplevel"],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        msg = "run this from inside the git repo you want to set up"
        raise BootstrapError(msg)
    return Path(result.stdout.strip()).resolve()


def _checkout_path(root: Path) -> str:
    """Return where dev-standards sits relative to the repo root."""
    try:
        return STANDARDS_DIR.relative_to(root).as_posix()
    except ValueError:
        msg = f"{STANDARDS_DIR} is not inside {root}; add it as a submodule first"
        raise BootstrapError(msg) from None


def _read_text(path: Path) -> str:
    """Read a UTF-8 file, treating a missing file as empty."""
    return path.read_text(encoding="utf-8") if path.exists() else ""


def _package_name(root: Path, pyproject: dict[str, Any]) -> str:
    """Use the declared project name, falling back to the directory name."""
    name = _lookup(pyproject, "project.name")
    if isinstance(name, str):
        return name
    return root.name.lower().replace("_", "-")


def _render(text: str, checkout: str, package: str) -> str:
    """Fill in the template placeholders."""
    return (
        text.replace(TEMPLATE_CHECKOUT_PATH, checkout)
        .replace(PLACEHOLDER_DASHED, package)
        .replace(PLACEHOLDER_MODULE, package.replace("-", "_"))
    )


def _render_template(name: str, checkout: str, package: str) -> str:
    """Return a template file with its placeholders filled in."""
    text = (TEMPLATES_DIR / name).read_text(encoding="utf-8")
    return _render(text, checkout, package)


def _lookup(data: dict[str, Any], dotted_key: str) -> Any:
    """Return the value at a dotted TOML key, or None if absent (TOML has no null)."""
    node: Any = data
    for part in dotted_key.split("."):
        if not isinstance(node, dict) or part not in node:
            return None
        node = node[part]  # pyright: ignore[reportUnknownVariableType]
    return node  # pyright: ignore[reportUnknownVariableType]


def _split_sections(text: str) -> list[tuple[str, str]]:
    """Split a TOML file into (table name, section text) pairs."""
    matches = list(TABLE_HEADER.finditer(text))
    ends = [m.start() for m in matches[1:]] + [len(text)]
    return [
        (m.group(1), text[m.start() : end].rstrip() + "\n")
        for m, end in zip(matches, ends, strict=True)
    ]


def load_state(root: Path, checkout: str) -> RepoState:
    """Parse the repo's pyproject and the matching rendered template."""
    pyproject = tomllib.loads(_read_text(root / PYPROJECT_FILE))
    package = _package_name(root, pyproject)
    template = tomllib.loads(_render_template(PYPROJECT_TEMPLATE, checkout, package))
    return RepoState(root, checkout, package, pyproject, template)


# --- Applying templates -----------------------------------------------------------


def copy_template(
    root: Path, name: str, checkout: str, package: str, *, force: bool
) -> None:
    """Copy one template into the repo unless it exists and force is off."""
    destination = root / name
    if destination.exists() and not force:
        LOGGER.info("kept existing %s", name)
        return
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(_render_template(name, checkout, package), "utf-8")
    LOGGER.info("wrote %s", name)


def merge_pyproject(root: Path, checkout: str, package: str) -> None:
    """Append template tables the repo lacks, leaving existing tables untouched."""
    destination = root / PYPROJECT_FILE
    text = _read_text(destination)
    parsed = tomllib.loads(text)
    template = _render_template(PYPROJECT_TEMPLATE, checkout, package)

    added: list[str] = []
    for table, section in _split_sections(template):
        if _lookup(parsed, table) is None:
            text = f"{text.rstrip()}\n\n{section}"
            added.append(table)
    destination.write_text(text.lstrip(), encoding="utf-8")
    LOGGER.info("pyproject.toml: added %s", ", ".join(added) or "nothing")


def _missing_gitignore_entries(root: Path) -> list[str]:
    """List template .gitignore patterns the repo's .gitignore lacks."""

    def patterns(text: str) -> list[str]:
        lines = (line.strip() for line in text.splitlines())
        return [line for line in lines if line and not line.startswith("#")]

    # "x" and "x/" both ignore a directory named x, so treat them as the same entry.
    present = {line.rstrip("/") for line in patterns(_read_text(root / GITIGNORE_FILE))}
    template = (TEMPLATES_DIR / GITIGNORE_FILE).read_text(encoding="utf-8")
    return [line for line in patterns(template) if line.rstrip("/") not in present]


def merge_gitignore(root: Path) -> None:
    """Append the template's ignore patterns that the repo does not already have."""
    missing = _missing_gitignore_entries(root)
    if not missing:
        LOGGER.info("%s already covers the template", GITIGNORE_FILE)
        return
    destination = root / GITIGNORE_FILE
    block = "\n".join([GITIGNORE_HEADER, *missing])
    existing = _read_text(destination).rstrip()
    destination.write_text(f"{existing}\n\n{block}\n".lstrip(), encoding="utf-8")
    LOGGER.info("%s: added %s", GITIGNORE_FILE, " ".join(missing))


def ensure_import(root: Path, name: str, import_line: str, checkout: str) -> None:
    """Make sure an agent file contains an import line, preserving existing content."""
    destination = root / name
    if not destination.exists():
        destination.write_text(_render_template(name, checkout, ""), "utf-8")
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
    package = _package_name(root, tomllib.loads(_read_text(root / PYPROJECT_FILE)))
    merge_pyproject(root, checkout, package)
    for name in COPIED_FILES:
        copy_template(root, name, checkout, package, force=force)
    for name in SEEDED_FILES:
        copy_template(root, name, checkout, package, force=False)
    merge_gitignore(root)
    ensure_import(root, AGENTS_FILE, STANDARDS_IMPORT.format(path=checkout), checkout)
    ensure_import(root, CLAUDE_FILE, AGENTS_IMPORT, checkout)


def install_environment(root: Path) -> list[str]:
    """Sync the dev environment and install the git hooks; return any problems."""
    uv = shutil.which("uv")
    if uv is None:
        return ["uv not found: install it, then 'uv sync && uv run pre-commit install'"]
    for argv in ([uv, "sync"], [uv, "run", "pre-commit", "install"]):
        result = subprocess.run(argv, cwd=root, check=False)  # noqa: S603  # fixed argv
        if result.returncode != 0:
            command = " ".join(["uv", *argv[1:]])
            return [f"'{command}' failed (exit {result.returncode}); fix it and rerun"]
    return []


# --- Checks: each yields one message per gap between the repo and the standard -----


def check_pyproject_tables(state: RepoState) -> Iterator[str]:
    """Report template tables missing from pyproject.toml."""
    template_text = _render_template(PYPROJECT_TEMPLATE, state.checkout, state.package)
    for table, _ in _split_sections(template_text):
        if _lookup(state.pyproject, table) is None:
            yield f"pyproject.toml lacks [{table}]"


def check_ruff(state: RepoState) -> Iterator[str]:
    """Report ruff config that would stop the shared rules applying."""
    expected = _lookup(state.template, "tool.ruff.extend")
    if _lookup(state.pyproject, "tool.ruff.extend") != expected:
        yield f'add extend = "{expected}" to [tool.ruff] to apply the shared rules'
    for key in ("tool.ruff.select", "tool.ruff.lint.select"):
        if _lookup(state.pyproject, key) is not None:
            yield f"{key} replaces the shared rule list: use extend-select instead"


def check_enforced_settings(state: RepoState) -> Iterator[str]:
    """Report settings weaker than, or different from, the standard."""
    for key in ENFORCED_SETTINGS:
        expected = _lookup(state.template, key)
        actual = _lookup(state.pyproject, key)
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


def _normalise(requirement: str) -> str:
    """Reduce a requirement string to its PEP 503 normalised project name."""
    match = REQUIREMENT_NAME.match(requirement.strip())
    name = match.group(0) if match else requirement
    return NAME_SEPARATORS.sub("-", name).lower()


def _group_entries(groups: dict[str, Any], name: str) -> tuple[set[str], set[str]]:
    """Return a group's own (normalised package names, included group names)."""
    packages: set[str] = set()
    includes: set[str] = set()
    for entry in groups.get(name, []):
        if isinstance(entry, str):
            packages.add(_normalise(entry))
        elif isinstance(entry, dict) and "include-group" in entry:
            includes.add(str(entry["include-group"]))  # pyright: ignore[reportUnknownArgumentType]
    return packages, includes


def _resolved_packages(groups: dict[str, Any], name: str) -> set[str]:
    """Return every package a group installs, following its includes."""
    packages, includes = _group_entries(groups, name)
    for included in includes:
        packages |= _resolved_packages(groups, included)
    return packages


def check_dependency_groups(state: RepoState) -> Iterator[str]:
    """Report dependency groups lacking the tools or includes the template has."""
    expected_groups: dict[str, Any] = state.template.get("dependency-groups", {})
    actual_groups: dict[str, Any] | None = state.pyproject.get("dependency-groups")
    if actual_groups is None:
        return  # reported by check_pyproject_tables
    for group in expected_groups:
        if group not in actual_groups:
            yield f"dependency group '{group}' is missing"
            continue
        # Includes are compared directly, so a tool missing from an included group is
        # reported once, against that group, rather than again for every includer.
        expected_packages, expected_includes = _group_entries(expected_groups, group)
        missing = expected_packages - _resolved_packages(actual_groups, group)
        missing_includes = expected_includes - _group_entries(actual_groups, group)[1]
        if missing:
            yield f"dependency group '{group}' lacks {', '.join(sorted(missing))}"
        if missing_includes:
            names = ", ".join(sorted(missing_includes))
            yield f"dependency group '{group}' does not include {names}"


def check_tox_config(state: RepoState) -> Iterator[str]:
    """Report tox config that tox reads ahead of tox.toml, which hides it."""
    competing: list[str] = []
    if (state.root / "tox.ini").exists():
        competing.append("tox.ini")
    if "[tox:tox]" in _read_text(state.root / "setup.cfg"):
        competing.append("setup.cfg [tox:tox]")
    if _lookup(state.pyproject, "tool.tox") is not None:
        competing.append("pyproject.toml [tool.tox]")
    if competing:
        yield (
            f"tox reads {' and '.join(competing)} instead of tox.toml: port any "
            "repo-specific environments into tox.toml, then remove it"
        )


def check_copied_files(state: RepoState) -> Iterator[str]:
    """Report copied files that are missing or differ from their template."""
    for name in COPIED_FILES:
        path = state.root / name
        rendered = _render_template(name, state.checkout, state.package)
        if not path.exists():
            yield f"{name} is missing"
        elif path.read_text(encoding="utf-8") != rendered:
            yield f"{name} differs from the template: merge by hand, or use --force"


def check_seeded_files(state: RepoState) -> Iterator[str]:
    """Report seeded files the repo does not have."""
    for name in SEEDED_FILES:
        if not (state.root / name).exists():
            yield f"{name} is missing"


def check_gitignore(state: RepoState) -> Iterator[str]:
    """Report template ignore patterns missing from .gitignore."""
    missing = _missing_gitignore_entries(state.root)
    if missing:
        yield f"{GITIGNORE_FILE} lacks {' '.join(missing)}"


def check_agent_files(state: RepoState) -> Iterator[str]:
    """Report agent files that do not import the standards as intended."""
    standards_import = STANDARDS_IMPORT.format(path=state.checkout)
    if standards_import not in _read_text(state.root / AGENTS_FILE):
        yield f"{AGENTS_FILE} does not import {standards_import}"
    claude_path = state.root / CLAUDE_FILE
    if not claude_path.exists():
        yield f"{CLAUDE_FILE} is missing"
    elif _read_text(claude_path).split() != [AGENTS_IMPORT]:
        yield f"move rules from {CLAUDE_FILE} to {AGENTS_FILE}; keep the shim only"


def check_python_version_file(state: RepoState) -> Iterator[str]:
    """Report a .python-version that pins a patch release."""
    lines = _read_text(state.root / PYTHON_VERSION_FILE).split()
    pins = [line for line in lines if PATCH_PIN.match(line)]
    if pins:
        minors = " ".join(".".join(pin.split(".")[:2]) for pin in pins)
        yield (
            f"{PYTHON_VERSION_FILE} pins {' '.join(pins)}; use {minors} "
            "so any installed patch release satisfies uv"
        )


CHECKS: tuple[Check, ...] = (
    check_pyproject_tables,
    check_ruff,
    check_enforced_settings,
    check_dependency_groups,
    check_tox_config,
    check_copied_files,
    check_seeded_files,
    check_gitignore,
    check_agent_files,
    check_python_version_file,
)


def run_checks(state: RepoState) -> list[str]:
    """Run every check and collect the gaps found."""
    return [message for check in CHECKS for message in check(state)]


# --- Entry point ------------------------------------------------------------------


def _report(actions: Sequence[str]) -> None:
    """Log the outstanding actions, or confirm there are none."""
    if not actions:
        LOGGER.info("conforms to dev-standards: nothing to do")
        return
    LOGGER.warning("ACTION NEEDED (%d):", len(actions))
    for action in actions:
        LOGGER.warning("  - %s", action)


def _parse_args(argv: Sequence[str] | None) -> argparse.Namespace:
    """Parse command-line options."""
    parser = argparse.ArgumentParser(description=(__doc__ or "").split("\n", 1)[0])
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--force", action="store_true", help="overwrite copied files")
    mode.add_argument(
        "--check", action="store_true", help="report gaps only; change nothing"
    )
    parser.add_argument(
        "--no-install", action="store_true", help="skip uv sync and pre-commit install"
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    """Run the bootstrap; return a process exit code."""
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    args = _parse_args(argv)
    try:
        root = _repo_root()
        checkout = _checkout_path(root)
        actions: list[str] = []
        if not args.check:
            apply_templates(root, checkout, force=args.force)
            if not args.no_install:
                actions += install_environment(root)
        actions += run_checks(load_state(root, checkout))
    except BootstrapError as error:
        LOGGER.error("%s", error)  # noqa: TRY400  # user-facing message, no traceback
        return 1
    _report(actions)
    return 1 if args.check and actions else 0


if __name__ == "__main__":
    sys.exit(main())
