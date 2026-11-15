# dev-standards

Shared development standards and tooling config. Read [STANDARDS.md](STANDARDS.md) for the rules.

| Path | Purpose | How repos use it |
|------|---------|------------------|
| `ruff.toml` | Shared ruff rules | Extended by reference |
| `templates/pyproject.toml` | Dependency groups, strict pyright, coverage, interrogate | Copy sections |
| `templates/tox.toml` | Tests on 3.12-3.15, lint, type, docstring and audit envs | Copy |
| `templates/.pre-commit-config.yaml` | ruff, pyright, interrogate hooks via `uv run` | Copy |
| `templates/CLAUDE.md` | Imports `STANDARDS.md` so Claude always reads it | Copy |
| `bootstrap.py` | Applies all of the above to a repo in one command | Run once |

## Adopting in a repo

From the root of any git repo:

```bash
git submodule add https://github.com/markjamie/dev-standards .dev-standards
python .dev-standards/bootstrap.py
tox
```

`bootstrap.py` is safe to re-run. It:

- copies `tox.toml` and `.pre-commit-config.yaml` (existing files are kept unless `--force`);
- creates `CLAUDE.md` importing `STANDARDS.md`, or prepends the import to an existing one;
- adds any missing `pyproject.toml` tables from the template, filling in the package name;
- runs `uv sync` and `pre-commit install` (skip with `--no-install`).

It never edits tables you already have. If your `[tool.ruff]` does not extend the shared
config it prints `ACTION NEEDED` with the line to add. Check its output.

CI must check out submodules (`submodules: true` in `actions/checkout`) and run `tox` only.
Update the standards with `git submodule update --remote` and commit the new pointer.

## Why these choices

- Ruff is the only tool that can extend a config file, so it is shared by reference.
  Pyright, coverage and interrogate have no cross-repo extend, so they live in the template.
- `per-file-ignores` sit in the template, not `ruff.toml`: ruff anchors their globs to the
  defining file's directory, so a shared copy cannot match a repo's `tests/`.
- Pre-commit hooks are `local` and run through `uv run`, so versions come from `uv.lock`
  and cannot drift from tox.
