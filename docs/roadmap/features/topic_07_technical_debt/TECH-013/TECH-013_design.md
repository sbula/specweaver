# Design: API Composition Roots Do Not Resolve Worktree-Isolation Policy

- **Feature ID**: TECH-013
- **Epic**: Topic 07 (Technical Debt)
- **Status**: STUB — not yet run through the `specweaver-design` skill
- **Origin**: Recorded during `C-EXEC-06 SF-03`'s implementation-plan Phase 4 (2026-07-20). SF-03 wires
  per-run (session) isolation policy at the **CLI** composition roots only (matching where `enforce_isolation`
  already lives) and explicitly deferred the **API** run sites to this ticket.
- **Severity**: MEDIUM — the API can start pipeline runs that silently ignore both isolation policies; a
  deployment relying on the REST API for autonomous/untrusted runs gets no worktree bounding even when the
  operator has enabled it in `[sandbox]`.

## Problem Statement

Worktree-isolation policy (`SandboxSettings.enforce_worktree_isolation` for per-step, and
`enforce_session_isolation` for per-run, added in `C-EXEC-06 SF-03`) is resolved at the **CLI** composition
roots and frozen onto `RunContext`:
- `sw run` → `_execute_run` (`core/flow/interfaces/cli.py:269-272`) sets `context.enforce_isolation`; SF-03
  additionally sets `context.session_isolation` + `context.allowed_paths` here.
- `sw resume` → `resume` (`cli.py:470-473`) does the same.

The **API** composition roots do **not** resolve any of this policy — a documented pre-existing INT-US-09 gap
(`interfaces/api/v1/pipelines.py:84-95`): `start_pipeline_run`, `resume_run`, and `submit_gate_decision`
construct `RunContext` without ever setting `enforce_isolation` (and now `session_isolation`/`allowed_paths`).
So an API-triggered run always executes with isolation **off**, regardless of `[sandbox]` settings.

**Coverage gap:** there is no API-level test asserting that an enabled `[sandbox]` isolation policy actually
reaches an API-started run's `RunContext`.

## Goal

Resolve worktree-isolation policy (per-step AND per-run) at the API composition roots with the same
best-effort, composition-root-frozen pattern the CLI uses (ADR-002), so REST-triggered runs honor the operator's
`[sandbox]` settings. Add API-level coverage proving the policy reaches the run.

## Relationship to `C-EXEC-06`

`C-EXEC-06 SF-03` deliberately scoped its wiring to the CLI to stay consistent with the existing INT-US-09
boundary and keep the sub-feature tight. The shared policy-resolution helper SF-03 introduces
(`apply_session_policy` in `core/flow/engine/runner_utils.py`) is intended to be reused verbatim at the API
sites when this ticket is picked up — the fix is expected to be small (call the same helper alongside an
`enforce_isolation` resolution at each API run site).

## Candidate Approaches (not yet designed)
1. **Reuse the CLI helper at each API run site** — recommended; call `apply_session_policy(context, settings,
   logger)` (and resolve `enforce_isolation`) in `start_pipeline_run`/`resume_run`/`submit_gate_decision`.
2. **Centralize composition-root policy resolution** — one factory that both CLI and API call to build a
   fully-policied `RunContext`, eliminating the drift risk entirely (larger; overlaps with `TECH-006`'s
   RunContext-God-Object concerns).

## Non-Goals (proposed, pending design)
- Changing isolation semantics or the `allowed_paths` derivation (owned by `C-EXEC-06`).
- The broader RunContext-construction refactor (that's `TECH-006`).

## Next Step
Run `specweaver-design TECH-013`. Add an API-level test that an enabled `[sandbox]` policy reaches an
API-started run's `RunContext` (both `enforce_isolation` and `session_isolation`).
