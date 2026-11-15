"""Command line: set up a repo to use dev-standards, then report where it differs."""

import argparse
import logging
import shutil
import subprocess
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from devstandards.apply import apply_templates
from devstandards.checks import load_state, run_checks
from devstandards.errors import BootstrapError
from devstandards.layout import STANDARDS_DIR

LOGGER = logging.getLogger(__name__)

DESCRIPTION = "Set up a repo to use dev-standards, then report where it still differs."


@dataclass(frozen=True)
class Options:
    """What a run should do."""

    check: bool = False  # report only, changing nothing
    force: bool = False  # overwrite copied files
    install: bool = True  # run uv sync and pre-commit install


def discover_repo(cwd: Path) -> tuple[Path, str]:
    """Return the git repo containing cwd, and where dev-standards sits inside it."""
    git = shutil.which("git")
    if git is None:
        msg = "git is required but was not found on PATH"
        raise BootstrapError(msg)
    result = subprocess.run(  # noqa: S603  # fixed argv, no user input
        [git, "-C", str(cwd), "rev-parse", "--show-toplevel"],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        msg = "run this from inside the git repo you want to set up"
        raise BootstrapError(msg)
    root = Path(result.stdout.strip()).resolve()
    try:
        return root, STANDARDS_DIR.relative_to(root).as_posix()
    except ValueError:
        msg = f"{STANDARDS_DIR} is not inside {root}; add it as a submodule first"
        raise BootstrapError(msg) from None


def install_environment(root: Path, uv: str | None) -> list[str]:
    """Sync the dev environment and install the git hooks; return any problems."""
    if uv is None:
        return ["uv not found: install it, then 'uv sync && uv run pre-commit install'"]
    for argv in ([uv, "sync"], [uv, "run", "pre-commit", "install"]):
        result = subprocess.run(argv, cwd=root, check=False)  # noqa: S603  # fixed argv
        if result.returncode != 0:
            command = " ".join(["uv", *argv[1:]])
            return [f"'{command}' failed (exit {result.returncode}); fix it and rerun"]
    return []


def run(root: Path, checkout: str, options: Options, uv: str | None) -> list[str]:
    """Apply the templates unless checking, then return every outstanding action."""
    actions: list[str] = []
    if not options.check:
        apply_templates(root, checkout, force=options.force)
        if options.install:
            actions += install_environment(root, uv)
    return actions + run_checks(load_state(root, checkout))


def report(actions: Sequence[str]) -> None:
    """Log the outstanding actions, or confirm there are none."""
    if not actions:
        LOGGER.info("conforms to dev-standards: nothing to do")
        return
    LOGGER.warning("ACTION NEEDED (%d):", len(actions))
    for action in actions:
        LOGGER.warning("  - %s", action)


def parse_args(argv: Sequence[str] | None) -> Options:
    """Parse command-line options."""
    parser = argparse.ArgumentParser(description=DESCRIPTION)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--force", action="store_true", help="overwrite copied files")
    mode.add_argument(
        "--check", action="store_true", help="report gaps only; change nothing"
    )
    parser.add_argument(
        "--no-install", action="store_true", help="skip uv sync and pre-commit install"
    )
    args = parser.parse_args(argv)
    return Options(check=args.check, force=args.force, install=not args.no_install)


def main(argv: Sequence[str] | None = None, cwd: Path | None = None) -> int:
    """Run the bootstrap; return a process exit code."""
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    options = parse_args(argv)
    try:
        root, checkout = discover_repo(cwd or Path.cwd())
        actions = run(root, checkout, options, shutil.which("uv"))
    except BootstrapError as error:
        LOGGER.error("%s", error)  # noqa: TRY400  # user-facing message, no traceback
        return 1
    report(actions)
    return 1 if options.check and actions else 0
