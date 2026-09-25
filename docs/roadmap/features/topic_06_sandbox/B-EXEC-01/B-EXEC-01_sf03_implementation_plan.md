# B-EXEC-01 SF-03 — Sandbox Config Plumbing

**Status**: APPROVED. Committed as `8046f12c`. · **FRs owned**: FR-9 (loader half — the model is
SF-02's) · **Depends on**: SF-02 (committed — provides `SandboxSettings`) · Design:
[B-EXEC-01_design.md](B-EXEC-01_design.md) §Sub-features → SF-03

## Goal

Load the target project's `specweaver.toml` `[sandbox]` table into `SandboxSettings` via a new
`_load_toml_sandbox()`, threaded into `load_settings_async()`. Result: `SpecWeaverSettings.sandbox`,
defaulting to `execution_mode="host"` on absence or any parse failure.

## Where it plugs in

- **`_load_toml_standards()`** (`core/config/settings_loader.py:54`): reads
  `<root_path>/specweaver.toml`, takes `toml_data.get("standards", {})`, builds
  `StandardsSettings(**std_data)` in a try/except that logs and falls back to the default.
  `_load_toml_sandbox()` mirrors it.
- **`core/config/context.yaml`**: add `SandboxSettings` to `exposes:` (next to
  `ValidationSettings`, `LLMSettings`) — an interface declaration, not code.
- Stays inside `core.config`: `config` never imports `sandbox` (the `forbids: specweaver/sandbox/*`
  rule in `core/config/context.yaml`), only the reverse.

Since moved (2026-09-25): `settings_loader.py` → `core/config/bootstrap/settings_loader.py`.

## Changes

`_load_toml_sandbox(root_path: str | None) -> SandboxSettings`: byte-for-byte mirror of
`_load_toml_standards` — read `specweaver.toml`, `toml_data.get("sandbox", {})`, build
`SandboxSettings(**data)` in the same try/except-log-and-default. Call it in
`load_settings_async()` next to `standards = _load_toml_standards(...)`; pass `sandbox=sandbox`
into the final `SpecWeaverSettings(...)`.

| File | Change | Purpose |
|------|--------|---------|
| `src/specweaver/core/config/settings_loader.py` | `[MODIFY]` | Add `_load_toml_sandbox(root_path)`; thread into `load_settings_async()` |
| `src/specweaver/core/config/context.yaml` | `[MODIFY]` | Add `SandboxSettings` to `exposes:` |
| `tests/unit/core/config/test_settings_loader.py` | `[MODIFY]` | `_load_toml_sandbox` tests |

## Tests

| Test | FR/NFR | Asserts |
|------|--------|---------|
| `test_load_toml_sandbox_parses_execution_mode` | FR-9 | `specweaver.toml` with `[sandbox]\nexecution_mode = "container"` → `SandboxSettings(execution_mode="container")` |
| `test_load_toml_sandbox_defaults_on_missing_section` | FR-9, NFR-7 | No `[sandbox]` table → `SandboxSettings()` (host default) |
| `test_load_toml_sandbox_defaults_on_parse_error` | NFR-7, error handling | Malformed TOML → logged exception, default `SandboxSettings()`, no crash |

These 3 meet or exceed the depth of `_load_toml_standards()`'s own tests (2 loader-level, no
malformed-TOML test); the pre-commit test-gap analysis found no gaps.

## As built

- Landed as planned.
- Tests: 3 new (165 `core/config` tests overall). Suite at commit: unit 4608 passed/15 skipped,
  integration 434 passed/5 skipped/15 deselected, e2e 139 passed/1 skipped. One unrelated flake,
  `tests/unit/graph/lineage/store/test_lineage_repository.py::test_log_artifact_event_concurrent_writes`,
  passes in isolation.
- Docs: `subprocess_execution.md` "Opt-In via QARunnerAtom" gained "Enabling It From
  specweaver.toml".
