# dev-standards

Shared development standards and tooling config. Read [STANDARDS.md](STANDARDS.md) for the rules.

| Path | Purpose | How repos use it |
|------|---------|------------------|
| `ruff.toml` | Shared ruff rules | Extended by reference |
| `templates/pyproject.template.toml` | Dependency groups, strict pyright, coverage, interrogate | Copy sections |
| `templates/tox.toml` | Tests on 3.12-3.15, lint, type, docstring, audit and licence envs, installed from `uv.lock` | Copy |
| `templates/.pre-commit-config.yaml` | ruff, pyright, interrogate hooks via `uv run` | Copy |
| `templates/AGENTS.md` | Canonical agent instructions; imports `STANDARDS.md` | Copy, then add repo rules |
| `templates/CLAUDE.md` | One-line shim importing `AGENTS.md` for Claude Code | Copy |
| `templates/.github/workflows/ci.yml` | Runs `tox` on push, PR and weekly | Copy |
| `templates/.gitignore` | Caches, environments, coverage output, secrets files | Merged |
| `templates/CHANGELOG.md` | Empty Keep a Changelog file | Created if missing |
| `bootstrap.py` | Applies all of the above, then reports what still differs | Run once; `--check` any time |

## Adopt in a repo

Needs `uv` and `tox` with the tox-uv plugin (`uv tool install tox --with tox-uv`).

```bash
git submodule add https://github.com/markjamie/dev-standards .dev-standards
python .dev-standards/bootstrap.py
tox
```

`bootstrap.py` ends with an `ACTION NEEDED` list of every gap it found. Fix each one,
then confirm with `python .dev-standards/bootstrap.py --check`, which changes nothing
and exits non-zero while any gap remains.

### Existing repos

The bootstrap never edits what a repo already has: it appends missing `pyproject.toml`
tables, adds missing `.gitignore` patterns and keeps every other existing file. Expect
the list to include:

- a `tox.ini` (or `[tool.tox]`, or `setup.cfg [tox:tox]`) that hides `tox.toml`: port
  repo-specific environments into `tox.toml`, then delete it;
- a local ruff `select`, which replaces the shared rules: switch to `extend-select`;
- missing dependency groups or tools, which make the matching tox environments fail;
- thresholds or settings weaker than the standard, and a non-hatchling build backend;
- a CI workflow or pre-commit config that differs from the template;
- an existing `AGENTS.md` whose own rules now repeat or contradict `STANDARDS.md`.

Turning on the shared ruff rules usually surfaces new findings. Fix them, or add a
targeted ignore with a reason, as a separate commit.

## Update a repo

```bash
git submodule update --remote .dev-standards
git add .dev-standards
git commit -m "Update dev-standards"
tox
```

Then run `python .dev-standards/bootstrap.py --check` to see what the new version asks
for. Copied files (`tox.toml`, pre-commit config, CI workflow) only change with
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
- Pre-commit hooks run through `uv run` and tox uses tox-uv's lock runner, so both take
  tool versions from `uv.lock` and cannot drift apart.
- The pyproject template is not called `pyproject.toml`, because ruff would load it as
  the config for the submodule's files and fail on its relative `extend` path. Once a
  repo extends `ruff.toml`, ruff skips `.dev-standards` altogether.
