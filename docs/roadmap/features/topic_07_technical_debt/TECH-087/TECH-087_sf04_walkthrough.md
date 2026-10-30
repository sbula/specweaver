# Walkthrough: TECH-087 SF-04 — Runners beside their factory, one JVM base

Plan: [TECH-087_sf04_implementation_plan.md](TECH-087_sf04_implementation_plan.md).

## CB-1 — the factory moves; the atom takes a runner (FR-12)

### What changed

- `sandbox/qa_runner/core/factory.py` → `sandbox/language/core/runner_factory.py`. `resolve_runner`
  is unchanged. New `qa_atom(cwd, language, sandbox_settings, scenarios_root)` picks the executor
  (host, container, or container with the scenario store), resolves the runner and returns the atom.
  The container-executor choice moved here from the atom unchanged.
- `QARunnerAtom(cwd, runner, *, scenarios_mounted=False)`: it no longer builds anything.
- `create_qa_runner_interface(role, atom)` takes the atom (it had no `src` caller).
- The lint-fix, validate-tests and code-validation handlers call `qa_atom`. `tach.toml` exposes it.
- `docs/dev_guides/language_support_guide.md` § Selection names the new home and the guard.
- Kind changed from the planned `refactor` to `bugfix`: the new constructor made 14 test files
  change, which the refactor gate refuses; the commit fixes SB-1's two-way imports.

### Red first

- `tests/unit/sandbox/qa_runner/test_qa_runner_imports_no_language.py`: red on the factory's six
  imports; its own cases show a function-level, a `TYPE_CHECKING` and a `from … import language`
  import all count, and a string mention does not.
- `tests/unit/sandbox/language/core/test_runner_factory.py` (moved from `qa_runner/core/qa_runner/`)
  `TestQaAtom`: the named language reaches the runner; a scenario store wins over host settings; the
  scenario scratch goes with the atom, and goes when no runner can be built (red before the fix
  below).
- Tests that built `QARunnerAtom(cwd=…)` or patched `…atom.QARunnerAtom`, `…atom._resolve_runner`
  or `…qa_runner.core.factory.resolve_runner` now use `qa_atom` and its module. The facade tests
  pass their mock atom directly.

### Proof

- Moved and re-pinned: `D-INTL-08` `named-language-ignored`, `container-runs-silently`,
  `atom-drops-the-language`, `lint-ignores-the-language`; `B-FLOW-01` `scenario-mount-on-coder`,
  `c03-c04-on-host`, `lint-on-host`. Corpora `D-INTL-08` 55/55, `B-FLOW-01` 69/69, `TECH-075` 30/30.
- Found by that run, already surviving on `d55f2fa0`: `D-INTL-08` FR-7 `note-not-shown` (since
  `TECH-078` gave every language its test rules, no journey prints the code-validation note). Fixed:
  `test_implementation_cli.py::TestCodeValidationLine` kills it; the campaign scope names it.
- Probes: scratch cleanup removed → `test_the_scenario_scratch_goes_with_the_atom` red; the
  failure cleanup removed → `test_the_scenario_scratch_goes_when_no_runner_is_built` red.

### Red/Blue (Phase 7.5), 2 cycles

- R1 (MEDIUM) the scratch folder leaked when `resolve_runner` raised: the cleanup was registered
  only once the atom existed. Fixed: `qa_atom` removes it on any failure, test first.
- R2 (LOW) `QARunnerAtom`'s constructor changed; an outside caller would break. Accepted: no
  entry point or guide names it; `qa_atom` is the documented way.
- R3 (LOW) `create_qa_runner_interface` changed its parameters. Accepted: no `src` caller.
- Cycle 2: no new finding (the guard runs on every file, so a new lazy import fails at once).
