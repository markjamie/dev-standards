"""Edit TOML a table at a time, keeping comments and layout everywhere else.

The standard library reads TOML but cannot write it, so edits work on the text of
whole tables. Comments directly above a table header belong to that table and move
with it; text before the first table is the preamble.
"""

import itertools
import json
import re
from collections.abc import Collection, Sequence
from dataclasses import dataclass
from typing import Any

PREAMBLE = ""  # section name for the text before the first table
TABLE_HEADER = re.compile(r"^\s*\[\s*([A-Za-z0-9_.\- ]+?)\s*\]\s*(?:#.*)?$")
BARE_KEY = re.compile(r"[A-Za-z0-9_-]+")


@dataclass(frozen=True)
class Section:
    """One table's text, including the comments above its header."""

    name: str
    text: str


def lookup(data: dict[str, Any], dotted_key: str) -> Any:
    """Return the value at a dotted key, or None if absent (TOML has no null)."""
    node: Any = data
    for part in dotted_key.split("."):
        if not isinstance(node, dict) or part not in node:
            return None
        node = node[part]  # pyright: ignore[reportUnknownVariableType]
    return node  # pyright: ignore[reportUnknownVariableType]


def lookup_table(data: dict[str, Any], dotted_key: str) -> dict[str, Any]:
    """Return the table at a dotted key, or an empty one if absent or not a table."""
    value = lookup(data, dotted_key)
    return value if isinstance(value, dict) else {}  # pyright: ignore[reportUnknownVariableType]


def lookup_list(data: dict[str, Any], dotted_key: str) -> list[Any]:
    """Return the array at a dotted key, or an empty one if absent or not an array."""
    value = lookup(data, dotted_key)
    return value if isinstance(value, list) else []  # pyright: ignore[reportUnknownVariableType]


def _table_name(line: str) -> str | None:
    """Return the table a header line opens, or None if it is not a header."""
    match = TABLE_HEADER.match(line)
    if match is None:
        return None
    return ".".join(part.strip() for part in match.group(1).split("."))


def _is_trivia(line: str) -> bool:
    """Report whether a line is blank or a comment."""
    stripped = line.strip()
    return not stripped or stripped.startswith("#")


def _section_start(lines: Sequence[str], header: int, floor: int) -> int:
    """Return the first line of a table: the comments directly above it, or its header.

    Blank lines between the previous table and those comments stay with the previous
    table, so joining sections reproduces the file exactly.
    """
    start = header
    while start > floor and _is_trivia(lines[start - 1]):
        start -= 1
    while start < header and not lines[start].strip():
        start += 1
    return start


def split_sections(text: str) -> list[Section]:
    """Split TOML text into the preamble followed by one section per table header."""
    lines = text.splitlines(keepends=True)
    headers = [
        (index, name)
        for index, line in enumerate(lines)
        if (name := _table_name(line)) is not None
    ]
    # The preamble keeps any comments above the first table; later tables claim theirs.
    starts = [header for header, _ in headers[:1]]
    for (previous, _), (header, _) in itertools.pairwise(headers):
        starts.append(_section_start(lines, header, floor=previous + 1))
    bounds = [0, *starts, len(lines)]
    names = [PREAMBLE, *(name for _, name in headers)]
    return [
        Section(name, "".join(lines[bounds[i] : bounds[i + 1]]))
        for i, name in enumerate(names)
    ]


def join_sections(sections: Sequence[Section]) -> str:
    """Reassemble sections into TOML text."""
    return "".join(section.text for section in sections)


def table_names(text: str) -> list[str]:
    """List the tables that have their own header, in file order."""
    return [s.name for s in split_sections(text) if s.name != PREAMBLE]


def section_text(text: str, name: str) -> str | None:
    """Return a table's text, or None if it has no header of its own."""
    return next((s.text for s in split_sections(text) if s.name == name), None)


def append_table(text: str, table_text: str) -> str:
    """Add a table at the end of the file, separated by a blank line."""
    return f"{text.rstrip()}\n\n{table_text.strip()}\n".lstrip()


def replace_table(text: str, name: str, table_text: str) -> str:
    """Replace a table's text, comments above it included, or append it if absent."""
    sections = split_sections(text)
    if name not in (s.name for s in sections):
        return append_table(text, table_text)
    replaced = [
        _replace_keeping_spacing(s, table_text) if s.name == name else s
        for s in sections
    ]
    return join_sections(replaced)


def _replace_keeping_spacing(old: Section, table_text: str) -> Section:
    """Swap a section's text, keeping the blank lines that followed it."""
    trailing = old.text[len(old.text.rstrip("\n")) :]
    return Section(old.name, table_text.rstrip("\n") + (trailing or "\n"))


def remove_tables(text: str, names: Collection[str]) -> str:
    """Delete tables, and the comments above them, from the file."""
    return join_sections([s for s in split_sections(text) if s.name not in names])


def add_lines(
    text: str, name: str, lines: Sequence[str], *, first: bool = False
) -> str:
    """Add key lines to a table (after its header if first), creating it if needed."""
    sections = split_sections(text)
    for index, section in enumerate(sections):
        if section.name == name:
            sections[index] = Section(name, _insert(section.text, lines, first=first))
            return join_sections(sections)
    return append_table(text, "\n".join([f"[{name}]", *lines]))


def _insert(table_text: str, new_lines: Sequence[str], *, first: bool) -> str:
    """Insert lines after a table's header, or after its last non-blank line."""
    lines = table_text.splitlines(keepends=True)
    if first:
        position = next(i for i, line in enumerate(lines) if _table_name(line)) + 1
    else:
        position = max(i for i, line in enumerate(lines) if line.strip()) + 1
        lines[position - 1] = lines[position - 1].rstrip("\n") + "\n"
    lines[position:position] = [f"{line}\n" for line in new_lines]
    return "".join(lines)


def rename_key(text: str, name: str, old_key: str, new_key: str) -> str:
    """Rename a key that sits directly in a table with its own header."""
    pattern = re.compile(rf"^(\s*){re.escape(old_key)}(\s*=)", re.MULTILINE)
    sections = [
        Section(s.name, pattern.sub(rf"\g<1>{new_key}\g<2>", s.text))
        if s.name == name
        else s
        for s in split_sections(text)
    ]
    return join_sections(sections)


def toml_key(key: str) -> str:
    """Write a key bare when TOML allows it, quoted otherwise."""
    return key if BARE_KEY.fullmatch(key) else json.dumps(key)


def toml_value(value: object) -> str:
    """Write a string, number, boolean, list or inline table as TOML."""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, str | int | float):
        return json.dumps(value)  # JSON strings and numbers are valid TOML
    if isinstance(value, list):
        items: list[object] = value  # pyright: ignore[reportUnknownVariableType]
        return "[" + ", ".join(toml_value(item) for item in items) + "]"
    if isinstance(value, dict):
        pairs: dict[str, object] = value  # pyright: ignore[reportUnknownVariableType]
        body = ", ".join(f"{toml_key(k)} = {toml_value(v)}" for k, v in pairs.items())
        return "{ " + body + " }"
    msg = f"cannot write {type(value).__name__} as TOML"
    raise TypeError(msg)


# --- Key-level edits --------------------------------------------------------------

KEY_LINE = r"^\s*{key}\s*="
STRING_ITEM = re.compile(r"\"(?:[^\"\\]|\\.)*\"|'[^']*'")


def _code_part(line: str) -> str:
    """Return a line without its comment, leaving any '#' inside strings alone."""
    quote = ""
    for index, char in enumerate(line):
        if quote:
            if char == quote:
                quote = ""
        elif char in "\"'":
            quote = char
        elif char == "#":
            return line[:index]
    return line


def _value_end(lines: Sequence[str], start: int) -> int:
    """Return the index after the last line of the key that starts at ``start``."""
    depth = 0
    for index in range(start, len(lines)):
        code = STRING_ITEM.sub("", _code_part(lines[index]))
        depth += code.count("[") + code.count("{") - code.count("]") - code.count("}")
        if depth <= 0:
            return index + 1
    return len(lines)


def _key_lines(table_text: str, key: str) -> tuple[list[str], int, int] | None:
    """Split a table's lines and find a key's span, or None if it is not there."""
    lines = table_text.splitlines(keepends=True)
    pattern = re.compile(KEY_LINE.format(key=re.escape(key)))
    start = next((i for i, line in enumerate(lines) if pattern.match(line)), None)
    if start is None:
        return None
    return lines, start, _value_end(lines, start)


def _has_keys(table_text: str) -> bool:
    """Report whether a table section holds a key, not only a header and comments."""
    return any(
        not _is_trivia(line) and _table_name(line) is None
        for line in table_text.splitlines()
    )


def _edit_section(text: str, name: str, new_text: str) -> str:
    """Replace one section's text, dropping the table if no keys remain."""
    sections = split_sections(text)
    if not _has_keys(new_text):
        return join_sections([s for s in sections if s.name != name])
    return join_sections(
        [Section(name, new_text) if s.name == name else s for s in sections]
    )


def remove_key(text: str, name: str, key: str) -> str:
    """Delete a key, and the comments directly above it, from a table with a header.

    A table left without keys is deleted too, along with its banner.
    """
    table_text = section_text(text, name)
    found = _key_lines(table_text, key) if table_text is not None else None
    if found is None:
        return text
    lines, start, end = found
    while start > 0 and lines[start - 1].strip().startswith("#"):
        start -= 1
    del lines[start:end]
    return _edit_section(text, name, "".join(lines))


def remove_array_items(text: str, name: str, key: str, items: Collection[str]) -> str:
    """Delete string entries from an array, keeping the other entries' comments."""
    table_text = section_text(text, name)
    found = _key_lines(table_text, key) if table_text is not None else None
    if found is None:
        return text
    lines, start, end = found
    kept = [_without_items(line, items) for line in lines[start:end]]
    lines[start:end] = [line for line in kept if line is not None]
    return _edit_section(text, name, "".join(lines))


def _without_items(line: str, items: Collection[str]) -> str | None:
    """Return a line with the given string entries removed, or None if it empties.

    The entries left keep their order, the line's indent and its comment. A line
    that held only dropped entries goes, with its comment, which described them.
    """
    code = _code_part(line)
    matches = list(STRING_ITEM.finditer(code))
    remaining = [m.group() for m in matches if m.group()[1:-1] not in items]
    if len(remaining) == len(matches):
        return line
    trailing_comma = re.match(r"\s*,", code[matches[-1].end() :])
    tail_start = matches[-1].end() + (trailing_comma.end() if trailing_comma else 0)
    head, tail = code[: matches[0].start()], code[tail_start:]
    if not remaining and not head.strip() and not tail.strip():
        return None
    body = ", ".join(remaining) + ("," if remaining and trailing_comma else "")
    comment = line[len(code) :]
    return f"{head}{body}{tail}{comment}"
