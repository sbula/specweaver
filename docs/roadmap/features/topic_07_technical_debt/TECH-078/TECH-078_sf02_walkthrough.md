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
