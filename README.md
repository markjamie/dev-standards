# dev-standards

Shared development standards and tooling config. Read [STANDARDS.md](STANDARDS.md) for the rules.

| Path | Purpose | How repos use it |
|------|---------|------------------|
| `ruff.toml` | Shared ruff rules | Extended by reference |
| `templates/pyproject.template.toml` | Build backend, dependency groups, ruff, strict pyright, coverage, interrogate | Merged |
| `templates/tox.toml` | Tests on 3.12-3.15 and at minimum dependency versions, lint, type, docstring, audit and licence envs | Copied; replaced with `--force` |
| `templates/.pre-commit-config.yaml` | ruff, pyright, interrogate hooks via `uv run` | Copied; replaced with `--force` |
| `templates/AGENTS.md` | Canonical agent instructions; imports `STANDARDS.md` | Import added; repo rules kept |
| `templates/CLAUDE.md` | One-line shim importing `AGENTS.md` for Claude Code | Created if missing |
| `templates/.github/workflows/ci.yml` | Runs `tox` on push and PR without the `minimum` environment, and in full weekly | Replaced on every run, plus any services the repo declares in `[tool.dev-standards.ci]` |
| `templates/.gitignore` | Caches, environments, coverage output, secrets files | Merged |
| `templates/CHANGELOG.md` | Empty Keep a Changelog file | Created if missing |
| `bootstrap.py` and `devstandards/` | Apply all of the above, then report what still differs | Run once; `--check` any time |

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

The bootstrap makes the mechanical changes itself and keeps comments and layout in
`pyproject.toml` outside the tables it edits:

- swaps a setuptools build backend for hatchling and deletes the `[tool.setuptools]`
  tables (hatchling finds a `src/<package>` layout without configuration);
- adds missing tables, dependency groups and tools, keeping existing version bounds
  (comments inside `[dependency-groups]` are not kept when it is rewritten);
- points ruff at `ruff.toml`, turns a local `select` into `extend-select`, and adds the
  template's `per-file-ignores` for paths the repo does not already configure;
- removes ruff settings that repeat `ruff.toml` (`target-version`, `line-length`, the
  complexity limit, the docstring convention, rule families it already selects and
  codes it already ignores) and ruff format's own defaults (`quote-style = "double"`,
  `indent-style = "space"`), keeping the comments beside any entries that stay;
- removes `venvPath` and `venv` from `[tool.pyright]`, which pin pyright to one
  environment so that `tox -e type` would not check its own;
- replaces the CI workflow, since CI runs `tox` and nothing else;
- reduces `.python-version` patch pins to minor versions, and merges `.gitignore`.

What needs judgement is left to you and listed under `ACTION NEEDED`:

- a `tox.ini` (or `[tool.tox]`, or `setup.cfg [tox:tox]`) that hides `tox.toml`: port
  repo-specific environments into `tox.toml`, then delete it;
- thresholds below the standard: raise them, or record why in `AGENTS.md`;
- ruff rules ignored in every file: fix the code, use `per-file-ignores` or a targeted
  `noqa`, or give the reason in `AGENTS.md` (naming the rule code there clears it);
- a pre-commit config that differs from the template, or a `tox.toml` that changes or
  drops a template setting (adding environments and listing them in `env_list` is
  fine, and comments and layout are not compared);
- `setup.py`, `setup.cfg` or setuptools-scm settings that hatchling does not read;
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

Then run `python .dev-standards/bootstrap.py` to apply what the new version adds, and
review `git diff`. `tox.toml` and the pre-commit config only change with `--force`,
which also drops any environments the repo added to `tox.toml`: re-add them after.

## Develop dev-standards

```bash
uv sync
tox
```

`bootstrap.py` is a thin entry point; the logic lives in `devstandards/`, tested under
`tests/`. It uses only the standard library, because it runs before a repo's
environment exists. Its own ruff settings are in `.ruff.toml`, which ruff reads ahead
of the shared `ruff.toml`, so consuming repos never inherit them.

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
