from pathlib import Path

import pytest

from devstandards.apply import apply_templates
from devstandards.checks import load_state, run_checks
from repos import CHECKOUT, MODULE


def gaps(root: Path) -> list[str]:
    return run_checks(load_state(root, CHECKOUT))


def edit(path: Path, old: str, new: str) -> None:
    text = path.read_text(encoding="utf-8")
    assert old in text, f"{old!r} not in {path.name}"
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


def append(path: Path, text: str) -> None:
    with path.open("a", encoding="utf-8") as handle:
        handle.write(text)


@pytest.fixture
def conforming(new_repo: Path) -> Path:
    """A new repo after a full bootstrap: every check passes."""
    apply_templates(new_repo, CHECKOUT, force=False)
    return new_repo


def test_conforming_repo_has_no_gaps(conforming: Path) -> None:
    assert gaps(conforming) == []


def test_unbootstrapped_repo_reports_everything(new_repo: Path) -> None:
    found = gaps(new_repo)
    assert "pyproject.toml lacks [tool.ruff]" in found
    assert "tox.toml is missing" in found
    assert "CHANGELOG.md is missing" in found
    assert "CLAUDE.md is missing" in found
    assert f"AGENTS.md does not import @{CHECKOUT}/STANDARDS.md" in found


def test_setuptools_repo_after_bootstrap(setuptools_repo: Path) -> None:
    apply_templates(setuptools_repo, CHECKOUT, force=False)
    assert gaps(setuptools_repo) == [
        "tool.coverage.report.fail_under is 90; the standard is at least 95 "
        "(record the reason in AGENTS.md if deliberate)",
        "tool.interrogate.fail-under is 90; the standard is at least 100 "
        "(record the reason in AGENTS.md if deliberate)",
        "tox reads tox.ini instead of tox.toml: port any repo-specific "
        "environments into tox.toml, then remove it",
    ]


@pytest.mark.parametrize(
    ("old", "new", "expected"),
    [
        (
            'extend = ".dev-standards/ruff.toml"',
            'extend = "elsewhere.toml"',
            'add extend = ".dev-standards/ruff.toml" to [tool.ruff]',
        ),
        (
            "[tool.ruff.lint.per-file-ignores]",
            "[tool.ruff.lint]\nselect = "
            '["E"]\n\n[tool.ruff.lint.per-file-ignores]',
            "tool.ruff.lint.select replaces the shared rule list",
        ),
        (
            '"tests/**"',
            '"other/**"',
            'lacks the template entry for "tests/**"',
        ),
        (
            'typeCheckingMode = "strict"',
            'typeCheckingMode = "basic"',
            "is 'basic'",
        ),
        ('typeCheckingMode = "strict"\n', "", "typeCheckingMode is not set"),
        ("fail_under = 95", "fail_under = 80", "fail_under is 80"),
        ('"pip-audit>=2.7", ', "", "dependency group 'lint' lacks pip-audit"),
        (
            '{include-group = "typecheck"},',
            "",
            "'dev' does not include typecheck",
        ),
        (
            'typecheck = ["pyright>=1.1.390"]\n',
            "",
            "dependency group 'typecheck' is missing",
        ),
    ],
)
def test_pyproject_gaps(
    conforming: Path, old: str, new: str, expected: str
) -> None:
    edit(conforming / "pyproject.toml", old, new)
    assert any(expected in gap for gap in gaps(conforming)), gaps(conforming)


def test_settings_above_the_minimum_pass(conforming: Path) -> None:
    edit(conforming / "pyproject.toml", "fail_under = 95", "fail_under = 99")
    assert gaps(conforming) == []


class TestRuffAndPyright:
    def test_redundant_ruff_settings(self, conforming: Path) -> None:
        append(
            conforming / "pyproject.toml",
            '\n[tool.ruff.format]\nquote-style = "double"\n',
        )
        assert gaps(conforming) == [
            "tool.ruff.format.quote-style repeats the shared ruff config: "
            "remove it"
        ]

    def test_repo_wide_ignores_need_a_reason_in_agents(
        self, conforming: Path
    ) -> None:
        append(
            conforming / "pyproject.toml",
            '\n[tool.ruff.lint]\nignore = ["D105"]\n',
        )
        assert gaps(conforming) == [
            "ruff ignores D105 in every file: fix the code, use "
            "per-file-ignores or "
            "a targeted noqa, or give the reason in AGENTS.md"
        ]
        append(
            conforming / "AGENTS.md", "\n- D105: magic methods inherit docs.\n"
        )
        assert gaps(conforming) == []

    def test_a_code_inside_another_word_is_not_a_reason(
        self, conforming: Path
    ) -> None:
        append(
            conforming / "pyproject.toml",
            '\n[tool.ruff.lint]\nignore = ["S1"]\n',
        )
        append(conforming / "AGENTS.md", "\nS101 is fine in tests.\n")
        assert any(
            "ignores S1 in every file" in gap for gap in gaps(conforming)
        )

    def test_pinned_pyright(self, conforming: Path) -> None:
        edit(
            conforming / "pyproject.toml",
            "[tool.pyright]\n",
            '[tool.pyright]\nvenv = ".venv"\n',
        )
        assert gaps(conforming) == [
            "tool.pyright.venv points pyright at one environment, so tox -e "
            "type "
            "would not check its own: remove it"
        ]


class TestBuild:
    def test_setuptools_leftovers(self, conforming: Path) -> None:
        (conforming / "setup.py").write_text("", encoding="utf-8")
        append(
            conforming / "pyproject.toml",
            '\n[tool.setuptools_scm]\nroot = "."\n',
        )
        found = gaps(conforming)
        assert any(gap.startswith("setup.py is unused") for gap in found)
        assert any(
            gap.startswith("[tool.setuptools_scm] is unused") for gap in found
        )

    def test_dynamic_version_needs_hatch_version(
        self, conforming: Path
    ) -> None:
        edit(
            conforming / "pyproject.toml",
            'version = "0.1.0"',
            'dynamic = ["version"]',
        )
        assert any("[tool.hatch.version]" in gap for gap in gaps(conforming))
        append(
            conforming / "pyproject.toml",
            '\n[tool.hatch.version]\npath = "x"\n',
        )
        assert gaps(conforming) == []

    def test_package_must_be_findable(self, conforming: Path) -> None:
        (conforming / "src" / MODULE / "__init__.py").unlink()
        assert any(f"src/{MODULE}/" in gap for gap in gaps(conforming))
        append(
            conforming / "pyproject.toml",
            '\n[tool.hatch.build.targets.wheel]\npackages = ["lib/x"]\n',
        )
        assert gaps(conforming) == []

    def test_other_backends_skip_hatchling_checks(
        self, conforming: Path
    ) -> None:
        edit(
            conforming / "pyproject.toml",
            '"hatchling.build"',
            '"flit_core.buildapi"',
        )
        (conforming / "src" / MODULE / "__init__.py").unlink()
        found = gaps(conforming)
        assert any(
            "build-backend is 'flit_core.buildapi'" in gap for gap in found
        )
        assert not any(f"src/{MODULE}/" in gap for gap in found)


class TestFiles:
    @pytest.mark.parametrize(
        ("name", "content", "expected"),
        [
            ("tox.ini", "[tox]\n", "tox reads tox.ini instead"),
            (
                "setup.cfg",
                "[tox:tox]\n",
                "tox reads setup.cfg [tox:tox] instead",
            ),
            (".python-version", "3.12.1\n", ".python-version pins 3.12.1"),
            (
                "CLAUDE.md",
                "@AGENTS.md\nMore rules\n",
                "move rules from CLAUDE.md",
            ),
            ("AGENTS.md", "# No import\n", "AGENTS.md does not import"),
            (".gitignore", "", ".gitignore lacks"),
            (
                "tox.toml",
                "",
                "tox.toml differs from the template in requires,",
            ),
            ("tox.toml", "env_list = [", "tox.toml is not valid TOML"),
            (
                ".github/workflows/ci.yml",
                "",
                "rerun bootstrap.py to replace it",
            ),
        ],
    )
    def test_file_gaps(
        self, conforming: Path, name: str, content: str, expected: str
    ) -> None:
        (conforming / name).write_text(content, encoding="utf-8")
        assert any(expected in gap for gap in gaps(conforming)), gaps(
            conforming
        )

    def test_tox_toml_may_add_environments(self, conforming: Path) -> None:
        tox_toml = conforming / "tox.toml"
        edit(tox_toml, '"licenses"]', '"licenses", "integration"]')
        append(
            tox_toml,
            '\n[env.integration]\ncommands = [["pytest", "-m", "slow"]]\n',
        )
        append(tox_toml, '\n[env.manual]\ncommands = [["pytest"]]\n')
        assert gaps(conforming) == []

    def test_tox_toml_ignores_comments_and_layout(
        self, conforming: Path
    ) -> None:
        tox_toml = conforming / "tox.toml"
        tox_toml.write_text(
            "# Local notes\n"
            + tox_toml.read_text(encoding="utf-8").replace(
                "skip_missing_interpreters = false",
                "skip_missing_interpreters=false",
            ),
            encoding="utf-8",
        )
        assert gaps(conforming) == []

    @pytest.mark.parametrize(
        ("old", "new", "departure"),
        [
            ('"lint", ', "", "env_list"),
            ('package = "wheel"', 'package = "skip"', "env_run_base"),
            ('[["pyright"]]', '[["pyright", "src"]]', "env.type"),
            ('"tox-uv>=1.25"', '"tox-uv>=1.12"', "requires"),
        ],
    )
    def test_tox_toml_must_keep_template_settings(
        self, conforming: Path, old: str, new: str, departure: str
    ) -> None:
        edit(conforming / "tox.toml", old, new)
        assert gaps(conforming) == [
            f"tox.toml differs from the template in {departure}: "
            "merge by hand, or use --force"
        ]

    def test_tool_tox_table_hides_tox_toml(self, conforming: Path) -> None:
        append(conforming / "pyproject.toml", "\n[tool.tox]\nenv_list = []\n")
        assert any(
            "pyproject.toml [tool.tox]" in gap for gap in gaps(conforming)
        )

    def test_missing_seeded_and_copied_files(self, conforming: Path) -> None:
        (conforming / "CHANGELOG.md").unlink()
        (conforming / ".pre-commit-config.yaml").unlink()
        found = gaps(conforming)
        assert "CHANGELOG.md is missing" in found
        assert ".pre-commit-config.yaml is missing" in found
