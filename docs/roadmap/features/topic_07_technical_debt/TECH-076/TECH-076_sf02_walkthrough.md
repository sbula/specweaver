# Walkthrough: TECH-076 SF-02 — Every door stops on a broken setting

- **Design**: [TECH-076_design.md](TECH-076_design.md)
- **Plan**: [TECH-076_sf02_implementation_plan.md](TECH-076_sf02_implementation_plan.md)

## CB-1 — FR-5 (CLI commands) and FR-4 (the CLI run root)

### What changed

- `interfaces/cli/_core.py`: `load_project_settings(db, project)` — `load_settings`, and on a
  `SettingsFileError` the existing refusal (`Error: <file>:<line>: <key>: <message>`, exit 1).
- `sw implement`, `sw draft`, `sw review`, `sw standards scan`, `sw drift check --analyze` and the
  run's model wiring call it instead of `load_settings`.
- `_apply_isolation_policy` (`sw run`, `sw resume`) calls it too; the refusal (`typer.Exit`) passes
  through, and any other lookup failure keeps its best effort (design decision 5).
- `tach.toml`: five interface modules no longer import `core.config.bootstrap`; their unused edges
  are removed (tach reports unused edges as errors).
- Coupling: `core/flow/interfaces/cli.py` imported 25 module names before this boundary (fan-out
  above 20, inherited). The topology attach moved to `core/flow/interfaces/run_topology.py`
  (`attach_topology`), which takes `assurance.graph.loader` and `commons.spec_names` with it.

### Red first

- e2e `test_broken_sandbox_stops_the_run_e2e.py`: with `execution_mod`, the run started, executed
  `validate_spec` and recorded a run; the located message never appeared.
- `test_cli_broken_settings_refuse.py`: all six cases ended in an uncaught `SettingsFileError`
  (empty output). `drift check` first failed on a missing `--plan`, a test mistake, fixed before
  judging the red.

### Combined analysis

| Function | Unit | Integration | E2E |
|---|---|---|---|
| `_core.load_project_settings` | — | ✅ five commands + DAL file | — |
| `_apply_isolation_policy` | ✅ loads, other failure best-effort, settings error exits | — | ✅ broken refused, valid runs |
| `attach_topology` | ✅ slice selected, no topology unchanged | — | ✅ existing run e2e |

Composition: the e2e drives `sw init` → `specweaver.toml` → `sw run` through the real loader.
Mutants (OBJECTED, pinned): FR-5 `cli-settings-error-escapes`; FR-4 `cli-run-isolation-off`
(re-pointed after the run root moved to the helper).

### Gates

- Full suite 11408 passed, 9 skipped. `quality.py sf` 18/18 after: tach unused edges (removed),
  coupling (the extraction above), duplication.
- **Duplication baseline re-frozen** (`scripts/baselines/duplication.json`): the report showed the
  same two old clone pairs (the "resolve the project or exit" preamble in `drift check`, `review`
  and `implement`) under new keys, because one import line inside them was deleted; the baseline's
  other line numbers had drifted too. Extracting the preamble into `_core` would add an
  `interfaces.cli → workspace.project` edge, which this design's NFR-4 rules out. Accepted risk;
  the clone count is unchanged (103).

### Red/Blue (code)

- R1 (MEDIUM) `typer.Exit` is a `RuntimeError`; the run root's `except Exception` would swallow the
  refusal. Fixed: `except typer.Exit: raise` first; the mutant removing it is killed by the e2e.
- R2 (LOW) `_wire_models` now refuses a broken file too, but the isolation step before it always
  refuses first. Kept for one rule on every door.
- Cycle 2: no new finding.
