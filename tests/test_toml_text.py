import tomllib

import pytest

from devstandards.toml_text import (
    PREAMBLE,
    add_lines,
    append_table,
    join_sections,
    lookup,
    lookup_list,
    lookup_table,
    remove_tables,
    rename_key,
    replace_table,
    section_text,
    split_sections,
    table_names,
    toml_key,
    toml_value,
)
from repos import SETUPTOOLS_PYPROJECT

BANNERED = """\
# File comment

[a]
x = 1

# Banner for b

[b]
y = 2
# trailing note in b
z = [
    "v",
]

[c]  # inline comment
w = 3
"""


class TestLookup:
    def test_finds_nested_value(self) -> None:
        assert lookup({"a": {"b": {"c": 1}}}, "a.b.c") == 1

    @pytest.mark.parametrize("key", ["a.x", "a.b.c.d", "missing"])
    def test_returns_none_when_absent(self, key: str) -> None:
        assert lookup({"a": {"b": {"c": 1}}}, key) is None

    def test_typed_helpers_fall_back_to_empty(self) -> None:
        data = {"t": {"k": 1}, "l": [1], "s": "x"}
        assert lookup_table(data, "t") == {"k": 1}
        assert lookup_table(data, "s") == {}
        assert lookup_list(data, "l") == [1]
        assert lookup_list(data, "s") == []


class TestSplitSections:
    @pytest.mark.parametrize("text", [BANNERED, SETUPTOOLS_PYPROJECT, "", "x = 1\n"])
    def test_round_trips_exactly(self, text: str) -> None:
        assert join_sections(split_sections(text)) == text

    def test_preamble_keeps_comments_above_first_table(self) -> None:
        preamble = split_sections(BANNERED)[0]
        assert preamble.name == PREAMBLE
        assert preamble.text == "# File comment\n\n"

    def test_banner_belongs_to_the_table_below_it(self) -> None:
        sections = {s.name: s.text for s in split_sections(BANNERED)}
        assert sections["b"].startswith("# Banner for b\n\n[b]")
        assert sections["a"] == "[a]\nx = 1\n\n"

    def test_comments_inside_a_table_stay_there(self) -> None:
        assert "# trailing note in b" in (section_text(BANNERED, "b") or "")

    def test_reads_headers_with_spaces_and_comments(self) -> None:
        assert table_names("[ tool . x ]  # note\nk = 1\n") == ["tool.x"]

    def test_ignores_array_of_tables_and_array_lines(self) -> None:
        text = '[[item]]\nk = 1\n\n[t]\nv = [\n["a"]\n]\n'
        assert table_names(text) == ["t"]


class TestEditing:
    def test_replace_table_swaps_text_and_spacing(self) -> None:
        result = replace_table(BANNERED, "b", "[b]\nnew = true\n")
        assert "# Banner for b" not in result
        assert "[b]\nnew = true\n\n[c]" in result
        assert tomllib.loads(result)["b"] == {"new": True}

    def test_replace_table_appends_when_absent(self) -> None:
        result = replace_table(BANNERED, "d", "[d]\nk = 1")
        assert result.endswith("w = 3\n\n[d]\nk = 1\n")

    def test_replace_last_table_keeps_final_newline(self) -> None:
        assert replace_table("[a]\nx = 1", "a", "[a]\nx = 2").endswith("x = 2\n")

    def test_remove_tables_takes_their_banners(self) -> None:
        result = remove_tables(BANNERED, {"b"})
        assert "Banner for b" not in result
        assert table_names(result) == ["a", "c"]

    def test_append_table_to_empty_text(self) -> None:
        assert append_table("", "[a]\nx = 1\n") == "[a]\nx = 1\n"

    def test_add_lines_first_goes_after_header(self) -> None:
        result = add_lines(BANNERED, "b", ['first = "yes"'], first=True)
        assert '[b]\nfirst = "yes"\ny = 2' in result

    def test_add_lines_last_goes_after_body(self) -> None:
        result = add_lines(BANNERED, "c", ["v = 4"])
        assert result.endswith("w = 3\nv = 4\n")

    def test_add_lines_to_text_without_final_newline(self) -> None:
        assert add_lines("[a]\nx = 1", "a", ["y = 2"]) == "[a]\nx = 1\ny = 2\n"

    def test_add_lines_creates_missing_table(self) -> None:
        result = add_lines(BANNERED, "new.table", ["k = 1"])
        assert tomllib.loads(result)["new"]["table"] == {"k": 1}

    def test_rename_key_only_in_named_table(self) -> None:
        text = "[a]\nselect = 1\n\n[b]\nselect = 2\n"
        result = rename_key(text, "b", "select", "extend-select")
        assert tomllib.loads(result) == {"a": {"select": 1}, "b": {"extend-select": 2}}


class TestWriting:
    @pytest.mark.parametrize(
        ("value", "expected"),
        [
            ('a"b', '"a\\"b"'),
            (3, "3"),
            (1.5, "1.5"),
            (True, "true"),
            (False, "false"),
            (["x", 1], '["x", 1]'),
            ({"include-group": "test"}, '{ include-group = "test" }'),
            ({"a b": 1}, '{ "a b" = 1 }'),
        ],
    )
    def test_toml_value(self, value: object, expected: str) -> None:
        assert toml_value(value) == expected

    def test_toml_value_round_trips(self) -> None:
        value = {"k": ["tests/**", {"n": True}]}
        assert tomllib.loads(f"v = {toml_value(value)}")["v"] == value

    def test_toml_value_rejects_other_types(self) -> None:
        with pytest.raises(TypeError, match="NoneType"):
            toml_value(None)

    @pytest.mark.parametrize(
        ("key", "expected"), [("lint", "lint"), ("tests/**", '"tests/**"')]
    )
    def test_toml_key(self, key: str, expected: str) -> None:
        assert toml_key(key) == expected
