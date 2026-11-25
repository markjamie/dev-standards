"""Opt-in additions to the managed CI workflow, for tests that need services.

A repo whose tests need a database, system libraries or a browser declares them
in its pyproject.toml:

    [tool.dev-standards.ci]
    services = ["postgres:17"]          # PostgreSQL on localhost:5432
    apt = ["libpango-1.0-0"]            # Ubuntu packages
    playwright = ["chromium"]           # browsers, at the version in uv.lock
    env = { DATABASE_URL = "postgres://postgres:postgres@localhost/test" }

CI still runs tox and nothing else: these only give tox what it needs. Every
value is checked against a strict pattern, so nothing declared here can add
commands or YAML of its own. A repo that declares nothing gets the template
unchanged, byte for byte.
"""

import json
import re
from typing import Any, cast

from devstandards.errors import BootstrapError
from devstandards.toml_text import lookup

CI_TABLE = "tool.dev-standards.ci"
KNOWN_KEYS = ("services", "apt", "playwright", "env")

# Where the additions go in templates/.github/workflows/ci.yml.
JOB_ANCHOR = "    runs-on: ubuntu-latest\n"
TOX_STEP = "      - run: tox\n"

SERVICE = re.compile(r"^postgres(?::(?P<tag>[0-9][0-9A-Za-z.-]*))?$")
APT_PACKAGE = re.compile(r"^[a-z0-9][a-z0-9.+-]*$")
BROWSERS = ("chromium", "firefox", "webkit")
ENV_NAME = re.compile(r"^[A-Z_][A-Z0-9_]*$")
DEFAULT_POSTGRES = "17"

# The service's own superuser; repos point their test settings at it.
POSTGRES_SERVICE = """\
    services:
      postgres:
        image: postgres:{tag}
        env:
          POSTGRES_PASSWORD: postgres
        ports:
          - 5432:5432
        options: >-
          --health-cmd pg_isready --health-interval 5s
          --health-timeout 5s --health-retries 10
"""


def ci_config(pyproject: dict[str, Any]) -> dict[str, Any]:
    """Return the repo's CI additions, refusing keys the standard lacks."""
    raw = lookup(pyproject, CI_TABLE)
    if raw is None:
        return {}
    if not isinstance(raw, dict):
        msg = f"[{CI_TABLE}] must be a table"
        raise BootstrapError(msg)
    table = cast("dict[str, Any]", raw)
    unknown = sorted(set(table) - set(KNOWN_KEYS))
    if unknown:
        msg = (
            f"[{CI_TABLE}] has unknown keys {', '.join(unknown)}; "
            f"allowed: {', '.join(KNOWN_KEYS)}"
        )
        raise BootstrapError(msg)
    return table


def render_workflow(template: str, pyproject: dict[str, Any]) -> str:
    """Return the CI workflow with the repo's declared additions, if any."""
    config = ci_config(pyproject)
    if not config:
        return template
    for anchor in (JOB_ANCHOR, TOX_STEP):
        if template.count(anchor) != 1:
            msg = (
                f"the CI template no longer has exactly one {anchor.strip()!r}"
            )
            raise BootstrapError(msg)
    job = _services(config.get("services", [])) + _env(config.get("env", {}))
    steps = _apt(config.get("apt", [])) + _playwright(
        config.get("playwright", [])
    )
    return template.replace(JOB_ANCHOR, JOB_ANCHOR + job).replace(
        TOX_STEP, steps + TOX_STEP
    )


def _strings(value: object, key: str) -> list[str]:
    """Return a list of strings, or explain what was expected."""
    items = cast("list[object]", value) if isinstance(value, list) else None
    if items is None or not all(isinstance(item, str) for item in items):
        msg = f"[{CI_TABLE}] {key} must be a list of strings"
        raise BootstrapError(msg)
    return [str(item) for item in items]


def _invalid(key: str, value: str) -> BootstrapError:
    """The error for a value that does not match its pattern."""
    return BootstrapError(f"[{CI_TABLE}] {key}: {value!r} is not allowed")


def _services(value: object) -> str:
    """The job's service containers (PostgreSQL only, for now)."""
    blocks: list[str] = []
    for service in _strings(value, "services"):
        match = SERVICE.fullmatch(service)
        if match is None:
            raise _invalid("services", service)
        blocks.append(
            POSTGRES_SERVICE.format(tag=match["tag"] or DEFAULT_POSTGRES)
        )
    if len(blocks) > 1:
        msg = f"[{CI_TABLE}] services: list PostgreSQL once"
        raise BootstrapError(msg)
    return "".join(blocks)


def _env(value: object) -> str:
    """Job-level environment variables, as double-quoted YAML strings."""
    if not isinstance(value, dict):
        msg = f"[{CI_TABLE}] env must be a table of strings"
        raise BootstrapError(msg)
    table = cast("dict[str, object]", value)
    lines: list[str] = []
    for name, text in sorted(table.items()):
        if ENV_NAME.fullmatch(name) is None:
            raise _invalid("env", name)
        if not isinstance(text, str) or "\n" in text:
            msg = f"[{CI_TABLE}] env.{name} must be a one-line string"
            raise BootstrapError(msg)
        lines.append(f"      {name}: {json.dumps(text)}\n")
    return "    env:\n" + "".join(lines) if lines else ""


def _apt(value: object) -> str:
    """A step installing Ubuntu packages."""
    packages = _strings(value, "apt")
    for package in packages:
        if APT_PACKAGE.fullmatch(package) is None:
            raise _invalid("apt", package)
    if not packages:
        return ""
    return (
        "      - run: sudo apt-get update && sudo apt-get install --yes "
        f"--no-install-recommends {' '.join(packages)}\n"
    )


def _playwright(value: object) -> str:
    """A step installing browsers with the Playwright version in uv.lock."""
    browsers = _strings(value, "playwright")
    for browser in browsers:
        if browser not in BROWSERS:
            raise _invalid("playwright", browser)
    if not browsers:
        return ""
    return (
        "      - run: uv run --frozen --only-group test playwright install "
        f"--with-deps {' '.join(browsers)}\n"
    )
