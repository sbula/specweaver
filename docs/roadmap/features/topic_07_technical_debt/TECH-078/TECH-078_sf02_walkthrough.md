# Walkthrough: TECH-078 SF-02 — One way to find a step's files

Plan: [TECH-078_sf02_implementation_plan.md](TECH-078_sf02_implementation_plan.md).

## CB-1 — one code file lookup (FR-1, FR-2, NFR-3)

### What changed

- `qa_targets.step_file(step, context)`: the file a step works on. `params["target"]`, else the old
  spelling `target_path`; resolved inside the project (`resolve_inside`), refused when outside, a link
  out included, or not a file (`file_inside`), the message naming the target. Without a target, the
  task's code file (`task_code_file`: `task_files_for`, Python keeping `output_dir/<stem>.py`); None
  when it is not there yet.
- `review_code`, `validate_code` and `drift` call it; `lint_fix` fixes `target` when it names a file
  and the task's file otherwise (its linter still gets `target`). The three `*.py` globs and
  `_find_code_path` / `_find_code_files` are gone. `drift` still needs an explicit target.
- `sw review --spec`, `sw drift check` and the rot check send `target`.
- `generated_code` reads `task_code_file` (one copy of the Python fallback).

### Red first

`test_step_file.py`: collection error (no `step_file`). `test_step_files_java.py` (P-1): the real
`generate_code` writes `src/main/java/com/shop/Greeter.java`; review, validate and lint_fix then work
on it, not on the stray `out/aaa.py`. Its red is the mutant `first-py-in-output-dir` (the old glob),
which this test alone kills.

### Tests changed

- `test_validate_code_find_path.py` and `test_lint_fix_find_code_files.py` removed: they tested the
  two removed methods; every case (target, folder, missing, `..`, outside, empty) is in
  `test_step_file.py`.
- Tests that relied on the glob now name their spec after the file they write
  (`test_lint_fix_handler.py`, `test_handlers_edge_cases.py`, `test_flow_validation_integration.py`,
  `test_validation_evaluator_di.py`, `test_mcp_flow_e2e.py`); `test_build_base_prompt_profiles.py`
  patches `step_file`; `test_drift.py` expects "Missing 'target'".
- Mutants: FR-1 `first-py-in-output-dir`, `lint-fix-has-no-fallback`; FR-2 `old-spelling-dropped`,
  `drift-reads-old-name-only`; NFR-3 `outside-target-accepted`, `folder-target-accepted`. All
  killed. TECH-075 `outside-module-is-source` re-pinned (`generated_code` changed) and re-killed.

### Accepted risks

- `sw review --spec` and `sw drift check` on a file outside the project now fail, naming the file
  (NFR-3; the README says so).
- A spec with a bad `Package` line now fails `validate_code` and `review_code` with the spec line,
  as generation already did.

## CB-2 — one test file lookup (FR-3)

### What changed

- `assurance/validation/project_root.find_tests(code, stop)`: the code file's test file by its
  language's convention, or why there is none. From the file's folder up to the project root, the
  first `<folder>/<tests root>` holding the name wins; any depth, except Rust (`tests/<m>.rs` only).
  A language with no convention (Go, C, C++) answers "no test convention for go".
- C02, C03 and the C03 hydrator (for C03 and C04) call it. C02 and C03 skip a language with no
  convention. The three old searches (C02 walk-up, C03 nearest `pyproject.toml`, the hydrator's
  `<root>/tests`) are one.
- `commons.languages`: JavaScript has the TypeScript convention, `tests/<stem>.test.js`.
- `validate_code` with no archetype runs C02 and C03 on every language with a test convention; the
  other default rules stay Python's.
- **Bug found and fixed**: `validate_code` handed the rules the spec path, not the code file. C02
  looked for `test_<spec stem>.py`, C03 and C04 ran nothing, C05 read the spec, and a non-Python
  "2/2 rules passed" was two skips. The rules now get the code file.
- `project_root` and `find_tests` are exposed to `core/flow` (`context.yaml`, `tach.toml`); its file
  reading in a `pure-logic` module has a row in `known_boundary_violations.md` (decision 2).
- Docs: `language_support_guide.md` gains the five steps it missed (generator text, task files,
  detection, rename/move resolver, standards analyzer) and their checklist rows.

### Red first

`test_find_tests.py` (collection error), `test_c02_c03_languages.py` (7 red),
`test_validate_code_languages.py` (Kotlin judged by no rule), the JavaScript convention row (red).
`test_the_rules_judge_the_code_file_not_the_spec` is killed by `rules-get-the-spec`.
`test_c02_c03_languages_live.py` (P-2): real cargo, and real Maven with Kotlin (`toolchain` tier);
a failing Kotlin test fails C03, a passing one passes it.

### Tests changed

- `test_rules_share_the_root.py`: the C03 `pyproject.toml` search is gone; the test now proves the
  shared search stays inside the project.
- `test_code_validation_dal_strictness.py`: its one warning was C04 failing to parse coverage of the
  spec file. The widget's test now imports it (C03 and C04 really pass) and a `TODO` gives the one
  warning (C07).
- `test_implement_in_every_language_e2e.py`: C03 now runs the task's tests again, so the test log
  holds the tests file more than once; non-Python runs say "code validation: 2/2 rules passed".
- Java tests that expected "no code rules for java" now expect C02 naming `GreeterTest.java`.
- Mutants: eight FR-3 mutants, all killed. D-VAL-05 `missing-test-passes` re-pointed to `find_tests`;
  `c03-own-search` re-pointed (the hydrator's file and the own search are now one search, so the old
  mutant changed nothing) and its scope gains `test_c02_c03_languages.py`.

### C03 timings (2026-10-24, for the timeout decision)

| Project | First run | Again |
|---|---|---|
| Rust crate, one test | 0.3 s | 0.0 s |
| Kotlin on Maven, packages cached | 2.6 s | 2.4 s |

Not measured: Maven with an empty package cache (needs downloads). C03's limit is 60 s.

**Decided** `[agreed 2026-10-24]`: C03 keeps its 60-second limit; a run that passes it fails as "timed out".

### Accepted risks

- A Python `sw implement` run is slower: C03 and C04 now run the task's tests, which they claimed to
  do and did not.
- A `.tsx` file's test is looked up as `<stem>.test.ts` (generation writes `.ts`).
