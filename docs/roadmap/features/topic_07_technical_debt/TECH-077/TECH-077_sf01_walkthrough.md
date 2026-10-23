# Walkthrough: TECH-077 SF-01 — One answer per lookup

- **Design**: [TECH-077_design.md](TECH-077_design.md)
- **Plan**: [TECH-077_sf01_implementation_plan.md](TECH-077_sf01_implementation_plan.md)

## CB-1 — FR-10 (one lookup per project question)

### What changed

- `workspace/store.py`: `_project_row_at(db, root)` is the one "project registered at this folder"
  query (paths compared resolved); `default_dal_at`, `project_name_at`, `domain_profile_at` read
  it. New `project_root_of(db, name)` (exact name match).
- `interfaces/cli/_core.py`: `registered_project_at` and `project_root` call the store (one DB
  style, decision 2); new `existing_project_root_or_exit(name)` replaces the two identical
  "not found / folder gone" blocks in `sw standards scan` and the project CLI. `sw use` keeps its own
  message over the same lookup.
- `interfaces/api/v1/paths.py` `resolve_project_root` and `settings_loader.load_settings_async`
  call `project_root_of` through `asyncio.to_thread` (each `db.connect()` opens its own connection).
- New `core/flow/engine/registered.py`: `registered(context, read, what)`; `registered_name`,
  `scenario_store`, `target_dal` and `_profile_of` use it, each keeping its own fallback.
- New `commons/limits.py`: `DEFAULT_MAX_CONSTITUTION_SIZE`; the loader, `constitution.py` and the
  store column default use it (decision 3).
- B-FLOW-07 mutants `default-dal-by-name` and `no-default-dal-fallback` re-pointed (OBJECTED,
  pinned); drifted mutants: 0.

### Red first

- `test_one_project_lookup.py`: import error (`project_root_of` absent). Its agreement test passed
  before the callers moved (they agreed through different code); it now guards the one path.
- `test_registered.py`, `test_limits.py`: import errors (no modules).
- `test_cli_standards.py::test_scan_nonexistent_root` mocked the repository the CLI no longer uses;
  it now registers a real folder and renames it away (nothing deleted).

### Combined analysis

| Function | Unit | Integration |
|---|---|---|
| `_project_row_at` and its three readers | — | ✅ found, two spellings, none |
| `project_root_of` | — | ✅ found, unknown, prefix name |
| `_core` helpers, API lookup | ✅ unregistered exits; existing returned | ✅ agreement with the store |
| `registered` | ✅ read, nothing to read, failed read warns | ✅ flow handler tests |
| limit | ✅ one constant, no literal in the model | — |

Mutants (OBJECTED, pinned): `path-not-resolved`, `root-by-name-prefix`, `failed-read-escapes`.

### Gates

Full suite 11455 passed, 9 skipped. `quality.py sf` 18/18 after mypy flagged `constitution.py`
re-exporting the constant through the loader (now imported from `commons`). `tach check` clean.

### Red/Blue (code)

- R1 (LOW) the API and the async settings loader now run a sync query in a worker thread. Each call
  opens and closes its own SQLite connection; no shared state crosses threads.
- R2 (LOW) `registered` swallows every read error by design (each caller has a safe default), and
  logs it with the traceback.
- Cycle 2: no new finding.

## CB-2 — FR-6 (the archetype found one way)

### What changed

- `RunContext._read_archetype` asks `ArchetypeResolver(project_path).resolve(spec_path)`: the
  spec's nearest `context.yaml`, not only the root file. The resolver logs an unreadable file.
- `context_assembler.evaluate_and_fetch_skeleton_context` resolves each target file's archetype
  (relative paths taken inside the project) and builds one `CodeStructureAtom` per archetype. The
  topology's archetype no longer overrides a file's own `context.yaml`.

### Red first

`test_one_archetype.py`, written before the change: the run context answered the root's `generic`
for a spec under `service/` (`spring-boot`), and the skeleton step used the topology's `adapter`.

### Combined analysis

Agreement: the run context, `archetype_of` and the skeleton step answer `spring-boot` for one file.
Cases: no `context.yaml` (generic), an unreadable one (generic, WARNING), a topology claiming
another archetype, a relative file path. Mutants (OBJECTED, pinned): `run-reads-root-archetype`,
`skeleton-ignores-file-archetype`. Drifted mutants: 0.

### Gates

Full suite 11460 passed, 9 skipped. `quality.py sf` 18/18. `tach check` clean.

### Red/Blue (code)

- R1 (LOW) the skeleton step may now build several atoms (one per archetype among the files).
  Atoms are light; the count is the number of distinct archetypes, usually one.
- R2 (LOW) the run record's archetype changes for specs in a sub-folder with its own
  `context.yaml`. Intended (FR-6).
- Cycle 2: no new finding.

## CB-3 — FR-9 (rules stay inside the run's project)

### What changed

- New `assurance/validation/project_root.py`: `walk_up(start, stop)` yields the file's folder and
  each parent, never above `stop` (the filesystem root when no root is known).
- `execute_validation_flow` (`core/flow/handlers/validation_hydrator.py`), which every code-level
  run uses (the validation handler, the API `/check`, `sw check`), hands `project_root` to the rules.
- C02 searches each `tests/` from the file up to the root; C03 keeps its own question, the nearest
  `pyproject.toml` (the Python test runner's root), but only inside the project; C09 takes the
  run's root when given, else its old marker search (decision 1).
- The graph hasher's `.git` search places a `.gitignore` line at the git root — a different
  question; unchanged.

### Red first

`test_rules_share_the_root.py`, written before the change: C02 passed on a `tests/test_orders.py`
above the project root, and C09 judged the enclosing repository (its `specs/` FR-1 untraced) instead
of the run's project. `test_project_root.py`: import error.

A first walker had two checks that both stopped at the root, so the mutant removing one was SILENT
(equivalent). The redundant check is gone; the remaining one is mutated (OBJECTED).

### Combined analysis

| Function | Unit | Integration |
|---|---|---|
| `walk_up` | ✅ ends at stop, start at stop, no stop, nothing above, start outside | — |
| C02 / C03 / C09 through `execute_validation_flow` | — | ✅ above-root file ignored, inside found, no root as before, nearest package inside the project, C09 judges the run's project |

Mutants (OBJECTED, pinned): `walk-passes-the-root`, `root-not-handed-to-rules`,
`traceability-ignores-the-run-root`. Drifted mutants: 0.

### Gates

Full suite 11470 passed, 9 skipped. `quality.py sf` 18/18 after `ruff format`. `tach check` clean.

### Red/Blue (code)

- R1 (MEDIUM) `sw check` with no `--project` uses the working folder as the root, so a file's tests
  above the working folder are not found. Accepted: the working folder is the project there, as it
  already is for the DAL and the pipeline.
- R2 (LOW) spec-level validation does not pass the root; C02, C03 and C09 are code rules only.
- Cycle 2: no new finding.

## Decision at the SF-01 stop (user, 2026-10-23)

CB-3 accepted.
