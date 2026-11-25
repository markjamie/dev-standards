"""Guard template settings that would otherwise pass without checking."""

import tomllib
from typing import Any

import pytest

from devstandards.layout import TEMPLATES_DIR

LOCK_RUNNER = "uv-venv-lock-runner"


@pytest.fixture(scope="module")
def tox() -> dict[str, Any]:
    return tomllib.loads(
        (TEMPLATES_DIR / "tox.toml").read_text(encoding="utf-8")
    )


@pytest.fixture(scope="module")
def minimum(tox: dict[str, Any]) -> dict[str, Any]:
    return tox["env"]["minimum"]


def test_minimum_runs_by_default(tox: dict[str, Any]) -> None:
    assert "minimum" in tox["env_list"]


def test_minimum_uses_the_oldest_supported_python(
    tox: dict[str, Any], minimum: dict[str, Any]
) -> None:
    assert minimum["base_python"] == [tox["env_list"][0]]


def test_minimum_does_not_install_from_the_lock(
    minimum: dict[str, Any],
) -> None:
    # uv.lock pins the newest versions, which would defeat the check.
    assert minimum["runner"] != LOCK_RUNNER


def test_minimum_installs_nothing_before_its_own_resolution(
    minimum: dict[str, Any],
) -> None:
    # Anything installed first (the inherited test group, or the package
    # itself) can bring in newer versions that the lowest-direct install then
    # keeps.
    assert minimum["dependency_groups"] == []
    assert minimum["skip_install"] is True


def test_minimum_resolves_package_and_tests_in_one_step(
    minimum: dict[str, Any],
) -> None:
    (install,) = minimum["commands_pre"]
    assert install[:3] == ["uv", "pip", "install"]
    assert install[install.index("--resolution") + 1] == "lowest-direct"
    assert install[install.index("--group") + 1] == "test"
    assert install[-1] == "."


def test_other_test_envs_use_the_lock(tox: dict[str, Any]) -> None:
    assert tox["env_run_base"]["runner"] == LOCK_RUNNER


def test_test_envs_keep_separate_coverage_data(tox: dict[str, Any]) -> None:
    # A shared ./.coverage is written by every test environment at once under
    # `tox -p`, which corrupts it and fails whichever environments finish
    # together.
    coverage_file = tox["env_run_base"]["set_env"]["COVERAGE_FILE"]
    assert coverage_file.startswith("{env_tmp_dir}/")


def test_no_env_replaces_the_coverage_setting(tox: dict[str, Any]) -> None:
    # An environment's own set_env replaces env_run_base's instead of merging.
    for name, settings in tox["env"].items():
        assert "set_env" not in settings, name
