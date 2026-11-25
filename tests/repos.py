"""Throwaway repos shaped like the ones bootstrap.py meets."""

from pathlib import Path

CHECKOUT = ".dev-standards"
PACKAGE = "demo-pkg"
MODULE = "demo_pkg"

# What a new repo starts with: metadata, a hatchling build and nothing else.
MINIMAL_PYPROJECT = f"""\
[project]
name = "{PACKAGE}"
version = "0.1.0"
requires-python = ">=3.12,<3.16"
dependencies = []

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"
"""

# An established repo, modelled on nas_sync: setuptools, its own tool settings,
# and comment banners that must survive the edits.
SETUPTOOLS_PYPROJECT = f"""\
[build-system]
# setuptools 77 accepts PEP 639 licence fields.
requires = ["setuptools>=77"]
build-backend = "setuptools.build_meta"

# ----------------------------------------------------------------------------
# Project
# ----------------------------------------------------------------------------

[project]
name = "{PACKAGE}"
version = "0.1.0"
requires-python = ">=3.12,<3.16"
license = "BSD-3-Clause"
dependencies = ["pydantic>=2.7.0"]

[dependency-groups]
test = ["pytest>=8.3.0", "pytest-cov>=5.0.0"]
lint = ["interrogate>=1.7.0", "pyright>=1.1.408", "ruff>=0.8.0"]
dev = [
    {{ include-group = "test" }},
    {{ include-group = "lint" }},
    "tox>=4.22.0",
]

# ----------------------------------------------------------------------------
# Setuptools
# ----------------------------------------------------------------------------

[tool.setuptools]
package-dir = {{ "" = "src" }}

[tool.setuptools.packages.find]
where = ["src"]

# ----------------------------------------------------------------------------
# Interrogate
# ----------------------------------------------------------------------------

[tool.interrogate]
fail-under = 90

[tool.coverage.run]
branch = true

[tool.coverage.report]
fail_under = 90

[tool.pytest.ini_options]
testpaths = ["tests"]

[tool.ruff]
line-length = 79

[tool.ruff.lint]
select = ["E", "F", "A", "PIE"]

[tool.ruff.lint.per-file-ignores]
"**/tests/*.py" = ["D", "PT018"]

[tool.pyright]
include = ["src", "tests"]
typeCheckingMode = "strict"
"""


def write_repo(root: Path, pyproject: str) -> Path:
    """Create a src-layout repo with the given pyproject.toml."""
    package_dir = root / "src" / MODULE
    package_dir.mkdir(parents=True)
    (package_dir / "__init__.py").write_text('"""Demo."""\n', encoding="utf-8")
    (root / "pyproject.toml").write_text(pyproject, encoding="utf-8")
    return root
