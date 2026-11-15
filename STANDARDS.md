# Development Standards

Applies to all repos. Read this before writing, reviewing or refactoring code.
Mechanical rules (formatting, linting, typing) are enforced by tooling; this file covers judgement.

## Priorities (in order)
1. **Correctness**
2. **Readability and maintainability**: prefer simple, idiomatic code over clever code, speculative abstraction or premature optimisation.
3. **Performance**, without sacrificing (2) unless the gain is material. If so, explain it in a comment.
4. **Scalability**: design so features can be added without rewrites.

## Working with coding agents
- Instructions for agents live in `AGENTS.md`, which is the single canonical file. `CLAUDE.md` is a one-line shim that imports it, so Claude Code and Codex read the same content.
- Read the existing code before changing it, and follow the repo's structure, public interfaces and conventions. Raise any conflict with this file rather than silently picking one.
- Make small, reviewable changes. Preserve behaviour unless asked to change it. Do not refactor speculatively or touch unrelated code.
- Do not add dependencies without asking first. Prefer the standard library.
- Run focused checks (one test module, `ruff`, `pyright`) while developing, and the full `tox` before declaring any task done. Fix failures rather than reporting them.
- Never weaken lint, pyright, coverage or docstring settings, skip or remove tests, or suppress failures to make a check pass. Fix the code, or use a targeted ignore with a reason.
- Review and simplify the final diff before finishing.
- Report changes, validation results and outstanding issues accurately, including anything skipped or not run.

## Definition of done
A task is complete when:
1. The requested behaviour works.
2. The code is simple, readable and maintainable.
3. `tox` passes: tests on every supported Python, coverage, lint, formatting, types, docstrings, audit and licences.
4. Tests cover the change, including edge cases, failures and a regression test for any bug fix.
5. README, docstrings and `CHANGELOG.md` are updated where affected.
6. The diff contains no unrelated changes.
7. Any remaining limitations are stated explicitly.

## Python versions
- Support Python 3.12 to 3.15. Set `requires-python = ">=3.12,<3.16"` in `pyproject.toml`.
- Write for the oldest supported version (3.12). Do not use syntax or stdlib features newer than 3.12 unless guarded for compatibility. The `type` statement and PEP 695 generics are fine.
- Every supported version is tested via `tox` (see Tooling).
- A `.python-version` file, if present, names a minor version (`3.12`), never a patch release, so `uv sync` works with whichever patch is installed.

# Code

## Structure
- Split code by responsibility into modules.
- Keep I/O, parsing and business logic separate.
- Keep functions small and single-purpose (aim for under ~30 lines). Extract helpers rather than nesting deeply.
- Prefer early returns and named intermediate variables over deep nesting and long expressions.
- Keep McCabe complexity at 10 or below (enforced by ruff `C90`).
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
- Use frozen `@dataclass`, `TypedDict` or `NamedTuple` instead of bare tuples or nested dicts. Prefer immutable models where practical.
- Use `pydantic` models where data crosses a boundary or needs validation: config files, API payloads, parsed input, serialisation. Use plain dataclasses for internal data that is already trusted, since they are lighter and faster.
- One-line docstring on every public module, class and function stating *why* it exists. Add Google-style Args/Returns/Raises sections only when not obvious from the types: non-obvious units or constraints, exceptions callers should handle, and public API that library users read. Docstring coverage is enforced by `interrogate`.
- Comment *why*, not *what*. Document important assumptions and non-obvious decisions.
- Use British English in code, comments, docstrings and documentation. Existing public names keep their spelling: renaming one is a breaking change, so leave it for a planned major release.

## Naming and constants
- Descriptive, unambiguous names (`activity_bq_per_g`, not `x2`).
- Include units in names or docs (`energy_kev`, `half_life_s`).
- No magic numbers or strings: use named module-level constants or enums.
- Use `pathlib.Path` for all paths.
- Use timezone-aware datetimes (enforced by ruff `DTZ`). Store and exchange UTC.

## Performance
- Vectorise numerical work (NumPy / pandas / SciPy). Avoid Python loops over large arrays.
- Use generators and iterators for large or streaming data.
- Choose the right data structure (sets/dicts for lookup, `deque` for queues).
- Profile before optimising. Add a short comment for any non-obvious optimisation.
- Cache expensive pure functions with `functools.lru_cache` where appropriate.
- Use concurrency (threads, processes or `asyncio`) only when there is a real benefit, shown by profiling. Otherwise keep the code sequential.

## Robustness
- Validate inputs at boundaries. Fail early with specific exceptions and clear messages. Never use bare `except:`, broad handlers or silently ignored errors. Preserve causes with `raise ... from error`.
- Use `logging`, not `print`, for diagnostics.
- Make behaviour configurable via arguments or a config object, not hard-coded.
- Define a small custom exception hierarchy per package, with one base exception that the others inherit from, so callers can catch precisely.
- Libraries log but never configure logging. Handlers, levels and formats are set only at the application entry point.
- Every module that logs gets its own `logging.getLogger(__name__)`. Do not pass loggers between functions.

## Scientific code
- Seed all randomness explicitly and make the seed configurable, so results are reproducible.
- Keep units explicit. Include them in names (`energy_kev`) and use `pint` where unit conversions are non-trivial or error-prone.
- Compare floating-point results with explicit tolerances (e.g. `pytest.approx` with stated `rel` and `abs`), never exact equality.
- Record data provenance: where inputs came from, their version or date, and the parameters used to produce each output.

# Process and tooling

## Testing
- Write `pytest` tests for core logic. Tests double as documentation of intended behaviour.
- Cover success, edge cases and failures. Add a regression test for every bug fix.
- Keep tests deterministic, isolated and independent of live services, the network and the clock. Use fakes or recorded data.
- Use unit tests for logic and integration tests for module and I/O boundaries.
- Use Hypothesis where properties or wide input ranges make it worthwhile, such as parsers and numerical routines.
- Test behaviour at module boundaries, not private implementation details.
- Mirror the source layout: `tests/` follows `src/<package>/`, with one test module per source module that has behaviour of its own (`foo.py` is tested in `test_foo.py`). Modules that only declare data, such as exceptions, models or constants, may be covered through the tests of the code that uses them.
- Put shared fixtures in `conftest.py`, scoped as narrowly as possible.
- Use `pytest.mark.parametrize` rather than copy-pasted test cases.
- Measure coverage with `coverage` (via `pytest-cov`), including branch coverage. The template sets `fail_under = 95`, which a repo may change in its own `[tool.coverage.report]`. Record the reason in the repo's `AGENTS.md`, and never lower it just to pass a build.
- Coverage settings live in `pyproject.toml` under `[tool.coverage]`, and the `test` dependency group includes `pytest-cov`.

## Dependencies
- All project metadata and dependencies live in `pyproject.toml`.
- Use `hatchling` as the build backend, never setuptools. `bootstrap.py` replaces a setuptools backend automatically:
  ```toml
  [build-system]
  requires = ["hatchling>=1.27"]
  build-backend = "hatchling.build"
  ```
- Use a `src/` layout so tests always run against the installed package, not the working directory.
- Runtime dependencies go in `[project.dependencies]`. Use `[project.optional-dependencies]` only for extras that end users install.
- Development dependencies go in PEP 735 `[dependency-groups]`, not in extras or `requirements*.txt` files.
- Use one group per purpose so each tool installs only what it needs: `test` (pytest and plugins), `lint` (ruff, interrogate, pip-audit, pip-licenses), `typecheck` (pyright) and `docs` where relevant.
- Add a `dev` group that includes the others (`{include-group = "test"}`, etc.) for a full local environment.
- Give dependencies sensible lower bounds. Pin exact versions through a lock file, not in `pyproject.toml`.
- Keep the lower bounds true: the `minimum` tox environment runs the tests with every direct requirement, runtime and test, at its lowest allowed version. When it fails, raise the bound rather than working around the old version.
- Use `uv` to manage environments, dependencies and the lock file. Commit `uv.lock`, use `uv sync` to set up an environment, and run `uv lock` after changing dependencies (tox fails on a stale lock).
- Prefer permissive licences (MIT, BSD, Apache-2.0, PSF). Avoid GPL-family dependencies unless the user has approved them.

## Tooling
- Code must pass all of these cleanly:
  - `ruff` for linting and formatting.
  - `pyright` for type checking (not mypy), always in strict mode (`typeCheckingMode = "strict"` under `[tool.pyright]` in `pyproject.toml`). Do not weaken it repo-wide. If something genuinely cannot be typed, use a targeted `# pyright: ignore[rule]` with a comment saying why.
  - `interrogate` for docstring coverage.
  - `pip-audit` and `pip-licenses` for vulnerability and licence checks.
  - `pytest` across all supported Python versions via `tox`.
- `tox` is the single entry point: one `tox` run executes tests on 3.12 to 3.15 and at the minimum dependency versions, and runs the lint, type, docstring, audit and licence checks, so local runs match CI.
- `tox` environments install tools from the dependency groups via `dependency_groups`, using tox-uv's `uv-venv-lock-runner`, so every environment gets the versions pinned in `uv.lock`. This needs tox 4.22 and tox-uv 1.25 or later (`uv tool install tox --with tox-uv`).
- Repo-specific environments (packaging checks, integration runs) go in the repo's `tox.toml`. Leave any that need real services or credentials out of `env_list`, so a plain `tox` stays self-contained, and record them in `AGENTS.md`.
- Do not keep a `tox.ini`, a `[tox:tox]` section in `setup.cfg` or a `[tool.tox]` table in `pyproject.toml`: tox reads each of them ahead of `tox.toml`.
- Shared config lives in the `dev-standards` repo. Repos extend it and keep only local overrides.

## Ruff rules
- Select an explicit list of rule families. Do not use `select = ["ALL"]`: it adds new rules on every ruff upgrade and would break CI across repos at once.
- Keep the list grouped and commented in the shared `ruff.toml`. Repos extend it and add only local overrides.
- Set `target-version = "py312"` and `line-length = 88`.
- Use double quotes. This is `ruff format`'s default, so leave `quote-style` unset.
- Selected families:
  - Core: `E`, `W`, `F`, `I` (imports), `N` (naming), `UP` (modern syntax)
  - Correctness and simplicity: `B`, `BLE`, `SIM`, `C4`, `C90` (complexity), `RET`, `ARG`, `RUF`
  - Standards in this file: `PTH` (pathlib), `T20` (no print), `DTZ` (aware datetimes), `PERF`, `NPY`, `PD`, `PT`, `PL`, `TRY`, `TC`, `S`, `D`
- Complexity limit is `max-complexity = 10`.
- Docstring convention is `google`. Ignore `D203` and `D213`, which conflict with `D211` and `D212`.
- Do not select `ANN`: strict pyright already covers annotations.
- Use `per-file-ignores` for tests and scripts (e.g. `S101`, `D`, `PLR2004` in `tests/**`), not repo-wide ignores.
- Add local rule families with `extend-select`. A local `select` replaces the shared list instead of adding to it.
- Add new rule families one at a time, running `ruff check` after each.

## Pre-commit and CI
- Every repo has a `.pre-commit-config.yaml` running `ruff` (lint and format), `pyright` and `interrogate`, so problems are caught before commit. The hooks are `local` and run through `uv run`, so their versions come from `uv.lock`, as tox's do.
- CI is a GitHub Actions workflow (`.github/workflows/ci.yml`) that runs `tox` and nothing else, so CI and local runs are identical. CI fails on any tox failure, including the coverage threshold.
- The workflow is the template, unmodified: `bootstrap.py` replaces it on every run, so repos have no CI-specific jobs or exceptions. Anything CI should run goes in `tox.toml`.

## Git
- Use focused commits, each doing one thing.
- Always make changes on a new branch and merge them into `main` through a pull request. Never commit directly to `main`.
- Branches created by Claude Code use the prefix `claude/`, which Claude Code cloud sessions assign. Branches created by Codex use the prefix `codex/`.

## Security
- Never commit secrets (API keys, passwords, tokens, credentials). Load them from the environment or a secrets manager, and keep any local `.env` files in `.gitignore`. Do not log sensitive data.
- Keep generated files, caches, virtual environments and runtime data out of Git. Every repo has a `.gitignore` (the template covers the common cases).
- Audit dependencies for known vulnerabilities with `pip-audit`. Add it to the `lint` dependency group and run it as a `tox` environment, so CI fails on any known vulnerability.
- Check licences with `pip-licenses`, also in the `lint` group and run as a `tox` environment. It fails on GPL-family licences, so any exception is a deliberate, recorded decision.
- Also run the audit on a weekly schedule in CI (the CI workflow's `schedule` trigger runs the full `tox`), so new vulnerabilities are caught even when the code has not changed.
- Triage audit failures rather than ignoring them: upgrade the dependency, or if no fix exists, suppress that specific advisory with a comment giving the reason and a review date.

## Documentation and versioning
- Every repo has a `README.md` covering what it is, how to install it, a quick-start example, and how to set up the dev environment and run `tox`. Keep it and any API documentation accurate.
- Keep a `CHANGELOG.md` in the Keep a Changelog format, updated with each user-visible change.
- Use semantic versioning: breaking changes bump the major version, new features the minor, fixes the patch.

## Reviewing and refactoring
- Report issues in this order: readability, typing, structure, performance.
- Preserve behaviour. Propose changes as small, reviewable steps.
- Keep explanations concise.

## Repo-specific rules
Anything specific to a single repo goes in that repo's `AGENTS.md`, below the import of this file, not here. This includes Python version overrides, coverage thresholds, scientific calculations, database conventions and deployment requirements. A repo may override tool settings in its own `pyproject.toml`, but never to weaken a check without the reason recorded in `AGENTS.md`.
