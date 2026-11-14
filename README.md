# dev-standards

Shared development standards and tooling config. Read [STANDARDS.md](STANDARDS.md) for the rules.

| Path | Purpose | How repos use it |
|------|---------|------------------|
| `ruff.toml` | Shared ruff rules | Extended by reference |
| `templates/pyproject.toml` | Dependency groups, strict pyright, coverage, interrogate | Copy sections |
| `templates/tox.toml` | Tests on 3.12-3.15, lint, type, docstring and audit envs | Copy |
| `templates/.pre-commit-config.yaml` | ruff, pyright, interrogate hooks via `uv run` | Copy |

## Adopting in a repo

```bash
git submodule add https://github.com/markjamie/dev-standards .dev-standards
cp .dev-standards/templates/tox.toml .dev-standards/templates/.pre-commit-config.yaml .
# merge .dev-standards/templates/pyproject.toml into your pyproject.toml
uv sync && uv run pre-commit install
tox
```

CI must check out submodules (`submodules: true` in `actions/checkout`) and run `tox` only.
Update the standards with `git submodule update --remote` and commit the new pointer.

## Why these choices

- Ruff is the only tool that can extend a config file, so it is shared by reference.
  Pyright, coverage and interrogate have no cross-repo extend, so they live in the template.
- `per-file-ignores` sit in the template, not `ruff.toml`: ruff anchors their globs to the
  defining file's directory, so a shared copy cannot match a repo's `tests/`.
- Pre-commit hooks are `local` and run through `uv run`, so versions come from `uv.lock`
  and cannot drift from tox.
