# Walkthrough: TECH-087 SF-03 — Dead code goes, TypeScript timeouts say what timed out

Plan: [TECH-087_sf03_implementation_plan.md](TECH-087_sf03_implementation_plan.md).

## CB-1 — the live JUnit reader warns; the dead QA code goes (FR-10, FR-11)

### What changed

- `sandbox/language/core/junit_reports.py`: `harvest_junit` logs an unreadable report at WARNING,
  "<file> is unreadable, so its tests are not counted: <reason>" (was DEBUG).
- Deleted, with their tests: `java/runner.py _harvest_junit`, `KotlinRunner._parse_junit_results`,
  `rust/runner.py _tally_junit`, `workspace/ast/parsers/rust/parsers.py`
  (`test_rust_parsers.py`), `sandbox/rule_atom.py` (`test_rule_atom.py`).
- `tach.toml`: the `rule_atom` and `rust.parsers` exposes go (the second one the plan missed), and
  the `specweaver.sandbox → specweaver.assurance.validation` edge goes with its last import;
  `sandbox/context.yaml` drops the matching `consumes` line.
- Guides: the single-operation atom example is `BashActionAtom`; the stale `loom/atoms/rule_atom.py`
  row in `developer_guide.html` is gone.

### Red first

- `test_lost_results_warn.py`: the two dead-copy tests became three on `harvest_junit` (unreadable
  alone; a good report beside an unreadable one; a folder named `TEST-dir.xml`). All three failed:
  DEBUG only.
- `tests/unit/sandbox/test_dead_qa_code_is_gone.py`: 5 cases, all failed before the delete. Each
  imports the parent first, so a wrong path fails.

### Proof

Mutant `junit-unreadable-silent` (WARNING back to DEBUG) killed. Corpus: FR-1..FR-8, FR-10 all
killed; 0 stale mutants. `tach check` green.

### Red/Blue (Phase 7.5), 2 cycles

- R1 (MEDIUM) the new warning dropped the reason the dead copies gave. Fixed: the parse error is
  appended.
- R2 (LOW) a non-JUnit XML in a report folder (TestNG's `testng-results.xml` in
  `surefire-reports`) now warns. Accepted: Maven/JUnit and Gradle write only `TEST-*.xml` there,
  and such a file was never counted; the warning names it.
- R3 (LOW) one line per broken file on a large broken set. Accepted, as the plan says.
- Cycle 2: no new finding.

## CB-2 — TypeScript timeouts name the tool (FR-15)

### What changed

- `toolchain.timed_out(result, tool, seconds=None)`: with `seconds`, the reason is "<tool> timed out
  after N s".
- `typescript/runner.py`: `run_compiler` and `run_architecture_check` check the timeout before
  `did_not_run` and return the shared `failed_compile` / `failed_architecture`: "tsc timed out after
  120 s", "ESLint timed out after 60 s" (was "Timeout during compilation" / "Jest timed out", or
  "did not run" when the output was empty). The two dead `except getattr(__builtins__, …)` branches
  are gone; the timeouts are module constants.

### Red first

- `test_typescript_runner.py`: tsc and ESLint timeouts, each with empty and with partial output; 4
  failed before. A debugger timeout (widened at the gate `[agreed 2026-10-30]`) names the
  program and the limit; 2 failed before. The Python debugger timeout the same (widened again
  `[agreed 2026-10-30]`); 1 failed before, and `test_python_debug_timeout.py` (integration, new)
  runs a real hanging program through the atom. The missing-tsc test and the debugger missing-binary test now use what the real
  executor returns (exit -1, the OSError in stderr) instead of a raise it never does.
- `test_typescript_timeouts.py` (integration, new): the real atom, runner and executor with a fake
  `npx` (and `node`) that hangs; written after the change (the CB gate found the folder had only `live` tests).
  Its red is shown by mutants: the old check order and the old ESLint branch each turn it red.
- `test_typescript_atom.py` (live): its escape keyed on a message that no code gives any more; it
  now keys on the not-run code.

### Proof

Mutants `ts-arch-timeout-says-jest`, `ts-timeout-after-did-not-run`, `ts-debug-timeout-unnamed` and
`py-debug-timeout-unnamed` killed. Corpus: every
TECH-087 mutant killed; 0 stale.

### Red/Blue (Phase 7.5), 2 cycles

- R1 (MEDIUM) the debugger timeout said "Timeout expired". Fixed: the user widened FR-15
  `[agreed 2026-10-30]`; it now says "<entrypoint> timed out after 300 s", in the TypeScript and the Python runner.
  No "Timeout expired" is left in `src`.
- R2 (LOW) the seam test needs `/bin/sh` and `sleep`. Accepted: the suite's git-hook tests need the
  same.
- R3 (LOW) the did-not-run text says "the TypeScript architecture checker", the timeout "ESLint".
  Accepted: no output change beyond FR-15's messages.
- Cycle 2: no new finding.
