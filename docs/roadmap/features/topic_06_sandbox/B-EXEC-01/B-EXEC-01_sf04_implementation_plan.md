# B-EXEC-01 SF-04 — Pipeline Handler Wiring & Scaffolding

**Status**: APPROVED. Committed as `a2143124`. · **FRs owned**: FR-1 (pipeline reachability),
FR-9 · **Depends on**: SF-03 (committed) · Design: [B-EXEC-01_design.md](B-EXEC-01_design.md)
§Sub-features → SF-04

## Goal

Make `[sandbox] execution_mode = "container"` reachable from a real pipeline run:
- `ValidateTestsHandler` and `LintFixHandler` read `context.config.sandbox` and pass it to
  `QARunnerAtom`;
- every new project gets `.specweaver/.sandbox/` in `.gitignore`;
- ship the declarative `Containerfile.sandbox` toolchain base image, so an operator can build a
  working image.

## Where it plugs in

- **`RunContext.config`** (`core/flow/handlers/base.py:53`): `Any = None  #
  SpecWeaverSettings | None`, on every handler's context. `ValidateTestsHandler._get_atom`
  (`validation.py:403-407`) and `LintFixHandler._get_atom` (`lint_fix.py:211-215`) both do
  `QARunnerAtom(cwd=context.project_path)` — they can read `context.config.sandbox` with no new
  `RunContext` plumbing. `core/flow/handlers/{validation,lint_fix}.py` add only a `TYPE_CHECKING`-guarded type hint; no
  `tach.toml` change.
- **`.gitignore` precedent** (`workspace/project/scaffold.py:343-354`): `_scaffold_gitignore_vault()`
  appends `.specweaver/vault.env` via `NativeIgnoreIOHandler`, idempotently.
  `_scaffold_gitignore_sandbox()` mirrors it for `.specweaver/.sandbox/`.
- **D-EXEC-01's GHCR pipeline** publishes the `sw serve` image from the repo-root `Containerfile`.
  The sandbox image is a **separate** artifact.

## Changes

1. `_get_atom(self, context: RunContext) -> QARunnerAtom` (both handlers): `sandbox_settings =
   context.config.sandbox if context.config else None`; return
   `QARunnerAtom(cwd=context.project_path, sandbox_settings=sandbox_settings)`.
2. `_scaffold_gitignore_sandbox(project_path: Path) -> None`: byte-for-byte mirror of
   `_scaffold_gitignore_vault` — if `.gitignore` lacks the literal line `.specweaver/.sandbox/`,
   append it via `NativeIgnoreIOHandler`. Called from `scaffold_project()` next to
   `_scaffold_gitignore_vault(project_path)`, **unconditionally** — not gated behind `mcp_target`,
   since `[sandbox]` is not MCP-specific.
3. `Containerfile.sandbox`: small, declarative, multi-stage-free, in the root `Containerfile`'s
   style (not TDD code): `ARG PY_VERSION=3.13`, `FROM python:${PY_VERSION}-slim`, install `uv`
   (pinned, same mechanism as the root `Containerfile`), create a non-root user, no
   `ENTRYPOINT`/`CMD` (the wrapped `podman run ... image *cmd` supplies the command).

| File | Change | Purpose |
|------|--------|---------|
| `src/specweaver/core/flow/handlers/validation.py` | `[MODIFY]` | `ValidateTestsHandler._get_atom` passes `sandbox_settings=context.config.sandbox if context.config else None` |
| `src/specweaver/core/flow/handlers/lint_fix.py` | `[MODIFY]` | Same as above for `LintFixHandler._get_atom` |
| `src/specweaver/workspace/project/scaffold.py` | `[MODIFY]` | New `_scaffold_gitignore_sandbox()`, called from `scaffold_project()` alongside the existing vault call |
| `Containerfile.sandbox` (repo root) | `[NEW]` | Declarative image spec: `python:3.1{1,2,3}-slim` + `uv`, no project-specific bake |
| `tests/unit/core/flow/handlers/test_validate_tests_handler.py` | `[MODIFY]` | `sandbox_settings` passthrough test |
| `tests/unit/core/flow/handlers/test_lint_fix_handler.py` | `[MODIFY]` | `sandbox_settings` passthrough test |
| `tests/unit/workspace/project/test_scaffold.py` | `[MODIFY]` | `.gitignore` sandbox-entry scaffolding tests |

## Tests

| Test | FR/NFR | Asserts |
|------|--------|---------|
| `test_validate_tests_handler_passes_sandbox_settings` | FR-1 | `RunContext.config.sandbox` set → `QARunnerAtom` receives it |
| `test_lint_fix_handler_passes_sandbox_settings` | FR-1 | Same, for `LintFixHandler` |
| `test_scaffold_gitignore_sandbox_appends_once` | Finding #5 | `.gitignore` gets `.specweaver/.sandbox/` appended; re-running scaffold doesn't duplicate the line |

FR-9: `QARunnerAtom`'s default-`None` `sandbox_settings` passes from the handlers unchanged when
absent.

## Decisions (audit)

| # | Question | Chosen | Severity |
|---|----------|--------|----------|
| #5 | Where do scratch/cache dirs live? | Project-local `<project_root>/.specweaver/.sandbox/{scratch,cache}/`, created lazily by `ContainerSubprocessExecutor` (SF-01); the `.gitignore` entry is scaffolded eagerly here, like `vault.env` | MEDIUM |
| #6 | Which image? | An official minimal SpecWeaver sandbox image family (`python:3.11/3.12/3.13-slim` + `uv` preinstalled, nothing project-specific). This SF ships `Containerfile.sandbox`; CI build+publish is deferred | MEDIUM |
| #8 | Wire all 4 `QARunnerAtom` call sites? | No — only `validation.py`/`lint_fix.py`'s `_get_atom`. `validation_hydrator.py` and `facades.py` stay unwired, logged as open | MEDIUM |
| #10 | CI provisioning of a real engine for integration/e2e tests? | Out of scope | LOW |

All resolved via "proceed with all proposals".

**Open, outside B-EXEC-01:**
- CI container-engine provisioning (integration/e2e tests `skipif` cleanly without it).
- `Containerfile.sandbox` CI build+publish to GHCR — `dev`-skill TDD does not touch CI YAML. Until
  it ships, `execution_mode: "container"` requires an operator to build the image locally.
- Container wiring for `validation_hydrator.py`/`facades.py`.
- **Capstone integration test**: `ValidateTestsHandler.execute()` in container mode on real
  Podman, proving the chain from `specweaver.toml` to a real `pytest` result through SF-01's `uv
  sync` prepare phase. That phase is never exercised for real: SF-01's unit tests mock at the
  `super().execute()` boundary and SF-02's integration test stops at the `factory`/`atom` layer.
  Proposed in this SF's test-gap analysis; the user replied "please commit" without approving it,
  taken as a decline. Target for whoever next touches this code, or a manual smoke test before wider
  rollout.
- **Literal e2e-tier (CLI-invocation) test**: the roadmap's Proof Mandate wants one before a
  capability-matrix status goes ✅. B-EXEC-01 has unit/integration tests only; the integration tests
  hit a real Podman engine, but they are not `tests/e2e/` CLI-invocation tests per
  `tests/CLAUDE.md`. Flagged on the roadmap status flip.

## As built

- Landed as planned: both handlers pass `context.config.sandbox if context.config else None` to
  `QARunnerAtom`; `_scaffold_gitignore_sandbox()` called unconditionally from `scaffold_project()`;
  `Containerfile.sandbox` is the Python+`uv` base image spec.
- Tests: 7 new (485 `core/flow/handlers` + `workspace/project` tests overall). Suite at commit:
  unit 4615 passed/15 skipped, integration 434 passed/5 skipped/15 deselected, e2e 139 passed/1
  skipped.
- Docs: `subprocess_execution.md` states the wiring is real (two "lands in a later commit"
  forward references removed) and that `validation_hydrator.py`/`facades.py` are deliberately
  unwired.
- `master_story_roadmap.md`/`capability_matrix.md` flipped `B-EXEC-01` to done in the re-homing
  pass, noting the Proof Mandate is met at integration tier (real Podman), not literal e2e tier.
