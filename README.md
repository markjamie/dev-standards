# dev-standards

Shared development standards and tooling config. Read [STANDARDS.md](STANDARDS.md) for the rules.

| Path | Purpose | How repos use it |
|------|---------|------------------|
| `ruff.toml` | Shared ruff rules | Extended by reference |
| `templates/pyproject.toml` | Dependency groups, strict pyright, coverage, interrogate | Copy sections |
| `templates/tox.toml` | Tests on 3.12-3.15, lint, type, docstring, audit and licence envs | Copy |
| `templates/.pre-commit-config.yaml` | ruff, pyright, interrogate hooks via `uv run` | Copy |
| `templates/AGENTS.md` | Canonical agent instructions; imports `STANDARDS.md` | Copy, then add repo rules |
| `templates/CLAUDE.md` | One-line shim importing `AGENTS.md` for Claude Code | Copy |
| `templates/.github/workflows/ci.yml` | Runs `tox` on push, PR and weekly | Copy |
| `templates/.gitignore` | Caches, environments, coverage output, secrets files | Copy |
| `bootstrap.py` | Applies all of the above to a repo in one command | Run once |

## Adopting in a repo

From the root of any git repo:

```bash
git submodule add https://github.com/markjamie/dev-standards .dev-standards
python .dev-standards/bootstrap.py
tox
```

`bootstrap.py` is safe to re-run. It:

- copies `tox.toml`, `.pre-commit-config.yaml`, `.gitignore` and the CI workflow (existing files are kept unless `--force`);
- creates `AGENTS.md` importing `STANDARDS.md` and a `CLAUDE.md` shim importing `AGENTS.md`, or prepends the import to existing files (and warns if `CLAUDE.md` holds other content to move);
- adds any missing `pyproject.toml` tables from the template, filling in the package name;
- runs `uv sync` and `pre-commit install` (skip with `--no-install`).

It never edits tables you already have. If your `[tool.ruff]` does not extend the shared
config it prints `ACTION NEEDED` with the line to add. Check its output.

The CI template checks out submodules and runs `tox` only. Its weekly schedule re-runs the dependency audit.
Update the standards with `git submodule update --remote` and commit the new pointer.

## Why these choices

- `AGENTS.md` is canonical because Codex reads it and Claude Code can import it; `CLAUDE.md`
  is a shim, so there is one file to edit.
- A repo may override defaults such as `fail_under` in its own `pyproject.toml`, and records
  why in `AGENTS.md`.

- Ruff is the only tool that can extend a config file, so it is shared by reference.
  Pyright, coverage and interrogate have no cross-repo extend, so they live in the template.
- `per-file-ignores` sit in the template, not `ruff.toml`: ruff anchors their globs to the
  defining file's directory, so a shared copy cannot match a repo's `tests/`.
- Pre-commit hooks are `local` and run through `uv run`, so versions come from `uv.lock`
  and cannot drift from tox.
