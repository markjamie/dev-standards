from pathlib import Path
from typing import Any

import pytest

from devstandards.apply import apply_templates
from devstandards.checks import load_state, run_checks
from devstandards.ci import render_workflow
from devstandards.errors import BootstrapError
from devstandards.layout import CI_WORKFLOW, render_for_repo, render_template
from repos import CHECKOUT, PACKAGE

TEMPLATE = render_template(CI_WORKFLOW, CHECKOUT, PACKAGE)

FULL = {
    "services": ["postgres:16"],
    "apt": ["libpango-1.0-0", "libpangoft2-1.0-0"],
    "playwright": ["chromium"],
    "env": {"DJANGO_SECRET_KEY": "ci-only", "POSTGRES_HOST": "localhost"},
}


def with_ci(config: dict[str, Any]) -> dict[str, Any]:
    return {"tool": {"dev-standards": {"ci": config}}}


def test_repo_without_additions_gets_the_template_unchanged() -> None:
    # Other repos must see no difference when they update the submodule.
    assert render_for_repo(CI_WORKFLOW, CHECKOUT, PACKAGE, {}) == TEMPLATE
    assert render_workflow(TEMPLATE, {"tool": {"ruff": {}}}) == TEMPLATE
    assert render_workflow(TEMPLATE, with_ci({})) == TEMPLATE


def test_other_templates_ignore_ci_additions() -> None:
    expected = render_template("tox.toml", CHECKOUT, PACKAGE)
    assert render_for_repo("tox.toml", CHECKOUT, PACKAGE, with_ci(FULL)) == expected


def test_additions_go_into_the_job_and_before_tox() -> None:
    text = render_workflow(TEMPLATE, with_ci(FULL))
    lines = text.splitlines()
    runs_on = lines.index("    runs-on: ubuntu-latest")
    assert lines[runs_on + 1] == "    services:"
    assert "        image: postgres:16" in lines
    assert '      DJANGO_SECRET_KEY: "ci-only"' in lines
    apt = next(i for i, line in enumerate(lines) if "apt-get install" in line)
    browsers = next(i for i, line in enumerate(lines) if "playwright install" in line)
    tox = lines.index("      - run: tox")
    assert apt < browsers < tox
    assert "libpango-1.0-0 libpangoft2-1.0-0" in lines[apt]
    assert "--only-group test" in lines[browsers]
    # Everything else is the template, in order.
    assert [line for line in lines if line in TEMPLATE.splitlines()] == (
        TEMPLATE.splitlines()
    )


def test_postgres_defaults_to_a_current_version() -> None:
    text = render_workflow(TEMPLATE, with_ci({"services": ["postgres"]}))
    assert "        image: postgres:17\n" in text


@pytest.mark.parametrize(
    "config",
    [
        {"services": ["mysql"]},
        {"services": ["postgres:17; rm -rf /"]},
        {"services": ["postgres", "postgres:16"]},
        {"apt": ["pango && curl evil"]},
        {"apt": "libpango-1.0-0"},
        {"playwright": ["chrome"]},
        {"env": {"lower_case": "x"}},
        {"env": {"KEY": "two\nlines"}},
        {"env": {"KEY": 1}},
        {"env": ["KEY"]},
        {"run": ["make test"]},
    ],
)
def test_anything_outside_the_patterns_is_refused(config: dict[str, Any]) -> None:
    with pytest.raises(BootstrapError):
        render_workflow(TEMPLATE, with_ci(config))


def test_env_values_are_quoted_safely() -> None:
    text = render_workflow(TEMPLATE, with_ci({"env": {"KEY": 'a "b": c # d'}}))
    assert '      KEY: "a \\"b\\": c # d"\n' in text


def test_bootstrap_writes_and_checks_accept_the_additions(new_repo: Path) -> None:
    with (new_repo / "pyproject.toml").open("a", encoding="utf-8") as handle:
        handle.write(
            '\n[tool.dev-standards.ci]\nservices = ["postgres"]\n'
            'env = { DATABASE_HOST = "localhost" }\n'
        )
    apply_templates(new_repo, CHECKOUT, force=False)
    written = (new_repo / CI_WORKFLOW).read_text(encoding="utf-8")
    assert "image: postgres:17" in written
    assert run_checks(load_state(new_repo, CHECKOUT)) == []


def test_check_reports_a_workflow_missing_its_additions(new_repo: Path) -> None:
    apply_templates(new_repo, CHECKOUT, force=False)
    with (new_repo / "pyproject.toml").open("a", encoding="utf-8") as handle:
        handle.write('\n[tool.dev-standards.ci]\nservices = ["postgres"]\n')
    found = run_checks(load_state(new_repo, CHECKOUT))
    assert any(gap.startswith(f"{CI_WORKFLOW} differs") for gap in found)
