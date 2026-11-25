"""Merge the template's ignore patterns into a repo's .gitignore."""

import logging
from pathlib import Path

from devstandards.layout import GITIGNORE_FILE, TEMPLATES_DIR, read_text

LOGGER = logging.getLogger(__name__)

HEADER = "# Added by dev-standards"


def _patterns(text: str) -> list[str]:
    """Return the non-blank, non-comment lines of a .gitignore."""
    lines = (line.strip() for line in text.splitlines())
    return [line for line in lines if line and not line.startswith("#")]


def missing_entries(root: Path) -> list[str]:
    """List template patterns the repo's .gitignore lacks."""
    # "x" and "x/" both ignore a directory named x, so treat them as the same
    # entry.
    present = {
        line.rstrip("/")
        for line in _patterns(read_text(root / GITIGNORE_FILE))
    }
    template = (TEMPLATES_DIR / GITIGNORE_FILE).read_text(encoding="utf-8")
    return [
        line for line in _patterns(template) if line.rstrip("/") not in present
    ]


def merge(root: Path) -> None:
    """Append the template patterns the repo does not already have."""
    missing = missing_entries(root)
    if not missing:
        LOGGER.info("%s already covers the template", GITIGNORE_FILE)
        return
    destination = root / GITIGNORE_FILE
    block = "\n".join([HEADER, *missing])
    existing = read_text(destination).rstrip()
    destination.write_text(
        f"{existing}\n\n{block}\n".lstrip(), encoding="utf-8"
    )
    LOGGER.info("%s: added %s", GITIGNORE_FILE, " ".join(missing))
