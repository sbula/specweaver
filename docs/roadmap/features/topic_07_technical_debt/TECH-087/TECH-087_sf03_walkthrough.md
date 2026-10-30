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
