# Implementation Plan: Ephemeral Podman Sub-Containers [SF-03: Sandbox Config Plumbing]

- **Feature ID**: B-EXEC-01
- **Sub-Feature**: SF-03 — Sandbox Config Plumbing
- **Design Document**: docs/roadmap/features/topic_06_sandbox/B-EXEC-01/B-EXEC-01_design.md
- **Design Section**: §Sub-Feature Breakdown → SF-03
- **Implementation Plan**: docs/roadmap/features/topic_06_sandbox/B-EXEC-01/B-EXEC-01_sf03_implementation_plan.md
- **Status**: APPROVED

## Scope

Load the `[sandbox]` TOML section into `SandboxSettings` (the model itself already landed in
SF-02, pulled forward early for a type-hint dependency) via a new `_load_toml_sandbox()` loader,
threaded into `load_settings_async()`. This is the smallest sub-feature — one function, one
call-site change.

**FRs covered**: FR-9 (loader half — the model itself is SF-02's).
**Inputs**: the target project's `specweaver.toml`.
**Outputs**: a `SandboxSettings` instance on `SpecWeaverSettings.sandbox`, defaulting to
`execution_mode="host"` on any absence or parse failure.
**Depends on**: SF-02 (committed — provides the `SandboxSettings` model).

## Research Notes

- **`_load_toml_standards()` pattern** (`core/config/settings_loader.py:54`): reads
  `<root_path>/specweaver.toml`, extracts `toml_data.get("standards", {})`, constructs
  `StandardsSettings(**std_data)` inside a try/except that logs and falls back to the default on
  any parse failure. `_load_toml_sandbox()` mirrors this exactly for a new `[sandbox]` table.
- **`core/config/context.yaml`**: needs `SandboxSettings` added to the `exposes:` list (alongside
  `ValidationSettings`, `LLMSettings`) — a pure documentation/interface-declaration change, not a
  code change.

## Proposed Changes

| File | Change | Purpose |
|------|--------|---------|
| `src/specweaver/core/config/settings_loader.py` | `[MODIFY]` | Add `_load_toml_sandbox(root_path)`; thread into `load_settings_async()` |
| `src/specweaver/core/config/context.yaml` | `[MODIFY]` | Add `SandboxSettings` to `exposes:` |
| `tests/unit/core/config/test_settings_loader.py` | `[MODIFY]` | `_load_toml_sandbox` tests |

## Implementation Sequence (pseudocode)

`_load_toml_sandbox(root_path: str | None) -> SandboxSettings`: byte-for-byte mirror of
`_load_toml_standards` — read `specweaver.toml`, `toml_data.get("sandbox", {})`, construct
`SandboxSettings(**data)` inside the same try/except-log-and-default pattern. Call it in
`load_settings_async()` alongside the existing `standards = _load_toml_standards(...)` line;
thread `sandbox=sandbox` into the final `SpecWeaverSettings(...)` construction.

## Test Plan

| Test | FR/NFR | Asserts |
|------|--------|---------|
| `test_load_toml_sandbox_parses_execution_mode` | FR-9 | `specweaver.toml` with `[sandbox]\nexecution_mode = "container"` → `SandboxSettings(execution_mode="container")` |
| `test_load_toml_sandbox_defaults_on_missing_section` | NFR-7 | No `[sandbox]` table → `SandboxSettings()` (host default) |
| `test_load_toml_sandbox_defaults_on_parse_error` | Error handling | Malformed TOML → logged exception, default `SandboxSettings()`, no crash |

## FR / NFR Coverage

| ID | Covered by |
|----|-----------|
| FR-9 | `_load_toml_sandbox()` defaulting to `"host"`; test: `test_load_toml_sandbox_defaults_on_missing_section` |
| NFR-7 | Default `execution_mode="host"` byte-identical behavior on missing/malformed config; tests: `test_load_toml_sandbox_defaults_on_missing_section`, `test_load_toml_sandbox_defaults_on_parse_error` |

## Phase 5: Final Consistency Check

**5.1 Open questions**: None.

**5.2 Architecture**: pure `core.config`-internal change — no new I/O mechanism reaching into
`sandbox` (the `forbids: specweaver/sandbox/*` rule in `core/config/context.yaml` is respected —
`config` never imports `sandbox`, only the reverse).

### Red/Blue Team Review

No findings beyond what the test-gap analysis already covers (see Post-Implementation Notes) —
this sub-feature mirrors an existing, already-reviewed pattern (`_load_toml_standards`) closely
enough that no new architectural risk was identified.

---

## HITL Gate — Approval Required

This plan is ready for review. Summary: 1 new function, 1 call-site change, 1 interface
declaration, 3 tests. Mirrors an existing pattern exactly.

Reply with approval to mark this plan `APPROVED` and proceed to the `dev` skill for SF-03's TDD
implementation.

---

## Post-Implementation Notes

**Landed as planned**: `_load_toml_sandbox()` in `settings_loader.py`, mirroring
`_load_toml_standards()` exactly — reads the target project's `specweaver.toml` `[sandbox]`
table, falls back to `SandboxSettings()` (host default) on absence or any parse failure. Threaded
into `load_settings_async()`'s final `SpecWeaverSettings(...)` construction.

**No test gaps found**: the pre-commit gate's test-gap analysis found this sub-feature's 3 tests
already meet or exceed the coverage depth of `_load_toml_standards()` — the sibling function this
mirrors — which itself has only 2 loader-level tests and no dedicated malformed-TOML test.

**Unrelated flake observed and dismissed**: one
`tests/unit/graph/lineage/store/test_lineage_repository.py::test_log_artifact_event_concurrent_writes`
failure appeared during the full-suite run — confirmed flaky (passes reliably in isolation), in a
module with zero relationship to anything this sub-feature touches. Not investigated further.

**Test counts**: 3 new tests, all green (165 `core/config` tests overall, zero regressions). Full
suite: unit 4608 passed/15 skipped, integration 434 passed/5 skipped/15 deselected, e2e 139
passed/1 skipped.

**Documentation updated**: `subprocess_execution.md`'s "Opt-In via QARunnerAtom" section extended
with an "Enabling It From specweaver.toml" subsection.

**Committed as**: `8046f12c`.
