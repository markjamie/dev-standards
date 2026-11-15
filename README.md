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

## Adopt in a repo

```bash
git submodule add https://github.com/markjamie/dev-standards .dev-standards
python .dev-standards/bootstrap.py
tox
```

Fix anything `bootstrap.py` flags as `ACTION NEEDED`.

## Update a repo

```bash
git submodule update --remote .dev-standards
git add .dev-standards
git commit -m "Update dev-standards"
tox
```

Copied files (`tox.toml`, pre-commit config, `.gitignore`, CI workflow) only change with
`python .dev-standards/bootstrap.py --force`. Review `git diff` afterwards.

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
