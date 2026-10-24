# Walkthrough: TECH-078 SF-03 — The API's implement and the planner

Plan: [TECH-078_sf03_implementation_plan.md](TECH-078_sf03_implementation_plan.md).

## CB-1 — the planner names the language (FR-5)

### What changed

- `Planner(..., language=)`: required, the language's display name; the system prompt says "for a
  `<language>` project". No silent Python default.
- `PlanSpecHandler` passes `language_guide(task_files_for(...).language, project).name`; a bad
  `Package` line fails the step naming the spec line.

### Red first

`test_planner_language.py` (unexpected keyword `language`), `test_plan_names_the_language.py` (P-4:
a Rust and a TypeScript project's plan step were told "Python project").

### Tests changed

The 16 older `Planner(...)` calls in tests pass `language="Python"`. Mutants: FR-5
`planner-always-python`, `plan-step-says-python`, both killed. Re-pinned after running (their code
moved in this ticket): D-INTL-03 `planner-can-write`, `guess-a-plan`; B-INTL-01 `absolute-path`;
D-INTL-08 `header-package-ignored`, `python-rules-on-java`; TECH-077 `review-not-read-only`,
`check-rot-opens-worktree`, `drift-check-wrong-folder`; TECH-078 `kotlin-test-loses-Test`.

### Not fixed here

32 other corpus mutants are `STALE` in files this ticket did not touch; the morning mutation gate
reports them.
