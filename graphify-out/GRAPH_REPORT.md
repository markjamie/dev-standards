# Graph Report - dev-standards  (2026-11-28)

## Corpus Check
- 34 files · ~16,881 words
- Verdict: corpus is large enough that graph structure adds value.
- Unclassified: 8 file(s) not represented in the graph (top: .toml 5, (none) 2, .lock 1)

## Summary
- 581 nodes · 1317 edges · 30 communities (26 shown, 4 thin omitted)
- Extraction: 98% EXTRACTED · 2% INFERRED · 0% AMBIGUOUS · INFERRED: 30 edges (avg confidence: 0.88)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `48abcf08`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- test_cli.py
- test_ci.py
- test_apply.py
- tomllib
- Process and tooling
- gaps
- checks.py
- toml_value
- on
- on
- toml_text.py
- read_text
- test_ruff_config.py
- split_sections
- gitignore.py
- test_toml_text.py
- layout.py
- add_lines
- apply.py
- test_templates.py
- join_sections
- hooks
- /dev-standards-comply
- module_name
- check_template_files
- load_shared
- Changelog
- AGENTS.md
- dev-standards

## God Nodes (most connected - your core abstractions)
1. `BootstrapError` - 26 edges
2. `lookup()` - 26 edges
3. `apply_templates()` - 23 edges
4. `gaps()` - 23 edges
5. `read_text()` - 21 edges
6. `split_sections()` - 21 edges
7. `RepoState` - 18 edges
8. `render_workflow()` - 18 edges
9. `merge_dependency_groups()` - 15 edges
10. `load_state()` - 15 edges

## Surprising Connections (you probably didn't know these)
- `TestUpdatePyproject` --uses--> `BootstrapError`  [INFERRED]
  tests/test_apply.py → devstandards/errors.py
- `test_anything_outside_the_patterns_is_refused()` --uses--> `BootstrapError`  [INFERRED]
  tests/test_ci.py → devstandards/errors.py
- `test_read_pyproject_reports_invalid_toml()` --uses--> `BootstrapError`  [INFERRED]
  tests/test_layout.py → devstandards/errors.py
- `conforming()` --calls--> `apply_templates()`  [EXTRACTED]
  tests/test_checks.py → devstandards/apply.py
- `test_setuptools_repo_after_bootstrap()` --calls--> `apply_templates()`  [EXTRACTED]
  tests/test_checks.py → devstandards/apply.py

## Import Cycles
- None detected.

## Communities (30 total, 4 thin omitted)

### Community 0 - "test_cli.py"
Cohesion: 0.06
Nodes (20): discover_repo(), install_environment(), main(), Options, parse_args(), report(), run(), BootstrapError (+12 more)

### Community 1 - "test_ci.py"
Cohesion: 0.08
Nodes (24): load_state(), run_checks(), _apt(), ci_config(), _env(), _invalid(), _playwright(), render_workflow() (+16 more)

### Community 2 - "test_apply.py"
Cohesion: 0.11
Nodes (13): apply_templates(), copy_template(), drop_pyright_venv(), drop_redundant_ruff_settings(), ensure_import(), pin_minor_versions(), update_pyproject(), render_template() (+5 more)

### Community 3 - "tomllib"
Cohesion: 0.10
Nodes (19): merge_dependency_groups(), check_dependency_groups(), group_entries(), Groups, merge(), normalise(), render(), _requirements_by_name() (+11 more)

### Community 4 - "Process and tooling"
Cohesion: 0.06
Nodes (30): Adopt in a repo, dev-standards, Develop dev-standards, Existing repos, Update a repo, Why these choices, Code, Definition of done (+22 more)

### Community 5 - "gaps"
Cohesion: 0.19
Nodes (12): append(), conforming(), edit(), gaps(), test_conforming_repo_has_no_gaps(), test_pyproject_gaps(), test_settings_above_the_minimum_pass(), test_setuptools_repo_after_bootstrap() (+4 more)

### Community 6 - "checks.py"
Cohesion: 0.11
Nodes (10): Check, check_agent_files(), check_enforced_settings(), check_gitignore(), check_pyproject_tables(), check_pyright_venv(), check_python_version_file(), check_seeded_files() (+2 more)

### Community 7 - "toml_value"
Cohesion: 0.12
Nodes (7): _add_per_file_ignores(), configure_ruff(), toml_key(), toml_value(), TestConfigureRuff, TestLookup, TestWriting

### Community 8 - "on"
Cohesion: 0.09
Nodes (22): TOX_SKIP_ENV, jobs, tox, name, on, pull_request, push, schedule (+14 more)

### Community 9 - "on"
Cohesion: 0.09
Nodes (21): TOX_SKIP_ENV, jobs, tox, name, on, pull_request, push, schedule (+13 more)

### Community 10 - "toml_text.py"
Cohesion: 0.14
Nodes (9): _code_part(), _has_keys(), _insert(), _is_trivia(), _key_lines(), _section_start(), _table_name(), _value_end() (+1 more)

### Community 11 - "read_text"
Cohesion: 0.17
Nodes (10): minor_version(), package_name(), read_pyproject(), read_text(), test_minor_version(), test_module_name(), test_package_name_falls_back_to_directory(), test_package_name_prefers_project_name() (+2 more)

### Community 12 - "test_ruff_config.py"
Cohesion: 0.18
Nodes (8): Redundancy, redundant_settings(), repo_wide_ignores(), settings(), test_describes_whole_settings_and_entries(), test_finds_settings_the_shared_config_provides(), test_keeps_local_overrides(), test_repo_wide_ignores_skip_the_shared_ones_and_repeats()

### Community 13 - "split_sections"
Cohesion: 0.18
Nodes (5): add_missing_tables(), split_sections(), table_names(), TestAddMissingTables, TestSplitSections

### Community 14 - "gitignore.py"
Cohesion: 0.25
Nodes (8): merge(), missing_entries(), _patterns(), template_patterns(), test_merge_appends_only_missing_patterns(), test_merge_creates_file_when_absent(), test_merge_leaves_complete_file_alone(), test_missing_entries_treats_trailing_slash_as_equal()

### Community 15 - "test_toml_text.py"
Cohesion: 0.20
Nodes (4): remove_array_items(), remove_key(), section_text(), TestKeyEdits

### Community 16 - "layout.py"
Cohesion: 0.20
Nodes (4): check_ruff(), lookup(), lookup_list(), lookup_table()

### Community 17 - "add_lines"
Cohesion: 0.20
Nodes (4): add_lines(), append_table(), replace_table(), TestEditing

### Community 18 - "apply.py"
Cohesion: 0.19
Nodes (4): Transform, use_hatchling(), remove_tables(), TestUseHatchling

### Community 19 - "test_templates.py"
Cohesion: 0.25
Nodes (10): minimum(), test_minimum_does_not_install_from_the_lock(), test_minimum_installs_nothing_before_its_own_resolution(), test_minimum_resolves_package_and_tests_in_one_step(), test_minimum_runs_by_default(), test_minimum_uses_the_oldest_supported_python(), test_no_env_replaces_the_coverage_setting(), test_other_test_envs_use_the_lock() (+2 more)

### Community 20 - "join_sections"
Cohesion: 0.22
Nodes (5): _edit_section(), join_sections(), rename_key(), _replace_keeping_spacing(), Section

### Community 21 - "hooks"
Cohesion: 0.18
Nodes (10): entry, id, language, name, pass_filenames, types, types_or, repos (+2 more)

### Community 22 - "/dev-standards-comply"
Cohesion: 0.20
Nodes (9): 1. Preflight, 2. Update the submodule and find the delta, 3. Classify the standards, 4. Audit, 5. Decide what to change, 6. Apply, 7. Verify, 8. Report (+1 more)

### Community 23 - "module_name"
Cohesion: 0.29
Nodes (4): check_build(), module_name(), render(), test_render_fills_every_placeholder()

### Community 24 - "check_template_files"
Cohesion: 0.29
Nodes (3): check_template_files(), tox_departures(), _tox_gaps()

### Community 25 - "load_shared"
Cohesion: 0.33
Nodes (3): check_ruff_ignores(), check_ruff_redundancy(), load_shared()

## Knowledge Gaps
- **1 isolated node(s):** `dev-standards`
  These have ≤1 connection - possible missing edges or undocumented components. (Counts symbols only; 208 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **4 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `BootstrapError` connect `test_cli.py` to `test_ci.py`, `test_apply.py`, `read_text`, `layout.py`, `apply.py`?**
  _High betweenness centrality (0.046) - this node is a cross-community bridge._
- **Are the 5 inferred relationships involving `BootstrapError` (e.g. with `main()` and `TestUpdatePyproject`) actually correct?**
  _`BootstrapError` has 5 INFERRED edges - model-reasoned connections that need verification._
- **What connects `dev-standards` to the rest of the system?**
  _1 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `test_cli.py` be split into smaller, more focused modules?**
  _Cohesion score 0.05506329113924051 - nodes in this community are weakly interconnected._
- **Why does `apply_templates()` connect `test_apply.py` to `test_cli.py`, `test_ci.py`, `gaps`, `read_text`, `gitignore.py`, `apply.py`?**
  _High betweenness centrality (0.034) - this node is a cross-community bridge._
- **Should `test_ci.py` be split into smaller, more focused modules?**
  _Cohesion score 0.08484848484848485 - nodes in this community are weakly interconnected._
- **Why does `lookup()` connect `layout.py` to `test_ci.py`, `test_apply.py`, `checks.py`, `toml_value`, `toml_text.py`, `read_text`, `test_ruff_config.py`, `split_sections`, `test_toml_text.py`, `apply.py`, `module_name`?**
  _High betweenness centrality (0.031) - this node is a cross-community bridge._