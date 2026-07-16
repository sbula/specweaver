# Implementation Plan: Ephemeral Podman Sub-Containers [SF-04: Pipeline Handler Wiring & Scaffolding]

- **Feature ID**: B-EXEC-01
- **Sub-Feature**: SF-04 — Pipeline Handler Wiring & Scaffolding
- **Design Document**: docs/roadmap/features/topic_06_sandbox/B-EXEC-01/B-EXEC-01_design.md
- **Design Section**: §Sub-Feature Breakdown → SF-04
- **Implementation Plan**: docs/roadmap/features/topic_06_sandbox/B-EXEC-01/B-EXEC-01_sf04_implementation_plan.md
- **Status**: APPROVED

## Scope

Connect `specweaver.toml`'s `[sandbox]` table to an actual pipeline run: `ValidateTestsHandler`
and `LintFixHandler` read `context.config.sandbox` and pass it to `QARunnerAtom`. Scaffold
`.specweaver/.sandbox/` out of version control for every new project. Ship the declarative
`Containerfile.sandbox` toolchain base image. This is the last sub-feature — after it,
`execution_mode: "container"` is reachable end-to-end from a real pipeline run.

**FRs covered**: FR-1 (pipeline reachability), FR-9.
**Inputs**: SF-03's `SandboxSettings`/`_load_toml_sandbox`; `RunContext.config` (already present
on every handler's context).
**Outputs**: a real pipeline run honors `[sandbox] execution_mode = "container"`; `.gitignore`
keeps sandbox scratch/cache dirs untracked; an operator can build `Containerfile.sandbox` to get
a working toolchain image.
**Depends on**: SF-03 (committed).

## Research Notes

- **`RunContext.config`** (`core/flow/handlers/base.py:53`): `Any = None  #
  SpecWeaverSettings | None` — already present on every handler's context.
  `ValidateTestsHandler._get_atom` (`validation.py:403-407`) and `LintFixHandler._get_atom`
  (`lint_fix.py:211-215`) both currently do `QARunnerAtom(cwd=context.project_path)` — both can
  read `context.config.sandbox` for free, no new plumbing needed on `RunContext` itself.
- **`.gitignore` scaffolding precedent** (`workspace/project/scaffold.py:343-354`):
  `_scaffold_gitignore_vault()` appends `.specweaver/vault.env` to the project's `.gitignore` via
  `NativeIgnoreIOHandler`, idempotently (checks the line isn't already present first). A new
  `_scaffold_gitignore_sandbox()` mirrors this exactly for `.specweaver/.sandbox/`.
- **Only 2 of 4 `QARunnerAtom` call sites are wired** (per SF-02's Resolved Audit Findings #8):
  `validation_hydrator.py`/`facades.py` are left unwired for scope discipline, logged in Backlog.
- **Existing D-EXEC-01 GHCR publish pipeline**: the repo-root `Containerfile` + CI publish a
  `sw serve` deployment image. A new sandbox base image is a **separate** artifact — its
  `Containerfile.sandbox` is included as a static, declarative Proposed Change, but the CI
  workflow that builds+publishes it to GHCR is explicitly deferred (Backlog) — `dev`-skill TDD
  doesn't touch CI YAML.

## Resolved Audit Findings

5. **(#5, MEDIUM)** Scratch/cache directories are project-local:
   `<project_root>/.specweaver/.sandbox/{scratch,cache}/`, created lazily by
   `ContainerSubprocessExecutor` on first use (SF-01), with a new `.gitignore` entry scaffolded
   eagerly here (mirrors `vault.env`'s precedent).
6. **(#6, MEDIUM)** SpecWeaver publishes an official minimal sandbox image family
   (`python:3.11/3.12/3.13-slim` + `uv` preinstalled, nothing project-specific baked in). This
   sub-feature ships the declarative `Containerfile.sandbox`; the CI build+publish automation is
   deferred (Backlog).
8. **(#8, MEDIUM)** `validation_hydrator.py` and `facades.py` are left unwired (logged in
   Backlog, not silently dropped) — only `validation.py`/`lint_fix.py`'s `_get_atom` methods are
   updated.
10. **(#10, LOW)** CI provisioning of a real container engine for integration/e2e tests: out of
    scope, Backlog item.

## Proposed Changes

| File | Change | Purpose |
|------|--------|---------|
| `src/specweaver/core/flow/handlers/validation.py` | `[MODIFY]` | `ValidateTestsHandler._get_atom` passes `sandbox_settings=context.config.sandbox if context.config else None` |
| `src/specweaver/core/flow/handlers/lint_fix.py` | `[MODIFY]` | Same as above for `LintFixHandler._get_atom` |
| `src/specweaver/workspace/project/scaffold.py` | `[MODIFY]` | New `_scaffold_gitignore_sandbox()`, called from `scaffold_project()` alongside the existing vault call |
| `Containerfile.sandbox` (repo root) | `[NEW]` | Declarative multi-stage image spec: `python:3.1{1,2,3}-slim` + `uv`, no project-specific bake |
| `tests/unit/core/flow/handlers/test_validate_tests_handler.py` | `[MODIFY]` | `sandbox_settings` passthrough test |
| `tests/unit/core/flow/handlers/test_lint_fix_handler.py` | `[MODIFY]` | `sandbox_settings` passthrough test |
| `tests/unit/workspace/project/test_scaffold.py` | `[MODIFY]` | `.gitignore` sandbox-entry scaffolding tests |

## Implementation Sequence (pseudocode)

`_get_atom(self, context: RunContext) -> QARunnerAtom` (both handlers): `sandbox_settings =
context.config.sandbox if context.config else None`; return `QARunnerAtom(cwd=context.project_path,
sandbox_settings=sandbox_settings)`.

`_scaffold_gitignore_sandbox(project_path: Path) -> None`: byte-for-byte mirror of
`_scaffold_gitignore_vault` — check `.gitignore` for the literal line `.specweaver/.sandbox/`,
append via `NativeIgnoreIOHandler` if absent. Call from `scaffold_project()` alongside the
existing `_scaffold_gitignore_vault(project_path)` call, **unconditionally** (not gated behind
`mcp_target`, since `[sandbox]` isn't MCP-specific).

`Containerfile.sandbox`: a small, declarative multi-stage-free Containerfile (matching the style
of the existing root `Containerfile`, not authored as TDD code): `ARG PY_VERSION=3.13`, `FROM
python:${PY_VERSION}-slim`, install `uv` (pinned version, same mechanism the root `Containerfile`
already uses), create a non-root user, no `ENTRYPOINT`/`CMD` (the wrapped `podman run ... image
*cmd` invocation supplies the command every time).

## Test Plan

| Test | FR/NFR | Asserts |
|------|--------|---------|
| `test_validate_tests_handler_passes_sandbox_settings` | Pipeline integration | `RunContext.config.sandbox` set → `QARunnerAtom` receives it |
| `test_lint_fix_handler_passes_sandbox_settings` | Pipeline integration | Same, for `LintFixHandler` |
| `test_scaffold_gitignore_sandbox_appends_once` | Finding #5 | `.gitignore` gets `.specweaver/.sandbox/` appended; re-running scaffold doesn't duplicate the line |

## FR / NFR Coverage

| ID | Covered by |
|----|-----------|
| FR-1 | Pipeline-reachable container routing; tests: `test_validate_tests_handler_passes_sandbox_settings`, `test_lint_fix_handler_passes_sandbox_settings` |
| FR-9 | `QARunnerAtom` default-`None` `sandbox_settings` propagated from handlers unchanged when absent |

## Backlog (deferred, out of scope for B-EXEC-01 entirely)

- **CI container-engine provisioning**: integration/e2e tests `skipif` cleanly today without it.
- **`Containerfile.sandbox` CI build+publish automation**: until it ships, `execution_mode:
  "container"` requires an operator to build `Containerfile.sandbox` locally.
- **`validation_hydrator.py` / `facades.py` container wiring**: the other 2 of 4 `QARunnerAtom`
  call sites.
- **A capstone integration test**: `ValidateTestsHandler.execute()` itself, container mode, real
  Podman, proving the entire chain from `specweaver.toml` down to a real `pytest` result via SF-01's
  `uv sync` prepare phase (never exercised for real anywhere in this feature — always mocked at
  the `super().execute()` boundary in SF-01's unit tests, exercised only up to the
  `factory`/`atom` layer in SF-02's integration test). Proposed during this sub-feature's test-gap
  analysis and declined by the user at the time (see Post-Implementation Notes); a natural target
  for whoever next touches this code, or a manual smoke test before wider rollout.
- **Literal e2e-tier (CLI-invocation) test**: the roadmap's Proof Mandate technically wants one
  before flipping a capability-matrix status to ✅; everything built across `B-EXEC-01` is
  unit/integration-tier (the integration tests do exercise a real Podman engine, which is the
  substantively important part, but they are not literal `tests/e2e/` CLI-invocation tests per
  `tests/CLAUDE.md`'s definition). Flagged transparently on the roadmap status flip rather than
  silently resolved.

## Phase 5: Final Consistency Check

**5.1 Open questions**: None remaining — all findings resolved via "proceed with all proposals."

**5.2 Architecture**: `core/flow/handlers/{validation,lint_fix}.py` read an already-present
`RunContext.config` field, no new import needed beyond a `TYPE_CHECKING`-guarded type hint. No
`tach.toml` change required.

### Red/Blue Team Review (2 cycles run)

No new findings beyond the already-flagged roadmap/e2e-proof gap (see Backlog). Converged.

---

## HITL Gate — Approval Required

This plan is ready for review. Summary: 2 modified handlers, 1 modified scaffold function, 1 new
declarative Containerfile, 3 test files. This is the last sub-feature of `B-EXEC-01` — after it,
the feature is reachable end-to-end from a real pipeline run.

Reply with approval to mark this plan `APPROVED` and proceed to the `dev` skill for SF-04's TDD
implementation.

---

## Post-Implementation Notes

**Landed as planned**: `ValidateTestsHandler`/`LintFixHandler` both pass
`context.config.sandbox if context.config else None` to `QARunnerAtom` — the last piece
connecting `specweaver.toml`'s `[sandbox]` table to an actual containerized pipeline step.
`_scaffold_gitignore_sandbox()` keeps `.specweaver/.sandbox/` out of version control, called
**unconditionally** from `scaffold_project()`. `Containerfile.sandbox` is the declarative
Python+`uv` toolchain base image spec.

**Capstone integration test proposed, declined**: the test-gap analysis proposed one more
integration test — `ValidateTestsHandler.execute()` itself, container mode, real Podman, proving
the entire chain from `specweaver.toml` down to a real `pytest` result via SF-01's `uv sync`
prepare phase. The user replied "please commit" without approving it, treated as a decline — not
implemented. See Backlog.

**Documentation updated**: `subprocess_execution.md`'s two remaining forward-references ("lands
in a later commit") corrected to state the wiring is real, and a note added that
`validation_hydrator.py`/`facades.py` remain deliberately unwired (Backlog, not oversight).

**Test counts**: 7 new tests, all green (485 `core/flow/handlers` + `workspace/project` tests
overall, zero regressions). Full suite: unit 4615 passed/15 skipped, integration 434 passed/5
skipped/15 deselected, e2e 139 passed/1 skipped.

**Feature status — `B-EXEC-01` complete**: all 4 sub-features done across commits `68c34359`,
`7e31ea9b`, `8046f12c`, `a2143124`. `master_story_roadmap.md`/`capability_matrix.md` status flips
for `B-EXEC-01` were made as part of the later re-homing pass that corrected this feature's
original (mis-scoped) `INT-US-09` labeling — transparently noting the Proof Mandate is satisfied
at integration-tier (real Podman), not literal e2e-tier, per the Backlog above.

**Committed as**: `a2143124`.
