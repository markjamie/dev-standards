# Development Standards

Applies to all repos. Read this before writing, reviewing or refactoring code.
Mechanical rules (formatting, linting, typing) are enforced by tooling; this file covers judgement.

## Priorities (in order)
1. **Correctness**
2. **Readability and maintainability**
3. **Performance**, without sacrificing (2) unless the gain is material. If so, explain it in a comment.
4. **Scalability**: design so features can be added without rewrites.

## Working with Claude
- Run `tox` before declaring any task done, and fix failures rather than reporting them.
- Make small, reviewable changes. Preserve behaviour unless asked to change it.
- Do not add dependencies without asking first.
- Never weaken lint, pyright, coverage or docstring settings to make a check pass. Fix the code, or use a targeted ignore with a reason.
- Follow the existing structure and conventions of the repo. Raise any conflict with this file rather than silently picking one.

## Python versions
- Support Python 3.12 to 3.15. Set `requires-python = ">=3.12,<3.16"` in `pyproject.toml`.
- Write for the oldest supported version (3.12). Do not use syntax or stdlib features newer than 3.12 unless guarded for compatibility. The `type` statement and PEP 695 generics are fine.
- Every supported version is tested via `tox` (see Tooling).

# Code

## Structure
- Split code by responsibility into modules.
- Keep I/O, parsing and business logic separate.
- Keep functions small and single-purpose (aim for under ~30 lines). Extract helpers rather than nesting deeply.
- Keep entry points thin and behind `if __name__ == "__main__":`.
- No global mutable state. Pass dependencies explicitly.

## Object-oriented design
- Model domain concepts as classes, with behaviour next to the data it works on.
- Define a small abstract base class or `Protocol` wherever there are, or will be, several implementations, so new variants can be added without changing existing code.
- Prefer composition over inheritance, and keep inheritance hierarchies shallow.
- Keep stateless operations (parsing, numerical routines) as plain functions. This also suits vectorised NumPy code.
- Within classes, group methods in this order: dunder, public, then private (single leading underscore). Within each group, keep methods in alphabetical order, except that `__init__` always comes first.

## Typing and documentation
- Type-hint all signatures, class attributes and return types. Use modern syntax (`list[int]`, `X | None`).
- Use frozen `@dataclass`, `TypedDict` or `NamedTuple` instead of bare tuples or nested dicts.
- Use `pydantic` models where data crosses a boundary or needs validation: config files, API payloads, parsed input, serialisation. Use plain dataclasses for internal data that is already trusted, since they are lighter and faster.
- One-line docstring on every public module, class and function stating *why* it exists. Add Args/Returns only when not obvious from the types. Docstring coverage is enforced by `interrogate`.
- Comment *why*, not *what*.

## Naming and constants
- Descriptive, unambiguous names (`activity_bq_per_g`, not `x2`).
- Include units in names or docs (`energy_kev`, `half_life_s`).
- No magic numbers or strings: use named module-level constants or enums.
- Use `pathlib.Path` for all paths.

## Performance
- Vectorise numerical work (NumPy / pandas / SciPy). Avoid Python loops over large arrays.
- Use generators and iterators for large or streaming data.
- Choose the right data structure (sets/dicts for lookup, `deque` for queues).
- Profile before optimising. Add a short comment for any non-obvious optimisation.
- Cache expensive pure functions with `functools.lru_cache` where appropriate.
- Use concurrency (threads, processes or `asyncio`) only when there is a real benefit, shown by profiling. Otherwise keep the code sequential.

## Robustness
- Validate inputs at boundaries. Raise specific exceptions with clear messages. Never use bare `except:`.
- Use `logging`, not `print`, for diagnostics.
- Make behaviour configurable via arguments or a config object, not hard-coded.
- Define a small custom exception hierarchy per package, with one base exception that the others inherit from, so callers can catch precisely.
- Libraries log but never configure logging. Handlers, levels and formats are set only at the application entry point.
- Use `logging.getLogger(__name__)` in every module.

## Scientific code
- Seed all randomness explicitly and make the seed configurable, so results are reproducible.
- Keep units explicit. Include them in names (`energy_kev`) and use `pint` where unit conversions are non-trivial or error-prone.
- Compare floating-point results with explicit tolerances (e.g. `pytest.approx` with stated `rel` and `abs`), never exact equality.
- Record data provenance: where inputs came from, their version or date, and the parameters used to produce each output.

# Process and tooling

## Testing
- Write `pytest` tests for core logic. Tests double as documentation of intended behaviour.
- Test behaviour at module boundaries, not private implementation details.
- Mirror the source layout: `tests/` follows `src/<package>/`, with one test module per source module (`foo.py` is tested in `test_foo.py`).
- Put shared fixtures in `conftest.py`, scoped as narrowly as possible.
- Use `pytest.mark.parametrize` rather than copy-pasted test cases.
- Measure coverage with `coverage` (via `pytest-cov`), including branch coverage. The build fails if total coverage is below 95% (`fail_under = 95`).
- Coverage settings live in `pyproject.toml` under `[tool.coverage]`, and the `test` dependency group includes `pytest-cov`.

## Dependencies
- All project metadata and dependencies live in `pyproject.toml`.
- Use `hatchling` as the build backend:
  ```toml
  [build-system]
  requires = ["hatchling"]
  build-backend = "hatchling.build"
  ```
- Use a `src/` layout so tests always run against the installed package, not the working directory.
- Runtime dependencies go in `[project.dependencies]`. Use `[project.optional-dependencies]` only for extras that end users install.
- Development dependencies go in PEP 735 `[dependency-groups]`, not in extras or `requirements*.txt` files.
- Use one group per purpose so each tool installs only what it needs: `test` (pytest and plugins), `lint` (ruff, interrogate), `typecheck` (pyright) and `docs` where relevant.
- Add a `dev` group that includes the others (`{include-group = "test"}`, etc.) for a full local environment.
- Give dependencies sensible lower bounds. Pin exact versions through a lock file, not in `pyproject.toml`.
- Use `uv` to manage environments, dependencies and the lock file. Commit `uv.lock`, and use `uv sync` to set up an environment.

## Tooling
- Code must pass all of these cleanly:
  - `ruff` for linting and formatting.
  - `pyright` for type checking (not mypy), always in strict mode (`typeCheckingMode = "strict"` under `[tool.pyright]` in `pyproject.toml`). Do not weaken it repo-wide. If something genuinely cannot be typed, use a targeted `# pyright: ignore[rule]` with a comment saying why.
  - `interrogate` for docstring coverage.
  - `pytest` across all supported Python versions via `tox`.
- `tox` is the single entry point: one `tox` run executes tests on 3.12 to 3.15 and runs the lint, type and docstring checks, so local runs match CI.
- `tox` environments install tools from the dependency groups via `dependency_groups = test` (etc.), so tool versions are defined once in `pyproject.toml`. This needs tox 4.22 or later.
- Shared config lives in the `dev-standards` repo. Repos extend it and keep only local overrides.

## Ruff rules
- Select an explicit list of rule families. Do not use `select = ["ALL"]`: it adds new rules on every ruff upgrade and would break CI across repos at once.
- Keep the list grouped and commented in the shared `ruff.toml`. Repos extend it and add only local overrides.
- Set `target-version = "py312"` and `line-length = 88`.
- Selected families:
  - Core: `E`, `W`, `F`, `I` (imports), `N` (naming), `UP` (modern syntax)
  - Correctness and simplicity: `B`, `BLE`, `SIM`, `C4`, `RET`, `ARG`, `RUF`
  - Standards in this file: `PTH` (pathlib), `T20` (no print), `PERF`, `NPY`, `PD`, `PT`, `PL`, `TRY`, `TC`, `S`, `D`
- Docstring convention is `google`. Ignore `D203` and `D213`, which conflict with `D211` and `D212`.
- Do not select `ANN`: strict pyright already covers annotations.
- Use `per-file-ignores` for tests and scripts (e.g. `S101`, `D`, `PLR2004` in `tests/**`), not repo-wide ignores.
- Add new rule families one at a time, running `ruff check` after each.

## Pre-commit and CI
- Every repo has a `.pre-commit-config.yaml` running `ruff` (lint and format), `pyright` and `interrogate`, so problems are caught before commit.
- CI runs `tox` and nothing else, so CI and local runs are identical. CI fails on any tox failure, including the coverage threshold.
- Keep tool versions in the pre-commit config and dependency groups aligned.

## Git
- Always make changes on a new branch and merge them into `main` through a pull request. Never commit directly to `main`.
- Branches created by Claude Code use the prefix `claudecode/`. Branches created by Codex use the prefix `codex/`.

## Security
- Never commit secrets (API keys, passwords, tokens, credentials). Load them from the environment or a secrets manager, and keep any local `.env` files in `.gitignore`.
- Audit dependencies for known vulnerabilities with `pip-audit`. Add it to the `lint` dependency group and run it as a `tox` environment, so CI fails on any known vulnerability.
- Also run the audit on a weekly schedule in CI, so new vulnerabilities are caught even when the code has not changed.
- Triage audit failures rather than ignoring them: upgrade the dependency, or if no fix exists, suppress that specific advisory with a comment giving the reason and a review date.

## Documentation and versioning
- Every repo has a `README.md` covering what it is, how to install it, a quick-start example, and how to set up the dev environment and run `tox`.
- Keep a `CHANGELOG.md` in the Keep a Changelog format, updated with each user-visible change.
- Use semantic versioning: breaking changes bump the major version, new features the minor, fixes the patch.

## Reviewing and refactoring
- Report issues in this order: readability, typing, structure, performance.
- Preserve behaviour. Propose changes as small, reviewable steps.
- Keep explanations concise.

## Repo-specific rules
Anything specific to a single repo goes in that repo's `CLAUDE.md`, below the import of this file, not here.
