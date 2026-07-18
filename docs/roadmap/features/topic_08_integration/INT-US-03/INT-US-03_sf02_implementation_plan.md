# Implementation Plan: Autonomous Implementation Integration — SF-02: Lint-Fix Reflection Loop Integration

- **Feature ID**: INT-US-03
- **Sub-Feature**: SF-02 — Lint-Fix Reflection Loop Integration
- **Design Document**: docs/roadmap/features/topic_08_integration/INT-US-03/INT-US-03_design.md
- **Design Section**: §Sub-Feature Breakdown → SF-02
- **Implementation Plan**: docs/roadmap/features/topic_08_integration/INT-US-03/INT-US-03_sf02_implementation_plan.md
- **Status**: APPROVED — approved by Steve Bula on 2026-07-18. Audit Q1–Q5 all resolved to option **(a)**.

## Scope (from the Design Document)

Append the `lint_fix` step (`LINT_FIX`/`CODE`, `ruff` auto-fix + LLM reflection loop) to the
`implement_spec` pipeline SF-01 established, and extend the inline report with
`{reflections_used, lint_errors_remaining, auto_fixed}`. **FR owned: FR-2.** Depends on SF-01
(committed). Host mode — worktree isolation is SF-03; Podman is out of scope for the whole feature.

## Research Notes (Phase 0)

1. **`LintFixHandler` already exists and is wired-ready** (`core/flow/handlers/lint_fix.py:23`, key
   `lint_fix+code`, in `VALID_STEP_COMBINATIONS`). `execute` (`lint_fix.py:37`):
   - reads `target = step.params.get("target", "src/")` and `max_reflections = step.params.get("max_reflections", 3)`.
   - **Phase 1 (cheap):** `run_linter` on `target`; if clean → PASS; else `ruff --fix` then re-lint. If now
     clean → PASS `{reflections_used:0, lint_errors_remaining:0, auto_fixed:True}` (`lint_fix.py:103-114`).
   - **Phase 2 (LLM reflection):** loops up to `max_reflections`; each cycle asks the LLM to rewrite the
     code file, re-lints. Clean → PASS; exhausted → **FAIL** `{reflections_used, lint_errors_remaining}`
     (`lint_fix.py:116-209`). No LLM → FAIL; LLM error → ERROR.
   - The linter targets `params["target"]` directly, so **Phase 1 works with just a file path** (no
     `output_dir` needed).
2. **Gap (mirror of SF-01 Q1):** the Phase-2 LLM loop locates the file via
   `_find_code_files(context)` → `context.output_dir.glob("*.py")` (`lint_fix.py:218-222`). The implement
   `RunContext` leaves `output_dir` unset (SF-01, NFR-2), so when ruff can't fully auto-fix and Phase 2
   engages, `_find_code_files` returns `[]` → FAIL "No code files found to fix". → SF-02 must teach
   `_find_code_files` to honor the explicit `target` (the generated `src/<stem>.py`), exactly as SF-01 did
   for `ValidateCodeHandler._find_code_path`. `target` is already in scope in `execute` (line 41).
3. **Current committed pipeline** (`cli.py:_build_implement_pipeline`): `generate_code → generate_tests →
   run_tests` (loop-back gate → `generate_code`, `max_retries=2`) `→ validate_code` (`CONTINUE` gate). SF-02
   inserts `lint_fix`.
4. **Reporting:** `_report_implementation` (`cli.py:90`) has per-step branches; SF-02 adds a `lint_fix`
   branch printing reflections/remaining/auto_fixed.
5. **Isolation (forward compat):** per `pipeline_engine_guide.md §7`, `lint_fix` (static ruff) is
   intentionally **project-root-bound** even under US-9 isolation — so SF-02's placement/targeting is
   isolation-agnostic; SF-03 needs no change to the lint step.
6. **Existing tests** (`tests/unit/core/flow/handlers/test_lint_fix_handler.py`) cover clean/auto-fix/
   reflection/exhausted/no-llm/zero-reflections/llm-error/no-code-files/stale-nodes/uuid/db-logging — a
   `test_no_code_files_found` exists for the output_dir-empty path; SF-02's `_find_code_files` change must
   keep that behavior when no `target` is given.

### External deps: none new (`ruff` already invoked by the QA runner). No `pyproject.toml` change.

## Implementation Approach

> Pseudocode / step-lists only.

### Change 1 — Insert `lint_fix` into the pipeline (FR-2) · `cli.py`
Add a `lint_fix` step (`LINT_FIX`/`CODE`) to `_build_implement_pipeline`:
- `params = {"target": f"src/{stem}.py", "max_reflections": 3}`
- `gate = GateDefinition(on_fail=OnFailAction.CONTINUE)` (report-only)
- **Position: immediately before `run_tests`** (see Audit Q2): `generate_code → generate_tests →
  lint_fix → run_tests → validate_code`, so tests + C01–C08 validate the lint-fixed code.

### Change 2 — Teach `_find_code_files` to honor an explicit target (FR-2) · `lint_fix.py`
`LintFixHandler._find_code_files(context, target=None)`: if `target` resolves (against `project_path`) to
an existing file inside the project → return `[that_file]`; else fall back to the existing
`output_dir.glob("*.py")`. Update the single caller in `execute` to pass `target`. Backward-compatible
(no current caller passes a file target that would change the glob path); traversal-guarded like SF-01.

### Change 3 — Report lint outcome (extends FR-7) · `cli.py`
Add a `name == "lint_fix"` branch to `_report_implementation`: print `auto_fixed` / `reflections_used` /
`lint_errors_remaining` (green when 0 remain; yellow when some remain — report-only).

### Files to modify
| File | Change | FR |
|------|--------|-----|
| `src/specweaver/workflows/implementation/interfaces/cli.py` | insert `lint_fix` step; add report branch | FR-2 |
| `src/specweaver/core/flow/handlers/lint_fix.py` | `_find_code_files` honors `target` | FR-2 |
| `tests/unit/workflows/implementation/test_implement_pipeline.py` | assert lint_fix step/gate/params/position | FR-2 |
| `tests/unit/workflows/implementation/test_implement_reporting.py` | lint_fix report branch | FR-2 |
| `tests/unit/core/flow/handlers/test_lint_fix_handler.py` | `_find_code_files` target-honoring cases | FR-2 |
| `tests/integration/interfaces/cli/test_cli_implement.py` | lint_fix stubbed in the loop (report + report-only) | FR-2 |

No new files/modules/migrations/YAML.

## Test Plan (4 Adversarial Buckets)

**Unit — pipeline:** [Happy] pipeline is `[generate_code, generate_tests, lint_fix, run_tests,
validate_code]`; `lint_fix` params `target=src/<stem>.py`, `max_reflections=3`, gate `CONTINUE`.
[Boundary] lint_fix precedes run_tests (position assertion).

**Unit — `_find_code_files`:** [Happy] `target` file exists → `[file]`. [Boundary] no target → output_dir
glob unchanged (`test_no_code_files_found` still holds). [Hostile] `../` traversal target → not resolved
outside project → falls back/empty.

**Unit — reporting:** [Happy] auto_fixed clean → "lint: auto-fixed, 0 remaining". [Boundary] reflections
used, some remaining → yellow report. [Hostile] malformed/empty lint output → defaults, no crash.

**Integration — CLI (lint_fix stubbed):** [Happy] lint passes → reported, exit 0. [Graceful] lint_fix
FAILED (errors remain) → report-only, run still exits 0 (gate CONTINUE); tests still gate the exit.

## Audit (Phase 2) — open questions for HITL

| # | Question | Options | Proposal | Severity |
|---|----------|---------|----------|----------|
| Q1 | Phase-2 LLM reflection can't find the generated file without a handler change (Note 2). Approve the `_find_code_files` target-honoring enhancement in `core/flow/handlers/lint_fix.py` (outside `workflows/implementation`, mirrors approved SF-01 Q1)? | (a) enhance handler [rec]; (b) set `output_dir` (breaks src/tests split — rejected in SF-01); (c) accept Phase-2 always fails when output_dir unset. | **(a)** — smallest correct fix; precedent set by SF-01; backward-compatible. | **HIGH** |
| Q2 | Where does `lint_fix` go? | (a) **before `run_tests`** [rec] — tests + C01–C08 validate the lint-fixed code; a lint rewrite that breaks behavior is caught by run_tests. (b) **last, after `validate_code`** — matches the contract's textual order and runs lint_fix once (cheaper), but tests/validation then ran on un-fixed code and a final LLM rewrite could silently break passing tests. | **(a)** — correctness (validate the final artifact) outweighs the bounded extra cost. | **HIGH** |
| Q3 | `lint_fix` gate. | (a) `CONTINUE` report-only [rec]; (b) `ABORT` on remaining errors. | **(a)** — remaining lint shouldn't kill an otherwise-working autonomous run; required anyway if lint_fix precedes run_tests (else tests never run). Consistent with `validate_code`. | MEDIUM |
| Q4 | Cost: with Q2(a), `lint_fix` re-runs on each `run_tests` loop-back (≤2), so up to 3 executions incl. LLM reflection. Acceptable? | (a) accept (bounded by `max_retries=2` × `max_reflections=3`) [rec]; (b) move lint_fix after the loop (Q2 b). | **(a)** — ruff Phase-1 is cheap and resolves most; LLM reflection is the rare tail; NFR-5 bounds it. | MEDIUM |
| Q5 | `max_reflections` value. | (a) handler default 3 [rec]; (b) configurable. | **(a)** — bounded, no new surface. | LOW |

## Architecture Verification (Phase 3)
- **Mechanism × constraint:** `cli.py` — Pydantic step build + string handling, imports already present
  (`GateDefinition`/`OnFailAction`), `orchestrator` archetype OK. `lint_fix.py` — pure `Path` resolution in
  `_find_code_files` (mirror of the SF-01 `_find_code_path` change), no new import, no I/O class added;
  `lint_fix` stays static/root-bound. **No archetype/`forbids` conflict.**
- **Zoom-out/duplication:** reuses the existing `LintFixHandler`/atom; extends an existing finder rather
  than adding a parallel one. No new module.
- **Acyclic imports:** no new cross-module edge. **tach** must stay green.
- **Common closure:** 2 modules (`workflows/implementation`, `core/flow/handlers`) — the intended
  integration seam; identical shape to SF-01. **Verdict: no CRITICAL violation.**

## Implementation Notes (as-built, 2026-07-18)

Delivered the SF-02 scope. Files changed: `cli.py` (`lint_fix` step inserted before `run_tests`;
`_report_implementation` lint branch) and `core/flow/handlers/lint_fix.py` (`_find_code_files` honors an
explicit, traversal-guarded `target`; caller updated). Tests: `test_lint_fix_find_code_files.py` (7),
`test_implement_pipeline.py` (+3), `test_implement_reporting.py` (+3), `test_cli_implement.py` (+4 incl.
graceful-failure), `tests/e2e/conftest.py` `stub_implement_qa` extended to stub `LintFixHandler`.

Confirmed during dev:
- **Graceful failure:** the `lint_fix` `CONTINUE` gate absorbs BOTH `FAILED` (errors remain after
  reflections) and `ERROR` (LLM crash mid-reflection) — the autonomous run advances to `run_tests`, which
  governs the exit code. Verified by integration tests.
- `_find_code_files` mirrors SF-01's `_find_code_path`, but a *missing* explicit file target falls back to
  the `output_dir` glob (lint is happy to lint available files) rather than returning empty — intentional
  and tested.
- No `output_dir` set by `implement` (NFR-2 preserved); lint stays project-root-bound (isolation-agnostic).

## Session Handoff
**Current status**: Implemented; pre-commit gate in progress (2026-07-18). Ready for commit boundary CB-1.
**Next step**: SF-03 (Zero-Trust Isolation + verifiable-proof e2e) closes the US-3 base contract.
