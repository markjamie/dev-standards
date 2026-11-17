import tomllib
from pathlib import Path

import pytest

from devstandards.apply import (
    add_missing_tables,
    apply_templates,
    configure_ruff,
    copy_template,
    drop_pyright_venv,
    drop_redundant_ruff_settings,
    ensure_import,
    merge_dependency_groups,
    pin_minor_versions,
    update_pyproject,
    use_hatchling,
)
from devstandards.errors import BootstrapError
from devstandards.layout import PYPROJECT_TEMPLATE, render_template
from devstandards.toml_text import table_names
from repos import CHECKOUT, MINIMAL_PYPROJECT, PACKAGE, SETUPTOOLS_PYPROJECT

TEMPLATE = render_template(PYPROJECT_TEMPLATE, CHECKOUT, PACKAGE)
CI = ".github/workflows/ci.yml"


def parse(text: str) -> dict[str, object]:
    return tomllib.loads(text)


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


class TestAddMissingTables:
    def test_appends_only_absent_tables(self) -> None:
        result = add_missing_tables(SETUPTOOLS_PYPROJECT, TEMPLATE)
        assert result.startswith(SETUPTOOLS_PYPROJECT.rstrip())
        names = table_names(result)
        assert names.count("tool.ruff") == 1
        assert names.count("project") == 1

    def test_new_repo_gets_every_table(self) -> None:
        result = add_missing_tables(MINIMAL_PYPROJECT, TEMPLATE)
        assert set(table_names(TEMPLATE)) <= set(table_names(result))


class TestUseHatchling:
    def test_replaces_setuptools_and_its_tables(self) -> None:
        result = use_hatchling(SETUPTOOLS_PYPROJECT, TEMPLATE)
        parsed = tomllib.loads(result)
        assert parsed["build-system"] == tomllib.loads(TEMPLATE)["build-system"]
        assert "setuptools" not in parsed.get("tool", {})
        assert "# Setuptools" not in result
        assert "# Interrogate" in result
        assert "# Project" in result

    @pytest.mark.parametrize(
        "backend", ["setuptools.build_meta:__legacy__", "setuptools.build_meta"]
    )
    def test_swaps_every_setuptools_backend(self, backend: str) -> None:
        text = (
            f'[build-system]\nrequires = ["setuptools"]\nbuild-backend = "{backend}"\n'
        )
        result = use_hatchling(text, TEMPLATE)
        assert (
            tomllib.loads(result)["build-system"]["build-backend"] == "hatchling.build"
        )

    @pytest.mark.parametrize("text", [MINIMAL_PYPROJECT, "[project]\nname = 'x'\n"])
    def test_leaves_other_builds_alone(self, text: str) -> None:
        assert use_hatchling(text, TEMPLATE) == text


class TestMergeDependencyGroups:
    def test_adds_missing_tools_and_groups(self) -> None:
        groups = tomllib.loads(merge_dependency_groups(SETUPTOOLS_PYPROJECT, TEMPLATE))[
            "dependency-groups"
        ]
        assert "pip-audit>=2.7" in groups["lint"]
        assert "ruff>=0.8.0" in groups["lint"]  # repo bound kept, not the template's
        assert groups["typecheck"] == ["pyright>=1.1.408"]  # the repo's bound
        assert {"include-group": "typecheck"} in groups["dev"]
        assert "tox>=4.22.0" in groups["dev"]

    def test_keeps_the_repos_indent(self) -> None:
        text = '[dependency-groups]\ntest = [\n  "pytest",\n]\n'
        result = merge_dependency_groups(text, TEMPLATE)
        assert '\n  "pytest-cov>=5",\n' in result
        assert "\n    " not in result

    def test_defaults_to_four_spaces_for_one_line_arrays(self) -> None:
        result = merge_dependency_groups(
            '[dependency-groups]\ntest = ["pytest"]\n', TEMPLATE
        )
        assert '\n    "pytest",\n' in result

    def test_conforming_groups_are_untouched(self) -> None:
        text = add_missing_tables(MINIMAL_PYPROJECT, TEMPLATE)
        assert merge_dependency_groups(text, TEMPLATE) == text

    def test_skips_groups_written_as_dotted_keys(self) -> None:
        text = 'dependency-groups.test = ["pytest"]\n'
        assert merge_dependency_groups(text, TEMPLATE) == text


class TestConfigureRuff:
    def test_extends_shared_rules_and_keeps_local_ones(self) -> None:
        ruff = tomllib.loads(configure_ruff(SETUPTOOLS_PYPROJECT, TEMPLATE))["tool"][
            "ruff"
        ]
        assert ruff["extend"] == f"{CHECKOUT}/ruff.toml"
        assert ruff["line-length"] == 88
        assert ruff["lint"]["extend-select"] == ["E", "F", "A", "PIE"]
        assert "select" not in ruff["lint"]
        ignores = ruff["lint"]["per-file-ignores"]
        assert ignores["**/tests/*.py"] == ["D", "PT018"]
        assert "S101" in ignores["tests/**"]

    def test_is_idempotent(self) -> None:
        once = configure_ruff(SETUPTOOLS_PYPROJECT, TEMPLATE)
        assert configure_ruff(once, TEMPLATE) == once

    def test_leaves_select_alongside_extend_select(self) -> None:
        text = (
            '[tool.ruff]\nextend = "x"\n\n'
            '[tool.ruff.lint]\nselect = ["E"]\nextend-select = ["F"]\n'
        )
        result = configure_ruff(text, TEMPLATE)
        assert tomllib.loads(result)["tool"]["ruff"]["lint"]["select"] == ["E"]

    def test_creates_ruff_table_when_absent(self) -> None:
        ruff = tomllib.loads(configure_ruff(MINIMAL_PYPROJECT, TEMPLATE))["tool"][
            "ruff"
        ]
        assert ruff["extend"] == f"{CHECKOUT}/ruff.toml"


# Modelled on radchem before it adopted dev-standards: settings the shared ruff.toml
# already makes, a repo-wide ignore list and a pyright pinned to .venv.
REDUNDANT_PYPROJECT = """\
[tool.ruff]
extend = ".dev-standards/ruff.toml"
target-version = "py312"
line-length = 88

[tool.ruff.lint]
extend-select = [
    "E",     # pycodestyle
    "A",     # prevent shadowing builtins
    "PIE",   # miscellaneous simplifications
]
# D105: magic methods inherit their class docs.
ignore = [
  "D105",
  "D203",
]

[tool.ruff.lint.mccabe]
max-complexity = 10

[tool.ruff.format]
quote-style = "double"
indent-style = "space"

[tool.pyright]
include = ["src"]
venvPath = "."
venv = ".venv"
typeCheckingMode = "strict"
"""


class TestDropRedundantSettings:
    def test_keeps_only_local_ruff_overrides(self) -> None:
        result = drop_redundant_ruff_settings(REDUNDANT_PYPROJECT, TEMPLATE)
        ruff = tomllib.loads(result)["tool"]["ruff"]
        assert ruff == {
            "extend": ".dev-standards/ruff.toml",
            "lint": {"extend-select": ["A", "PIE"], "ignore": ["D105"]},
        }
        assert "# prevent shadowing builtins" in result
        assert "# D105: magic methods inherit their class docs." in result
        assert "# pycodestyle" not in result

    def test_is_idempotent(self) -> None:
        once = drop_redundant_ruff_settings(REDUNDANT_PYPROJECT, TEMPLATE)
        assert drop_redundant_ruff_settings(once, TEMPLATE) == once

    def test_leaves_dotted_keys_for_the_checks(self) -> None:
        text = "[tool]\nruff.line-length = 88\n"
        assert drop_redundant_ruff_settings(text, TEMPLATE) == text

    def test_unpins_pyright(self) -> None:
        result = drop_pyright_venv(REDUNDANT_PYPROJECT, TEMPLATE)
        assert tomllib.loads(result)["tool"]["pyright"] == {
            "include": ["src"],
            "typeCheckingMode": "strict",
        }
        assert drop_pyright_venv(result, TEMPLATE) == result


class TestUpdatePyproject:
    def test_writes_valid_conforming_file(self, setuptools_repo: Path) -> None:
        update_pyproject(setuptools_repo, CHECKOUT, PACKAGE)
        parsed = tomllib.loads(read(setuptools_repo / "pyproject.toml"))
        assert parsed["build-system"]["build-backend"] == "hatchling.build"
        assert parsed["tool"]["ruff"]["extend"] == f"{CHECKOUT}/ruff.toml"
        assert "typecheck" in parsed["dependency-groups"]
        assert parsed["tool"]["coverage"]["report"]["fail_under"] == 90  # judgement
        # Shared settings go; the repo's own rule families stay.
        assert "line-length" not in parsed["tool"]["ruff"]
        assert parsed["tool"]["ruff"]["lint"]["extend-select"] == ["A", "PIE"]

    def test_refuses_to_write_invalid_toml(self, new_repo: Path) -> None:
        # ruff configured by dotted keys under [tool] cannot take a [tool.ruff] table.
        original = MINIMAL_PYPROJECT + "\n[tool]\nruff.line-length = 88\n"
        (new_repo / "pyproject.toml").write_text(original, encoding="utf-8")
        with pytest.raises(BootstrapError, match="invalid TOML"):
            update_pyproject(new_repo, CHECKOUT, PACKAGE)
        assert read(new_repo / "pyproject.toml") == original


class TestFiles:
    def test_copy_keeps_existing_unless_overwriting(self, tmp_path: Path) -> None:
        target = tmp_path / "tox.toml"
        target.write_text("mine", encoding="utf-8")
        copy_template(tmp_path, "tox.toml", CHECKOUT, PACKAGE, overwrite=False)
        assert read(target) == "mine"
        copy_template(tmp_path, "tox.toml", CHECKOUT, PACKAGE, overwrite=True)
        assert read(target) == render_template("tox.toml", CHECKOUT, PACKAGE)

    def test_copy_creates_parent_directories(self, tmp_path: Path) -> None:
        copy_template(tmp_path, CI, CHECKOUT, PACKAGE, overwrite=False)
        assert (tmp_path / CI).exists()

    def test_pin_minor_versions(self, tmp_path: Path) -> None:
        path = tmp_path / ".python-version"
        path.write_text("3.13.1\n3.13.2\n3.12\n", encoding="utf-8")
        pin_minor_versions(tmp_path)
        assert read(path) == "3.13\n3.12\n"

    def test_pin_minor_versions_ignores_missing_file(self, tmp_path: Path) -> None:
        pin_minor_versions(tmp_path)
        assert not (tmp_path / ".python-version").exists()

    def test_ensure_import_creates_prepends_and_skips(self, tmp_path: Path) -> None:
        agents = tmp_path / "AGENTS.md"
        ensure_import(tmp_path, "AGENTS.md", "@x/STANDARDS.md", "x")
        assert read(agents).startswith("@x/STANDARDS.md")
        agents.write_text("# Mine\n", encoding="utf-8")
        ensure_import(tmp_path, "AGENTS.md", "@x/STANDARDS.md", "x")
        assert read(agents) == "@x/STANDARDS.md\n\n# Mine\n"
        ensure_import(tmp_path, "AGENTS.md", "@x/STANDARDS.md", "x")
        assert read(agents).count("@x/STANDARDS.md") == 1


class TestApplyTemplates:
    def test_ci_is_always_replaced(self, setuptools_repo: Path) -> None:
        apply_templates(setuptools_repo, CHECKOUT, force=False)
        assert read(setuptools_repo / CI) == render_template(CI, CHECKOUT, PACKAGE)

    def test_copied_files_need_force(self, setuptools_repo: Path) -> None:
        (setuptools_repo / "tox.toml").write_text("mine", encoding="utf-8")
        apply_templates(setuptools_repo, CHECKOUT, force=False)
        assert read(setuptools_repo / "tox.toml") == "mine"
        apply_templates(setuptools_repo, CHECKOUT, force=True)
        assert read(setuptools_repo / "tox.toml") != "mine"

    def test_changelog_is_never_overwritten(self, new_repo: Path) -> None:
        (new_repo / "CHANGELOG.md").write_text("# History\n", encoding="utf-8")
        apply_templates(new_repo, CHECKOUT, force=True)
        assert read(new_repo / "CHANGELOG.md") == "# History\n"

    def test_fixes_python_version_and_agent_files(self, setuptools_repo: Path) -> None:
        apply_templates(setuptools_repo, CHECKOUT, force=False)
        assert read(setuptools_repo / ".python-version") == "3.13\n3.12\n"
        assert read(setuptools_repo / "AGENTS.md").startswith(
            f"@{CHECKOUT}/STANDARDS.md"
        )
        assert read(setuptools_repo / "CLAUDE.md").strip() == "@AGENTS.md"
