# INT-US-03 SF-02 — Lint-Fix Reflection Loop Integration

**Status**: APPROVED — approved by Steve Bula on 2026-07-18. Audit Q1–Q5 all resolved to option
**(a)**. Implemented 2026-07-18. · **FRs owned**: FR-2 · **Depends on**: SF-01 (committed) · Design:
[INT-US-03_design.md](INT-US-03_design.md) §Sub-features → SF-02

## Goal

Append the `lint_fix` step (`LINT_FIX`/`CODE`, `ruff` auto-fix + LLM reflection loop) to the
`implement_spec` pipeline SF-01 established, and extend the inline report with
`{reflections_used, lint_errors_remaining, auto_fixed}`. Inputs: the SF-01 pipeline, the generated
`src/<stem>.py`, `RunContext.llm` + `config`. Host mode — worktree isolation is SF-03;
Podman is out of scope for the whole feature.

## Where it plugs in

| Fact | Where |
|---|---|
| `LintFixHandler`, key `lint_fix+code`, in `VALID_STEP_COMBINATIONS` | `core/flow/handlers/lint_fix.py:23` |
| `execute` reads `target = step.params.get("target", "src/")` and `max_reflections = step.params.get("max_reflections", 3)`; `target` in scope at line 41 | `lint_fix.py:37` |
| **Phase 1 (cheap):** `run_linter` on `target`; clean → PASS; else `ruff --fix`, re-lint; now clean → PASS `{reflections_used:0, lint_errors_remaining:0, auto_fixed:True}`. Works with just a file path — no `output_dir` needed | `lint_fix.py:103-114` |
| **Phase 2 (LLM reflection):** up to `max_reflections` cycles; LLM rewrites the code file, re-lint. Clean → PASS; exhausted → **FAIL** `{reflections_used, lint_errors_remaining}`. No LLM → FAIL; LLM error → ERROR | `lint_fix.py:116-209` |
| Phase 2 finds the file via `_find_code_files(context)` → `context.output_dir.glob("*.py")` | `lint_fix.py:218-222` |
| Current pipeline: `generate_code → generate_tests → run_tests` (loop-back → `generate_code`, `max_retries=2`) `→ validate_code` (`CONTINUE`) | `cli.py:_build_implement_pipeline` |
| Per-step report branches | `_report_implementation` (`cli.py:90`) |
| Existing handler tests cover clean/auto-fix/reflection/exhausted/no-llm/zero-reflections/llm-error/no-code-files/stale-nodes/uuid/db-logging; `test_no_code_files_found` pins the output_dir-empty path | `tests/unit/core/flow/handlers/test_lint_fix_handler.py` |

**The gap (mirror of SF-01 Q1):** the implement `RunContext` leaves `output_dir` unset (NFR-2), so
when ruff can't fully auto-fix and Phase 2 engages, `_find_code_files` returns `[]` → FAIL "No code
files found to fix". Fix: `_find_code_files` honors the explicit `target` (the generated
`src/<stem>.py`), as SF-01 did for `ValidateCodeHandler._find_code_path`. Without a `target` it must
keep today's behavior.

**Isolation:** per `pipeline_engine_guide.md §7`, `lint_fix` (static ruff) is **project-root-bound**
even under US-9 isolation, so placement/targeting is isolation-agnostic; SF-03 needs no lint change.

External: none new (`ruff` already invoked by the QA runner). No `pyproject.toml` change.

## Changes

1. **Insert `lint_fix`** (FR-2) · `cli.py` — in `_build_implement_pipeline`:
   - `params = {"target": f"src/{stem}.py", "max_reflections": 3}`
   - `gate = GateDefinition(on_fail=OnFailAction.CONTINUE)` (report-only)
   - **Immediately before `run_tests`** (Q2): `generate_code → generate_tests → lint_fix → run_tests →
     validate_code`, so tests + C01–C08 validate the lint-fixed code.
2. **`_find_code_files` honors an explicit target** (FR-2) · `lint_fix.py` —
   `LintFixHandler._find_code_files(context, target=None)`: if `target` resolves (against
   `project_path`) to an existing file inside the project → `[that_file]`; else the existing
   `output_dir.glob("*.py")`. The single caller in `execute` passes `target`. Traversal-guarded like
   SF-01.
3. **Report lint outcome** (extends FR-7) · `cli.py` — a `name == "lint_fix"` branch in
   `_report_implementation`: `auto_fixed` / `reflections_used` / `lint_errors_remaining` (green when
   0 remain; yellow when some remain — report-only).

| File | Change | FR |
|------|--------|-----|
| `src/specweaver/workflows/implementation/interfaces/cli.py` | insert `lint_fix` step; add report branch | FR-2 |
| `src/specweaver/core/flow/handlers/lint_fix.py` | `_find_code_files` honors `target` | FR-2 |
| `tests/unit/workflows/implementation/test_implement_pipeline.py` | assert lint_fix step/gate/params/position | FR-2 |
| `tests/unit/workflows/implementation/test_implement_reporting.py` | lint_fix report branch | FR-2 |
| `tests/unit/core/flow/handlers/test_lint_fix_handler.py` | `_find_code_files` target-honoring cases | FR-2 |
| `tests/integration/interfaces/cli/test_cli_implement.py` | lint_fix stubbed in the loop (report + report-only) | FR-2 |

No new files/modules/migrations/YAML.

## Tests

| Tier | Bucket | Case |
|---|---|---|
| Unit — pipeline | Happy | `[generate_code, generate_tests, lint_fix, run_tests, validate_code]`; params `target=src/<stem>.py`, `max_reflections=3`; gate `CONTINUE` |
| | Boundary | lint_fix precedes run_tests |
| Unit — `_find_code_files` | Happy | `target` file exists → `[file]` |
| | Boundary | no target → output_dir glob unchanged (`test_no_code_files_found` still holds) |
| | Hostile | `../` traversal target → not resolved outside project → falls back/empty |
| Unit — reporting | Happy | auto_fixed clean → "lint: auto-fixed, 0 remaining" |
| | Boundary | reflections used, some remaining → yellow report |
| | Hostile | malformed/empty lint output → defaults, no crash |
| Integration — CLI, lint_fix stubbed | Happy | lint passes → reported, exit 0 |
| | Degradation | lint_fix FAILED (errors remain) → report-only, exit 0 (gate CONTINUE); tests still gate the exit |

## Decisions (audit)

| # | Question | Options | Proposal | Severity |
|---|----------|---------|----------|----------|
| Q1 | Phase-2 LLM reflection can't find the generated file without a handler change. Approve the `_find_code_files` target-honoring enhancement in `core/flow/handlers/lint_fix.py` (outside `workflows/implementation`, mirrors approved SF-01 Q1)? | (a) enhance handler [rec]; (b) set `output_dir` (breaks src/tests split — rejected in SF-01); (c) accept Phase-2 always fails when output_dir unset. | **(a)** — smallest correct fix; precedent set by SF-01; backward-compatible. | **HIGH** |
| Q2 | Where does `lint_fix` go? | (a) **before `run_tests`** [rec] — tests + C01–C08 validate the lint-fixed code; a lint rewrite that breaks behavior is caught by run_tests. (b) **last, after `validate_code`** — matches the contract's textual order and runs lint_fix once (cheaper), but tests/validation then ran on un-fixed code and a final LLM rewrite could silently break passing tests. | **(a)** — correctness (validate the final artifact) outweighs the bounded extra cost. | **HIGH** |
| Q3 | `lint_fix` gate. | (a) `CONTINUE` report-only [rec]; (b) `ABORT` on remaining errors. | **(a)** — remaining lint shouldn't kill an otherwise-working autonomous run; required anyway if lint_fix precedes run_tests (else tests never run). Consistent with `validate_code`. | MEDIUM |
| Q4 | Cost: with Q2(a), `lint_fix` re-runs on each `run_tests` loop-back (≤2), so up to 3 executions incl. LLM reflection. Acceptable? | (a) accept (bounded by `max_retries=2` × `max_reflections=3`) [rec]; (b) move lint_fix after the loop (Q2 b). | **(a)** — ruff Phase-1 is cheap and resolves most; LLM reflection is the rare tail; NFR-5 bounds it. | MEDIUM |
| Q5 | `max_reflections` value. | (a) handler default 3 [rec]; (b) configurable. | **(a)** — bounded, no new surface. | LOW |

Architecture check: `cli.py` — Pydantic step build, imports already present
(`GateDefinition`/`OnFailAction`), `orchestrator` archetype OK. `lint_fix.py` — pure `Path`
resolution (mirror of SF-01's `_find_code_path`), no new import, no I/O class; `lint_fix` stays
static/root-bound. Reuses `LintFixHandler`/atom; extends the finder, no parallel one. 2 modules
(`workflows/implementation`, `core/flow/handlers`) — the integration seam, same shape as SF-01. No
new cross-module edge; **tach** stays green. No CRITICAL violation.

## As built (2026-07-18)

`cli.py` (`lint_fix` before `run_tests`; `_report_implementation` lint branch) and
`core/flow/handlers/lint_fix.py` (`_find_code_files` honors an explicit, traversal-guarded `target`;
caller updated).

- The `lint_fix` `CONTINUE` gate absorbs BOTH `FAILED` (errors remain after reflections) and `ERROR`
  (LLM crash mid-reflection); the run advances to `run_tests`, which governs the exit code.
  Integration-tested.
- Unlike SF-01's `_find_code_path`, a *missing* explicit file target falls back to the `output_dir`
  glob (lint is happy to lint available files) rather than returning empty — intentional, tested.
- `implement` sets no `output_dir` (NFR-2); lint stays project-root-bound (isolation-agnostic).

Tests and results: [walkthrough](INT-US-03_sf02_walkthrough.md).
