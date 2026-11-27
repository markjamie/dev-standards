---
name: dev-standards-comply
description: Update the dev-standards submodule to latest and bring this repo into compliance with it. Only when the user runs /dev-standards-comply.
argument-hint: "[--dry-run] [--full] [--since <sha>] [--no-branch]"
disable-model-invocation: true
---


# /dev-standards-comply

Update this repo's `dev-standards` submodule to the latest commit, then bring the
local code base into compliance with the standards as they now stand. Prioritise
anything that changed in the standards since this repo last synced.

Arguments: `$ARGUMENTS`

- `--dry-run`: do steps 1–4 and report the violations. Change no code, and leave the submodule pointer where it was.
- `--full`: treat every standard as new and check all of them closely (use on a repo's first sync).
- `--since <sha>`: use this standards commit as the baseline, not the recorded submodule pointer.
- `--no-branch`: work on the current branch instead of creating one.

Work through the steps in order. Do not skip the safety checks.

## 1. Preflight

1. Confirm this is a git repo, and find the standards submodule. It is the entry in `.gitmodules` whose path or URL contains `dev-standards`. If there is none, stop and say so. If there is more than one, ask which to use. Call its path `$STD` below.
2. Run `git status --porcelain`. If the working tree is dirty, stop and ask the user to commit or stash first. Never stash their work for them.
3. Unless `--no-branch` or `--dry-run` was given: if already on a non-default branch created for this session (typical in a cloud session, e.g. `claude/...`), use it; otherwise create and switch to `chore/dev-standards-<YYYY-MM-DD>`.
4. Find the repo's test and check commands, in this order of preference: `tox`, `pyproject.toml` scripts or dependency groups, a `Makefile`, CI config. If the dev tools aren't installed (common in a fresh cloud clone), install the repo's dev dependencies first, using uv if the repo uses it. Run the test suite now and record the result as the **baseline**. If tests already fail, report which ones, and carry on only if the user agrees. Pre-existing failures must not be blamed on this run.

## 2. Update the submodule and find the delta

1. Record the old pointer: `OLD=$(git rev-parse HEAD:$STD)`, or the `--since` value if given.
2. Update: `git submodule update --init --remote $STD`, then `NEW=$(git -C $STD rev-parse HEAD)`. If the fetch fails in a cloud session, the session probably can't access the dev-standards repo: say so and stop.
3. If `OLD == NEW` and `--full` was not given, say the standards haven't changed. Still do the drift check in step 4, but keep it light.
4. Get the delta: `git -C $STD log --oneline $OLD..$NEW` and `git -C $STD diff $OLD..$NEW`. If the standards repo has a CHANGELOG, read the entries in that range too.
5. Read the full current standards document(s) in `$STD`, and any config fragments it ships (Ruff, Pyright, Interrogate, tox, pyproject templates).

## 3. Classify the standards

Build a short working list of the standards. Use the standards' own rule IDs if they have them. Otherwise give each rule a short label.

Mark each rule with:

- **New or changed**: touched by the `$OLD..$NEW` delta (or every rule, under `--full`).
- **Unchanged**: everything else.

and with how it is enforced:

- **Tool-enforced**: a linter, type checker, docstring coverage or tox config can check it.
- **Judgement**: needs reading the code (readability, structure, naming, data-model choices, project layout).

## 4. Audit

1. **Config first.** Compare the repo's tool config (`pyproject.toml`, `ruff.toml`, `pyrightconfig.json`, `tox.ini`, and so on) with what the standards require. List each difference.
2. **Tools second.** With the standards-compliant config in place (applied temporarily under `--dry-run`), run the checkers (Ruff, Pyright, Interrogate, tox environments as applicable) and collect what they find.
3. **Judgement third.** Review the code against the judgement rules:
   - Check the new or changed rules thoroughly, across the whole code base.
   - For unchanged rules, do a lighter drift pass. Flag clear violations rather than re-litigating style.
   - In a large repo, split this review across subagents by package or top-level module. Give each one the rule list and ask for its findings only, not edits.
4. Write up the findings, grouped by rule: file and line, what's wrong, and the proposed fix.

If `--dry-run` was given: reset the submodule to `$OLD` (`git submodule update $STD`), discard any temporary config edits, show the report, and stop here.

## 5. Decide what to change

Sort the fixes into two groups:

- **Safe to apply**: mechanical or local changes that don't alter behaviour or the public API (formatting, lint autofixes, type annotations, docstrings, small refactors within one function).
- **Needs approval**: anything sweeping or behaviour-affecting, such as raising the minimum Python version, changing dependency tooling (e.g. pip to uv), renaming or moving modules, changing public APIs or data models, deleting code, or touching more than about 20 files for a single rule.

Show the user the "Needs approval" list in one message, and apply only the items they approve. Go ahead with the safe group without asking.

## 6. Apply

Commit in this order. Keep each commit small enough to review.

1. **Submodule bump on its own:** `chore(standards): update dev-standards to <short NEW sha>`. List the standards commits in the body.
2. **Config changes:** `chore(standards): align tool config with <rule IDs>`.
3. **Code changes, one commit per rule** (or per closely related group of rules): `refactor(standards): <rule ID> <short description>`.

While applying:

- Run the tool autofixers before editing by hand (e.g. `ruff check --fix`, `ruff format`).
- Keep the code readable. A standards fix must not make the code harder to follow. If complying with a rule would do that, don't force it: flag it in the report.
- Don't change behaviour. If a fix needs a behaviour change, it belongs in "Needs approval".
- Never add suppressions (`# noqa`, `# type: ignore`, `# pyright: ignore`) to get a check to pass, unless the standards allow it for that case. If you add one, give the reason inline.

## 7. Verify

1. Re-run every checker. Each one must pass, or report no more than the baseline.
2. Re-run the test suite. No test that passed at the baseline may now fail. If one does, fix the cause, or revert the commit responsible and report it.
3. Check `git status` is clean, and that `git rev-parse HEAD:$STD` matches `NEW`.

## 8. Report

End with a concise report:

- Standards updated: `OLD` → `NEW`, with the standards commits in between.
- **New or changed rules:** for each one, what was found, what was fixed, and what is still open.
- **Drift fixed:** violations of unchanged rules that were corrected.
- **Deferred:** "Needs approval" items the user declined or hasn't answered, and any rule that couldn't be met cleanly, with the reason.
- Checker and test results before and after.
- The branch name and commit list.

Locally, do not push, open a PR or merge unless the user asks. In a cloud session, push the working branch (never the default branch) so the work isn't lost, but don't open a PR or merge unless asked.
