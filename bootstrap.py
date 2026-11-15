"""Set up a repo to use dev-standards, then report where it still differs.

Run from inside the target repo, with dev-standards added as a submodule:
    python .dev-standards/bootstrap.py            # apply templates, install, report
    python .dev-standards/bootstrap.py --check    # report only; exit 1 on any gap
"""

import sys

# Keep the submodule clean: bytecode caches would show as changes in the parent repo.
sys.dont_write_bytecode = True

from devstandards.cli import main  # noqa: E402  # must follow the line above

if __name__ == "__main__":
    sys.exit(main())
