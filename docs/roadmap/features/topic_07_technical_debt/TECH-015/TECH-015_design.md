# Design: Retire Grab-Bag Modules (Name-Says-Nothing Refactor)

- **Feature ID**: TECH-015
- **Epic**: Topic 07 (Technical Debt)
- **Status**: STUB — not yet run through the `specweaver-design` skill
- **Origin**: User mandate during INT-US-21 SF-01 CB-4 (2026-07-25).

## Problem Statement

A module whose name promises nothing cannot be contradicted, so it accretes. Every author with
something that "sort of belongs near the runner" reaches for `runner_utils`. The mechanism is
observable rather than theoretical: INT-US-21 CB-4 added `try_staleness_bypass` to
`runner_utils.py` for exactly that reason, and relocated it to `engine/staleness.py` in the same
commit boundary once it was called out.

The fix is to split each offender into modules named for their **contract**, so the next addition
has something to violate.

## In Scope (4 modules, measured 2026-07-25)

| Module | Lines | Unrelated concerns |
|---|---|---|
| `core/flow/engine/runner_utils.py` | 413 | **9** |
| `core/flow/handlers/base.py` | 250 | 5 |
| `workspace/project/_helpers.py` | 172 | 3 |
| `interfaces/cli/_core.py` | 88 | 3 |

### 1. `core/flow/engine/runner_utils.py`

Nine concerns: isolation policy (`resolve_should_isolate`, `apply_session_policy`,
`_dal_requires_isolation`, `_derive_allowed_paths`), sandboxed execution (`execute_in_sandbox`,
`setup_sandbox_caches`), session-worktree lifecycle (`execute_run`), fan-out (`run_fan_out`), the
event protocol (`RunnerEventCallback`), vault security (`verify_vault_security`), telemetry
(`flush_telemetry`), time formatting (`_now_iso`).

Proposed targets: `isolation.py`, `session.py`, `fan_out.py`, `events.py`, `security.py`,
`telemetry.py`. **32 references across 8 files.**
`tests/unit/core/flow/engine/test_runner_utils.py` splits the same way — a test file named after a
grab-bag inherits the problem.

### 2. `core/flow/handlers/base.py`

**Do NOT rename this one — move the non-base members out.** `StepHandler` (a Protocol) legitimately
belongs in a `base`; `RunContext`, `_now_iso`, `_error_result` and `_build_base_prompt` do not.

`_now_iso` has **119 call sites**, most importing it from here rather than from `runner_utils`.
Relocating it to the L0 `commons` leaf is architecturally right but has the widest blast radius of
anything in this ticket, so it should be **its own step**.

> Coordinate with **`TECH-006`**, whose Finding 3 (RunContext god object) targets this same file.
> Do not let the two collide.

### 3. `workspace/project/_helpers.py`

Three concerns: constitution discovery/loading (`ConstitutionInfo`, `load_constitution`), directory
traversal (`walk_up_dirs`), markdown table rendering (`build_tech_stack_rows`,
`build_standards_section`).

### 4. `interfaces/cli/_core.py`

Three concerns: repo-op wrapper (`run_repo_op`), active-project guard (`_require_active_project`),
version callback (`_version_callback`).

## Explicitly OUT of Scope

These are legitimate single-ABC homes where `base` **is** the contract; renaming them would be pure
churn:

- `workspace/ast/parsers/base.py` — `BaseTreeSitterParser`
- `infrastructure/llm/adapters/base.py` — `LLMAdapter`
- `sandbox/base.py` — `AtomStatus` / `AtomResult` / `Atom` / `BaseTool`, one cohesive abstract kernel

## Guardrail to Ship With the Fix

A standards rule rejecting **new** module names matching `util(s)` / `helper(s)` / `misc` /
`shared` / `common` outside the L0 `specweaver/commons` leaf. Without it the pathology simply
regrows.

## Execution Constraint

Purely mechanical move + rename per module. **Land one module per commit**, full suite green each
time, and do **not** bundle any of it into a feature commit — the diff must stay trivially
reviewable as "moved, not changed".

## Next Step

Run the `specweaver-design` skill against this stub before any implementation.
