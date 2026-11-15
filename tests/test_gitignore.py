from pathlib import Path

from devstandards.gitignore import HEADER, merge, missing_entries
from devstandards.layout import TEMPLATES_DIR


def template_patterns() -> list[str]:
    lines = (TEMPLATES_DIR / ".gitignore").read_text(encoding="utf-8").splitlines()
    return [line for line in lines if line and not line.startswith("#")]


def test_missing_entries_treats_trailing_slash_as_equal(tmp_path: Path) -> None:
    (tmp_path / ".gitignore").write_text(".venv\n__pycache__\n", encoding="utf-8")
    missing = missing_entries(tmp_path)
    assert ".venv/" not in missing
    assert "__pycache__/" not in missing
    assert ".env" in missing


def test_merge_appends_only_missing_patterns(tmp_path: Path) -> None:
    (tmp_path / ".gitignore").write_text("# mine\n.env\nlocal/\n", encoding="utf-8")
    merge(tmp_path)
    text = (tmp_path / ".gitignore").read_text(encoding="utf-8")
    assert text.startswith("# mine\n.env\nlocal/\n\n" + HEADER + "\n")
    assert text.count(".env\n") == 1
    assert missing_entries(tmp_path) == []


def test_merge_creates_file_when_absent(tmp_path: Path) -> None:
    merge(tmp_path)
    text = (tmp_path / ".gitignore").read_text(encoding="utf-8")
    assert text.startswith(HEADER)
    assert text.splitlines()[1:] == template_patterns()


def test_merge_leaves_complete_file_alone(tmp_path: Path) -> None:
    complete = "\n".join(template_patterns()) + "\n"
    (tmp_path / ".gitignore").write_text(complete, encoding="utf-8")
    merge(tmp_path)
    assert (tmp_path / ".gitignore").read_text(encoding="utf-8") == complete
