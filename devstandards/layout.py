"""Where the templates live, which files they map to, and how they are filled in."""

import re
import tomllib
from pathlib import Path
from typing import Any

from devstandards.ci import render_workflow
from devstandards.errors import BootstrapError
from devstandards.toml_text import lookup

STANDARDS_DIR = Path(__file__).resolve().parent.parent
TEMPLATES_DIR = STANDARDS_DIR / "templates"

TEMPLATE_CHECKOUT_PATH = ".dev-standards"  # where the templates assume the submodule is
PLACEHOLDER_DASHED = "your-package"
PLACEHOLDER_MODULE = "your_package"

# Replaced only with --force: a repo may extend these by hand.
COPIED_FILES = ("tox.toml", ".pre-commit-config.yaml")
# Always replaced: CI runs tox only. A repo may declare services, packages and
# settings its tests need ([tool.dev-standards.ci]; see devstandards/ci.py).
CI_WORKFLOW = ".github/workflows/ci.yml"
MANAGED_FILES = (CI_WORKFLOW,)
# Created when missing and never overwritten, because they hold repo content.
SEEDED_FILES = ("CHANGELOG.md",)
GITIGNORE_FILE = ".gitignore"  # merged line by line
AGENTS_FILE = "AGENTS.md"  # canonical agent instructions
CLAUDE_FILE = "CLAUDE.md"  # thin shim importing AGENTS.md
AGENTS_IMPORT = "@AGENTS.md"
STANDARDS_IMPORT = "@{path}/STANDARDS.md"
PYPROJECT_FILE = "pyproject.toml"
# Not named pyproject.toml, so ruff in a consuming repo never loads it as a config.
PYPROJECT_TEMPLATE = "pyproject.template.toml"
PYTHON_VERSION_FILE = ".python-version"

PATCH_PIN = re.compile(r"^(\d+)\.(\d+)\.\d+$")
NAME_SEPARATORS = re.compile(r"[-_.]+")


def read_text(path: Path) -> str:
    """Read a UTF-8 file, treating a missing file as empty."""
    return path.read_text(encoding="utf-8") if path.exists() else ""


def read_pyproject(root: Path) -> dict[str, Any]:
    """Parse the repo's pyproject.toml, which may be absent but not malformed."""
    try:
        return tomllib.loads(read_text(root / PYPROJECT_FILE))
    except tomllib.TOMLDecodeError as error:
        msg = f"{PYPROJECT_FILE} is not valid TOML: {error}"
        raise BootstrapError(msg) from error


def package_name(root: Path, pyproject: dict[str, Any]) -> str:
    """Use the declared project name, falling back to the directory name."""
    name = lookup(pyproject, "project.name")
    if isinstance(name, str):
        return name
    return root.name.lower().replace("_", "-")


def module_name(package: str) -> str:
    """Return the import name hatchling expects for a project name."""
    return NAME_SEPARATORS.sub("_", package).lower()


def render(text: str, checkout: str, package: str) -> str:
    """Fill in the template placeholders."""
    return (
        text.replace(TEMPLATE_CHECKOUT_PATH, checkout)
        .replace(PLACEHOLDER_DASHED, package)
        .replace(PLACEHOLDER_MODULE, module_name(package))
    )


def render_template(name: str, checkout: str, package: str) -> str:
    """Return a template file with its placeholders filled in."""
    text = (TEMPLATES_DIR / name).read_text(encoding="utf-8")
    return render(text, checkout, package)


def render_for_repo(
    name: str, checkout: str, package: str, pyproject: dict[str, Any]
) -> str:
    """Return a template as this repo should have it, with any CI additions."""
    text = render_template(name, checkout, package)
    if name == CI_WORKFLOW:
        return render_workflow(text, pyproject)
    return text


def minor_version(line: str) -> str:
    """Reduce a patch pin such as 3.12.4 to 3.12; leave anything else unchanged."""
    return PATCH_PIN.sub(r"\1.\2", line.strip())
