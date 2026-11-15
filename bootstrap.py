"""Set up a repo to use dev-standards: copy templates, merge config, install hooks.

Run from inside the target repo, with dev-standards added as a submodule:
    python .dev-standards/bootstrap.py
"""

import argparse
import logging
import re
import shutil
import subprocess
import sys
import tomllib
from collections.abc import Sequence
from pathlib import Path
from typing import Any

LOGGER = logging.getLogger(__name__)

STANDARDS_DIR = Path(__file__).resolve().parent
TEMPLATES_DIR = STANDARDS_DIR / "templates"

TEMPLATE_CHECKOUT_PATH = ".dev-standards"  # where the templates assume the submodule is
PLACEHOLDER_DASHED = "your-package"
PLACEHOLDER_MODULE = "your_package"
COPIED_FILES = (
    "tox.toml",
    ".pre-commit-config.yaml",
    ".gitignore",
    ".github/workflows/ci.yml",
)
AGENTS_FILE = "AGENTS.md"  # canonical agent instructions
CLAUDE_FILE = "CLAUDE.md"  # thin shim importing AGENTS.md
AGENTS_IMPORT = "@AGENTS.md"
PYPROJECT_FILE = "pyproject.toml"
STANDARDS_IMPORT = "@{path}/STANDARDS.md"
TABLE_HEADER = re.compile(r"^\[([^\[\]]+)\]\s*$", re.MULTILINE)


class BootstrapError(Exception):
    """Base class for bootstrap failures the user must fix."""


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


def _render(text: str, checkout_path: str, package: str) -> str:
    """Fill in the template placeholders."""
    return (
        text.replace(TEMPLATE_CHECKOUT_PATH, checkout_path)
        .replace(PLACEHOLDER_DASHED, package)
        .replace(PLACEHOLDER_MODULE, package.replace("-", "_"))
    )


def _package_name(root: Path, pyproject: dict[str, Any]) -> str:
    """Use the declared project name, falling back to the directory name."""
    name = pyproject.get("project", {}).get("name")
    if isinstance(name, str):
        return name
    return root.name.lower().replace("_", "-")


def _has_table(data: dict[str, Any], dotted_name: str) -> bool:
    """Report whether a dotted TOML table name exists in parsed data."""
    node: Any = data
    for part in dotted_name.split("."):
        if not isinstance(node, dict) or part not in node:
            return False
        node = node[part]  # pyright: ignore[reportUnknownVariableType]
    return True


def _split_sections(text: str) -> list[tuple[str, str]]:
    """Split a TOML file into (table name, section text) pairs."""
    matches = list(TABLE_HEADER.finditer(text))
    ends = [m.start() for m in matches[1:]] + [len(text)]
    return [
        (m.group(1), text[m.start() : end].rstrip() + "\n")
        for m, end in zip(matches, ends, strict=True)
    ]


def copy_template(root: Path, name: str, package: str, *, force: bool) -> bool:
    """Copy one template into the repo; return whether it was written."""
    destination = root / name
    if destination.exists() and not force:
        LOGGER.info("kept existing %s (use --force to overwrite)", name)
        return False
    text = (TEMPLATES_DIR / name).read_text(encoding="utf-8")
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(_render(text, _checkout_path(root), package), "utf-8")
    LOGGER.info("wrote %s", name)
    return True


def ensure_import(root: Path, name: str, import_line: str) -> None:
    """Make sure an agent file contains an import line, preserving existing content."""
    destination = root / name
    if not destination.exists():
        text = (TEMPLATES_DIR / name).read_text(encoding="utf-8")
        destination.write_text(_render(text, _checkout_path(root), ""), "utf-8")
        LOGGER.info("wrote %s", name)
        return
    existing = destination.read_text(encoding="utf-8")
    if import_line in existing:
        LOGGER.info("%s already contains %s", name, import_line)
        return
    destination.write_text(f"{import_line}\n\n{existing}", encoding="utf-8")
    LOGGER.info("prepended %s to %s", import_line, name)


def merge_pyproject(root: Path) -> str:
    """Append template tables the repo lacks; return the package name used."""
    destination = root / PYPROJECT_FILE
    existing = destination.read_text(encoding="utf-8") if destination.exists() else ""
    parsed = tomllib.loads(existing)
    package = _package_name(root, parsed)
    checkout = _checkout_path(root)
    template = (TEMPLATES_DIR / PYPROJECT_FILE).read_text(encoding="utf-8")

    added: list[str] = []
    skipped: list[str] = []
    for table, section in _split_sections(template):
        if _has_table(parsed, table):
            skipped.append(table)
        else:
            existing = f"{existing.rstrip()}\n\n{_render(section, checkout, package)}"
            added.append(table)
    destination.write_text(existing.lstrip(), encoding="utf-8")
    LOGGER.info("pyproject.toml: added %s", ", ".join(added) or "nothing")
    if skipped:
        LOGGER.info(
            "pyproject.toml: left existing [%s] untouched", "], [".join(skipped)
        )
    _warn_if_ruff_not_extended(tomllib.loads(existing), checkout)
    return package


def _warn_if_ruff_not_extended(pyproject: dict[str, Any], checkout_path: str) -> None:
    """Warn when ruff would not pick up the shared rules (silent otherwise)."""
    expected = f"{checkout_path}/ruff.toml"
    extend = pyproject.get("tool", {}).get("ruff", {}).get("extend")
    if extend != expected:
        LOGGER.warning(
            'ACTION NEEDED: add extend = "%s" to [tool.ruff] in pyproject.toml, '
            "or the shared lint rules are not applied",
            expected,
        )


def _warn_if_claude_has_content(root: Path) -> None:
    """Warn when CLAUDE.md holds more than the shim, since AGENTS.md is canonical."""
    lines = (root / CLAUDE_FILE).read_text(encoding="utf-8").split()
    if lines != [AGENTS_IMPORT]:
        LOGGER.warning(
            "ACTION NEEDED: move repo-specific rules from %s into %s, leaving only %s",
            CLAUDE_FILE,
            AGENTS_FILE,
            AGENTS_IMPORT,
        )


def install_environment(root: Path) -> None:
    """Sync the dev environment and install the git hooks."""
    uv = shutil.which("uv")
    if uv is None:
        LOGGER.warning("uv not found: run 'uv sync && uv run pre-commit install' later")
        return
    for argv in ([uv, "sync"], [uv, "run", "pre-commit", "install"]):
        subprocess.run(argv, cwd=root, check=True)  # noqa: S603  # fixed argv


def _parse_args(argv: Sequence[str] | None) -> argparse.Namespace:
    """Parse command-line options."""
    parser = argparse.ArgumentParser(description=(__doc__ or "").split("\n", 1)[0])
    parser.add_argument("--force", action="store_true", help="overwrite copied files")
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
        package = merge_pyproject(root)
        for name in COPIED_FILES:
            copy_template(root, name, package, force=args.force)
        ensure_import(
            root, AGENTS_FILE, STANDARDS_IMPORT.format(path=_checkout_path(root))
        )
        ensure_import(root, CLAUDE_FILE, AGENTS_IMPORT)
        _warn_if_claude_has_content(root)
        if not args.no_install:
            install_environment(root)
    except BootstrapError as error:
        LOGGER.error("%s", error)  # noqa: TRY400  # user-facing message, no traceback
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
