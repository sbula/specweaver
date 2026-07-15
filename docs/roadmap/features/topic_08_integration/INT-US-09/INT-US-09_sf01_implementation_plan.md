# Implementation Plan: Zero-Trust Sandbox Integration [SF-01: Core QA Runner Containerized Injection]

- **Feature ID**: INT-US-09
- **Sub-Feature**: SF-01 — Core QA Runner Containerized Injection
- **Design Document**: docs/roadmap/features/topic_08_integration/INT-US-09/INT-US-09_design.md
- **Design Section**: §Sub-Feature Breakdown → SF-01
- **Implementation Plan**: docs/roadmap/features/topic_08_integration/INT-US-09/INT-US-09_sf01_implementation_plan.md
- **Status**: APPROVED

## Scope

Build `ContainerSubprocessExecutor` — a `SubprocessExecutor` subclass that routes a command through an ephemeral Podman/Docker container (RO source mount, RW scratch mount, `--network none`) instead of the host — and wire it through `QARunnerAtom`/`PythonQARunner` via a new opt-in `[sandbox]` config section, defaulting to today's unsandboxed host behavior. Delivers `B-EXEC-01` (Ephemeral Podman Sub-Containers).

**FRs covered**: FR-1 through FR-9 (see design doc for full text).
**Inputs**: `PythonQARunner`'s existing argv-building logic (unchanged); host source root + a derived scratch/cache directory pair; the new `[sandbox]` config block; installed `podman`/`docker` CLI.
**Outputs**: A `SubprocessResult`-compatible response for every QA intent, produced inside an ephemeral, auto-removed container when `execution_mode: "container"` is set; unchanged host-mode behavior otherwise.
**Depends on**: none.

## Research Notes

- **The swap point**: every `PythonQARunner` method (`run_tests`, `run_linter`, `run_complexity`, `run_compiler`, `run_debugger`, `run_architecture_check` — `sandbox/language/core/python/runner.py`) calls `self._executor.execute(cmd, ...)` **exactly once**. `PythonQARunner.__init__(cwd, executor: SubprocessExecutor | None = None)` already has the DI seam (`runner.py:131`). All 5 language runners (Python/TS/Rust/Kotlin/Java) share this exact constructor shape — confirmed uniform across the codebase.
- **`SubprocessExecutor.execute()` exact signature** (`sandbox/execution/executor.py:90`): `execute(cmd: list[str], *, timeout_seconds: int | None = None, extra_env: dict[str,str] | None = None, cwd_override: Path | None = None, input_text: str | None = None) -> SubprocessResult`. Constructor: `__init__(cwd: Path, timeout_seconds: int = 120, resource_limits: ResourceLimits | None = None, env_allowlist: frozenset[str] | None = None, strip_credentials: bool = True)`. `resource_limits`/`preexec_fn`/Windows Job Objects apply to the **local `podman`/`docker` CLI client process**, not the containerized process — container-side limits are separate `--memory`/`--pids-limit` flags baked into the wrapped argv. Do not conflate the two.
- **No `input_text` usage exists today**: none of `PythonQARunner`'s 6 methods pass `input_text` to `execute()` (only the dev-guide's hypothetical Rust `cargo2junit` example does). Confirmed not applicable — no `-i`/`--interactive` flag handling needed for SF-01's actual call sites; if a future language runner adds one, it will need this flag added to `_build_container_cmd`.
- **`ResourceLimits`** (`sandbox/execution/models.py`): frozen dataclass, `max_memory_bytes`, `max_processes`, `max_file_size_bytes`, all default `None`. `BashActionAtom` (`sandbox/execution/core/atom.py:24`) sets `ResourceLimits(max_memory_bytes=2_147_483_648, max_processes=128)` as its own local default — SF-01 reuses these same numbers for the container's `--memory`/`--pids-limit` flags (AD-4), not by passing `ResourceLimits` to the parent `SubprocessExecutor` (which would only limit the local CLI client, per the point above).
- **Placement**: `execution/core/` (where `BashActionAtom` lives) only holds Atom-tier orchestration; `SubprocessExecutor` itself lives flat at `execution/executor.py`. `ContainerSubprocessExecutor` is executor-tier, not atom-tier, so it belongs flat at **`sandbox/execution/container_executor.py`**, sibling to `executor.py` — this also keeps it inside the TID251 subprocess-import-ban exemption glob (`"src/specweaver/sandbox/execution/*.py"`, confirmed flat/non-recursive in `pyproject.toml`), though the override design below never imports raw `subprocess` anyway (it only ever calls `super().execute()`).
- **`WorkspaceBoundary` / `ReadOnlyWorkspaceBoundary`** (`sandbox/security.py`): `WorkspaceBoundary(roots: list[Path], api_paths: list[Path] | None = None)`, `.validate_path(requested: Path) -> Path` (raises `WorkspaceBoundaryError`). `ReadOnlyWorkspaceBoundary(api_paths: list[Path])` — a subclass with no write roots, `.is_read_only` always `True`. This maps directly onto the two mounts: `ReadOnlyWorkspaceBoundary(api_paths=[source_root])` validates the RO source mount path, plain `WorkspaceBoundary(roots=[scratch_root, cache_root])` validates the RW mounts — reused, not reinvented (AD-3).
- **tach.toml**: `specweaver.sandbox` and `specweaver.core.config` are **flat** tach modules — `sandbox.execution`/`sandbox.qa_runner` only appear in the `[[interfaces]]` allow-list (governing imports from **outside** `specweaver.sandbox`, i.e. by `core.flow`), not as separate `[[modules]]`. Since `ContainerSubprocessExecutor` is consumed entirely *within* `sandbox` (by `qa_runner/core/factory.py` and `qa_runner/core/atom.py`), **no `tach.toml` change is needed for this SF** — internal sandbox-to-sandbox imports aren't gated by `[[interfaces]]`.
- **`MCPAtom`** (`sandbox/mcp/core/atom.py`) already enforces "must run through docker/podman" (`NFR-2 Boundary Violation` check on `command[0]`), and `mcp_implementation_patterns.md` documents this as an existing mandate. **Not directly reusable**: `MCPAtom` validates an *externally pre-built* command list (e.g. from an MCP server's own config) and bridges long-lived bidirectional JSON-RPC over stdio — a different execution model from this SF's one-shot, programmatically-mount-constructed container run. Cited as related precedent for the "must go through an isolated engine" convention, not as reusable argv-building code.
- **`RunContext.config`** (`core/flow/handlers/base.py:53`): `Any = None  # SpecWeaverSettings | None` — **already present** on every handler's context. `ValidateTestsHandler._get_atom` (`validation.py:403-407`) and `LintFixHandler._get_atom` (`lint_fix.py:211-215`) both currently do `QARunnerAtom(cwd=context.project_path)` — both can read `context.config.sandbox` for free, no new plumbing needed on `RunContext` itself.
- **`_load_toml_standards()` pattern** (`core/config/settings_loader.py:54`): reads `<root_path>/specweaver.toml`, extracts `toml_data.get("standards", {})`, constructs `StandardsSettings(**std_data)` inside a try/except that logs and falls back to the default on any parse failure. `_load_toml_sandbox()` mirrors this exactly for a new `[sandbox]` table.
- **`.gitignore` scaffolding precedent** (`workspace/project/scaffold.py:343-354`): `_scaffold_gitignore_vault()` appends `.specweaver/vault.env` to the project's `.gitignore` via `NativeIgnoreIOHandler`, idempotently (checks the line isn't already present first). A new `_scaffold_gitignore_sandbox()` mirrors this exactly for `.specweaver/.sandbox/`.
- **Factory/atom call sites for `QARunnerAtom`** (4 total, `grep -rn "QARunnerAtom("` across `src/`): `core/flow/handlers/validation.py:407`, `core/flow/handlers/lint_fix.py:215`, `core/flow/handlers/validation_hydrator.py:80`, `sandbox/qa_runner/interfaces/facades.py:180`. Per the Phase 4 HITL resolution (#8), only the first two are wired for SF-01.
- **Test file locations, confirmed by direct search** (not assumed): `tests/unit/core/flow/handlers/test_validate_tests_handler.py`, `tests/unit/core/flow/handlers/test_lint_fix_handler.py`, `tests/unit/core/config/test_settings_loader.py` (no per-section nesting convention in `core/config`, unlike `sandbox`'s doubled-segment convention), `tests/unit/sandbox/qa_runner/core/qa_runner/test_atom.py`, `tests/unit/sandbox/language/core/language/python/test_runner.py`. No existing `test_factory.py` for `qa_runner/core/factory.py` — a new one is added (direct unit coverage for the widened DI signature, since none existed before).
- **Existing D-EXEC-01 GHCR publish pipeline**: the repo-root `Containerfile` + CI publish a `sw serve` deployment image. A new sandbox base image is a **separate** artifact (see Backlog) — its `Containerfile.sandbox` is included as a static, declarative Proposed Change (same category as the existing root `Containerfile`), but the CI workflow that builds+publishes it to GHCR is explicitly deferred (mirrors the Phase-4-resolved scope cut on CI provisioning, finding #10) — `dev`-skill TDD doesn't touch CI YAML.

## Resolved Audit Findings

(Full audit ran across Phase 2–4 of the implementation-plan skill; presented via artifact, user replied "proceed with all proposals." All 11 findings are resolved as follows and merged into the plan below.)

1. **(#1, HIGH)** `run_architecture_check`'s host-side `shutil.which("tach")` pre-check is made conditional on `not isinstance(self._executor, ContainerSubprocessExecutor)` — skipped in container mode, letting the containerized `tach check` invocation's own exit/stderr signal absence (existing `OSError`→stderr path already handles it).
2. **(#2, HIGH)** Engine detection is existence (`shutil.which`) **plus** a liveness probe (`podman info`/`docker info`), cached once per `ContainerSubprocessExecutor` instance (lazy, on first `execute()` call) — not re-probed per invocation.
3. **(#3, HIGH)** Container name = `f"specweaver-qa-{run_id}-{uuid4().hex[:8]}"` — `run_id` alone is insufficient since one `run_id` can span multiple sequential QA calls within a pipeline run.
4. **(#4, MEDIUM)** `SandboxSettings` ships **only** `execution_mode: Literal["host", "container"] = "host"` for SF-01 — no `engine`/`image` override fields (YAGNI; revisit if SF-02 needs its own settings anyway).
5. **(#5, MEDIUM)** Scratch/cache directories are project-local: `<project_root>/.specweaver/.sandbox/{scratch,cache}/`, created lazily by `ContainerSubprocessExecutor` on first use (not eagerly scaffolded at `sw init`), with a new `.gitignore` entry scaffolded eagerly (mirrors `vault.env`'s precedent — see Research Notes).
6. **(#6, MEDIUM)** SpecWeaver publishes an official minimal sandbox image family (`python:3.11/3.12/3.13-slim` + `uv` preinstalled, nothing project-specific baked in). SF-01 ships the declarative `Containerfile.sandbox`; the CI build+publish automation is deferred (Backlog), consistent with #10's scope cut.
7. **(#7, MEDIUM)** Engine-unavailable failures raise a new `ContainerEngineUnavailableError`, caught once per `PythonQARunner` method (all 6), converted into the same kind of synthetic-failure result each method already builds for its `<timeout>` case (e.g. `TestFailure(nodeid="<sandbox>", message=...)`, matching the existing pattern at `runner.py:188`).
8. **(#8, MEDIUM)** `validation_hydrator.py` and `facades.py` are left unwired for SF-01 (logged in Backlog, not silently dropped) — only `validation.py`/`lint_fix.py`'s `_get_atom` methods are updated.
9. **(#9, MEDIUM)** `factory.resolve_runner`'s DI seam is widened generically for all 5 languages, but the "is this runner class Python?" check and its accompanying WARNING log for non-Python + container-mode combinations live **once, centrally, in `factory.py`** — not duplicated across 4 language-runner files.
10. **(#10, LOW)** CI provisioning of a real container engine for integration/e2e tests: out of scope for this plan's file list, Backlog item.
11. **(#11, LOW)** `specweaver.toml` user-facing reference: dev-guide extension only (already in the design doc); no separate canonical "all TOML sections" user doc was found to require updating.

## Proposed Changes

| File | Change | Purpose |
|------|--------|---------|
| `src/specweaver/sandbox/execution/container_executor.py` | `[NEW]` | `ContainerSubprocessExecutor(SubprocessExecutor)` + `ContainerEngineUnavailableError` |
| `src/specweaver/sandbox/execution/models.py` | `[MODIFY]` | Add `ContainerMounts` frozen dataclass (`source_root`, `scratch_root`, `cache_root`) |
| `src/specweaver/sandbox/qa_runner/core/factory.py` | `[MODIFY]` | Widen `resolve_runner(cwd, executor=None)`; central non-Python + container-mode WARNING log |
| `src/specweaver/sandbox/qa_runner/core/atom.py` | `[MODIFY]` | `QARunnerAtom.__init__` gains `sandbox_settings: SandboxSettings \| None = None`; builds `ContainerSubprocessExecutor` when `execution_mode == "container"` |
| `src/specweaver/sandbox/language/core/python/runner.py` | `[MODIFY]` | Conditional `tach` pre-check skip; catch `ContainerEngineUnavailableError` in all 6 methods; artifact-path redirection to `/scratch` when containerized |
| `src/specweaver/core/config/settings.py` | `[MODIFY]` | Add `SandboxSettings(BaseModel)`; add `sandbox: SandboxSettings = SandboxSettings()` to `SpecWeaverSettings` |
| `src/specweaver/core/config/settings_loader.py` | `[MODIFY]` | Add `_load_toml_sandbox(root_path)`; thread into `load_settings_async()` |
| `src/specweaver/core/config/context.yaml` | `[MODIFY]` | Add `SandboxSettings` to `exposes:` |
| `src/specweaver/core/flow/handlers/validation.py` | `[MODIFY]` | `ValidateTestsHandler._get_atom` passes `sandbox_settings=context.config.sandbox if context.config else None` |
| `src/specweaver/core/flow/handlers/lint_fix.py` | `[MODIFY]` | Same as above for `LintFixHandler._get_atom` |
| `src/specweaver/workspace/project/scaffold.py` | `[MODIFY]` | New `_scaffold_gitignore_sandbox()`, called from `scaffold_project()` alongside the existing vault call |
| `Containerfile.sandbox` (repo root) | `[NEW]` | Declarative multi-stage image spec: `python:3.1{1,2,3}-slim` + `uv`, no project-specific bake |
| `tests/unit/sandbox/execution/test_container_executor.py` | `[NEW]` | Unit tests for `ContainerSubprocessExecutor` (mocked at `super().execute()` boundary — no real container spawn) |
| `tests/unit/sandbox/qa_runner/core/qa_runner/test_factory.py` | `[NEW]` | DI-passthrough tests for the widened `resolve_runner` signature |
| `tests/unit/sandbox/qa_runner/core/qa_runner/test_atom.py` | `[MODIFY]` | `sandbox_settings` → executor selection tests |
| `tests/unit/sandbox/language/core/language/python/test_runner.py` | `[MODIFY]` | Conditional tach-precheck-skip test; `ContainerEngineUnavailableError` → synthetic-failure test |
| `tests/unit/core/config/test_settings_loader.py` | `[MODIFY]` | `_load_toml_sandbox`/`SandboxSettings` tests |
| `tests/unit/core/flow/handlers/test_validate_tests_handler.py` | `[MODIFY]` | `sandbox_settings` passthrough test |
| `tests/unit/core/flow/handlers/test_lint_fix_handler.py` | `[MODIFY]` | `sandbox_settings` passthrough test |
| `tests/integration/sandbox/execution/test_container_executor_integration.py` | `[NEW]` | Real `podman`/`docker` run, `@pytest.mark.integration`, `skipif` no engine detected |

## Implementation Sequence (pseudocode)

### `container_executor.py`

`ContainerEngineUnavailableError(Exception)` — raised when neither engine is detected+live.

`ContainerMounts` (in `models.py`): frozen dataclass, `source_root: Path`, `scratch_root: Path`, `cache_root: Path`.

`ContainerSubprocessExecutor(SubprocessExecutor)`:
1. `__init__(self, cwd, mounts: ContainerMounts, image: str | None = None, timeout_seconds=120, resource_limits=None)`: call `super().__init__(cwd=cwd, timeout_seconds=timeout_seconds, resource_limits=resource_limits)`; validate `mounts.source_root` via `ReadOnlyWorkspaceBoundary(api_paths=[mounts.source_root])`, `mounts.scratch_root`/`cache_root` via `WorkspaceBoundary(roots=[...])` (AD-3); create `scratch_root`/`cache_root` on disk if missing (`mkdir(parents=True, exist_ok=True)`); resolve `image` if `None` by reading `requires-python` from `cwd / "pyproject.toml"` (best-effort regex/`tomllib` parse; map to closest of `{3.11, 3.12, 3.13}`, default `3.13` on absence/parse failure); store `self._engine: str | None = None` (unresolved).
2. `_ensure_engine(self) -> str` (lazy, memoized): if `self._engine` is set, return it. Else, for `"podman"` then `"docker"`: resolve via `shutil.which(name)` (absolute path, never the bare string — mirrors the documented `special_patterns_and_adaptations.md` lesson and the existing `bash`/`tach` precedent); if found, run a liveness probe (`[resolved_path, "info"]`) through `super().execute(..., timeout_seconds=5)`; if `exit_code == 0`, memoize and return. If neither engine is live, raise `ContainerEngineUnavailableError` naming both attempted engines.
3. `_ensure_prepared(self) -> None`: compute a hash of `cwd / "uv.lock"` (fallback `pyproject.toml`) if present; compare against a stamp file under `cache_root / ".prepared_hash"`; if unchanged, return immediately. Else run a **network-enabled** prepare container (`--network` default, i.e. omit `--network none`) invoking `uv sync` with `cwd`'s source mounted RO at `/workspace`, `cache_root` mounted RW at `/cache` (`UV_CACHE_DIR=/cache`), no scratch mount, no LLM-generated code executed — write the new hash to the stamp file on success (AD-7/AD-9's two-phase split).
4. `execute(self, cmd, *, timeout_seconds=None, extra_env=None, cwd_override=None, input_text=None) -> SubprocessResult` (override): call `self._ensure_engine()` (propagates `ContainerEngineUnavailableError`); call `self._ensure_prepared()`; build `name = f"specweaver-qa-{run_id}-{uuid4().hex[:8]}"` (`run_id` passed at construction or defaulted to a short random token if absent — see atom.py wiring below); pre-emptively `[engine, "rm", "-f", name]` via `super().execute(...)`, ignoring its result (idempotent, AD-8); build the wrapped argv (see below); call `result = super().execute(wrapped, timeout_seconds=timeout_seconds, input_text=input_text)` — note `cwd_override`/`extra_env` are NOT forwarded to `super().execute()` as-is: `extra_env` entries become `-e KEY=VAL` flags baked into `wrapped` (they must reach the *container's* env, not the local CLI client's); `cwd_override` is not meaningful for a container invocation and is ignored with a `logger.warning` if non-`None`; in a `finally` block, run `[engine, "rm", "-f", name]` again via `super().execute()` unconditionally (post-run cleanup, AD-8), swallowing any error from the cleanup call itself (never let cleanup-failure mask the real result).
5. `_build_container_cmd(self, name, cmd, extra_env) -> list[str]`: `[engine, "run", "--rm", "--name", name, "--read-only", "-v", f"{source_root}:/workspace:ro", "-v", f"{scratch_root}:/scratch:rw", "--tmpfs", "/tmp:size=100m,mode=1777", "--network", "none", "--cap-drop", "ALL", "--security-opt", "no-new-privileges:true", "--memory", "2147483648", "--pids-limit", "128", *user_flag, *(f"-e" then f"{k}={v}" for k, v in (extra_env or {}).items()), "--workdir", "/workspace", image, *cmd]`.
   - **`user_flag` (NFR-4 — non-root, not deferred; see correction below)**: on non-Windows (`sys.platform != "win32"`), `["--user", f"{os.getuid()}:{os.getgid()}"]`. This is tractable at low complexity specifically because `scratch_root`/`cache_root` are created by `ContainerSubprocessExecutor.__init__` itself (step 1, `mkdir(parents=True, exist_ok=True)`) as the invoking host user — there is no separate UID to reconcile, the container simply runs as the same UID that already owns every mount it touches. On Windows (`sys.platform == "win32"`, where `os.getuid()` doesn't exist), `user_flag = []` — falls back to the container image's default (root) — consistent with NFR-11's already-agreed Linux-primary scope (Windows/VM-backed engines are best-effort, not a completion blocker); log a one-time `logger.warning` in this branch so the gap is visible, not silent.

> [!NOTE]
> This is an implementation sequence for the `dev` skill's TDD loop, not code to paste. Write failing tests first (Test Plan below), then implement to green.

### `qa_runner/core/atom.py` + `factory.py`

1. `factory.resolve_runner(cwd: Path, executor: SubprocessExecutor | None = None) -> QARunnerInterface`: thread `executor` through to whichever language-runner constructor is selected (all 5 already accept it). After selection, if `executor` is a `ContainerSubprocessExecutor` and the selected class is not `PythonQARunner`, `logger.warning("container sandboxing is validated for Python projects only; %s may not have its toolchain available in the sandbox image", runner.language_name)` — centralizes finding #9's warning in one place.
2. `QARunnerAtom.__init__(self, cwd: Path, language: str = "python", sandbox_settings: SandboxSettings | None = None) -> None`: if `sandbox_settings is None or sandbox_settings.execution_mode == "host"`, behavior is byte-for-byte identical to today (`executor=None` passed to `resolve_runner`, preserving NFR-7). Else, build `mounts = ContainerMounts(source_root=cwd, scratch_root=cwd/".specweaver"/".sandbox"/"scratch", cache_root=cwd/".specweaver"/".sandbox"/"cache")`, construct `ContainerSubprocessExecutor(cwd=cwd, mounts=mounts)`, pass it as `executor=` to `resolve_runner`.

### `settings.py` + `settings_loader.py` + `context.yaml`

1. `SandboxSettings(BaseModel)`: single field `execution_mode: Literal["host", "container"] = "host"`. Add `sandbox: SandboxSettings = SandboxSettings()` to `SpecWeaverSettings`, matching the `stitch`/`standards` field pattern exactly.
2. `_load_toml_sandbox(root_path: str | None) -> SandboxSettings`: byte-for-byte mirror of `_load_toml_standards` — read `specweaver.toml`, `toml_data.get("sandbox", {})`, construct `SandboxSettings(**data)` inside the same try/except-log-and-default pattern. Call it in `load_settings_async()` alongside the existing `standards = _load_toml_standards(...)` line; thread `sandbox=sandbox` into the final `SpecWeaverSettings(...)` construction.
3. `core/config/context.yaml`: add `SandboxSettings` to the `exposes:` list (alongside `ValidationSettings`, `LLMSettings`).

### `validation.py` / `lint_fix.py`

`_get_atom(self, context: RunContext) -> QARunnerAtom`: `sandbox_settings = context.config.sandbox if context.config else None`; return `QARunnerAtom(cwd=context.project_path, sandbox_settings=sandbox_settings)`.

### `scaffold.py`

`_scaffold_gitignore_sandbox(project_path: Path) -> None`: byte-for-byte mirror of `_scaffold_gitignore_vault` — check `.gitignore` for the literal line `.specweaver/.sandbox/`, append via `NativeIgnoreIOHandler` if absent. Call from `scaffold_project()` alongside the existing `_scaffold_gitignore_vault(project_path)` call.

### `Containerfile.sandbox`

A small, declarative multi-stage-free Containerfile (matching the style of the existing root `Containerfile`, not authored as TDD code): `ARG PY_VERSION=3.13`, `FROM python:${PY_VERSION}-slim`, install `uv` (pinned version, same mechanism the root `Containerfile` already uses), create a non-root user, no `ENTRYPOINT`/`CMD` (the wrapped `podman run ... image *cmd` invocation supplies the command every time — this image is a toolchain base, not a service).

## Test Plan

| Test | FR/NFR | Asserts |
|------|--------|---------|
| `test_engine_detection_prefers_podman` | FR-6, AD-6 | Both engines "available" (mocked `shutil.which`) → `podman` selected |
| `test_engine_detection_falls_back_to_docker` | FR-6 | Only `docker` available → `docker` selected |
| `test_engine_detection_cached_after_first_call` | Finding #2 | `shutil.which`/liveness probe called once across 2 `execute()` calls on the same instance |
| `test_engine_unavailable_raises_typed_error` | FR-7, Finding #7 | Neither engine on PATH → `ContainerEngineUnavailableError`, message names both engines |
| `test_engine_on_path_but_not_live_raises` | Finding #2 | `shutil.which` finds binary, liveness probe (`info`) returns nonzero → `ContainerEngineUnavailableError` |
| `test_read_only_source_mount_flag_present` | FR-2, NFR-2 | Wrapped argv contains `-v {source}:/workspace:ro` and `--read-only` |
| `test_writable_scratch_mount_flag_present` | FR-3, NFR-2 | Wrapped argv contains `-v {scratch}:/scratch:rw`, distinct from the source mount |
| `test_network_none_by_default` | NFR-3, AD-9 | Wrapped argv contains `--network none` for the execute phase (not the prepare phase) |
| `test_non_root_capabilities_dropped` | NFR-4 | Wrapped argv contains `--cap-drop ALL`, `--security-opt no-new-privileges:true` |
| `test_user_flag_matches_invoking_uid_on_linux` | NFR-4 | On non-Windows, wrapped argv contains `--user {os.getuid()}:{os.getgid()}` |
| `test_user_flag_omitted_on_windows_with_warning` | NFR-4, NFR-11 | On Windows (mocked `sys.platform`), `--user` is absent from wrapped argv and a warning is logged |
| `test_resource_limits_match_bash_action_atom_defaults` | NFR-5, AD-4 | Wrapped argv contains `--memory 2147483648`, `--pids-limit 128` |
| `test_deterministic_name_includes_run_id_and_uuid_suffix` | Finding #3 | Container name matches `specweaver-qa-{run_id}-{8 hex chars}` |
| `test_cleanup_runs_before_and_after_execution` | FR-8, NFR-6, AD-8 | Two `rm -f {name}` calls observed (pre-run idempotent + post-run `finally`), regardless of success/failure/timeout |
| `test_cleanup_runs_on_super_execute_exception` | AD-8 | `super().execute()` raising → cleanup `finally` block still fires |
| `test_extra_env_becomes_dash_e_flags_not_host_env` | Research Notes | `extra_env={"X": "1"}` → `-e X=1` present in wrapped argv, NOT forwarded to `super().execute()`'s own `extra_env` param |
| `test_cwd_override_ignored_with_warning` | Research Notes | `cwd_override` passed → logged warning, no crash, container still runs against the constructor's `source_root` |
| `test_prepare_phase_skipped_when_lockfile_hash_unchanged` | AD-7 | Stamp file present + matching hash → no `uv sync` container invocation |
| `test_prepare_phase_reruns_on_lockfile_change` | AD-7 | Stamp file hash mismatch → `uv sync` invoked, stamp updated |
| `test_prepare_phase_has_network_execute_phase_does_not` | AD-9 | Prepare-phase argv omits `--network none`; execute-phase argv includes it |
| `test_image_defaults_from_requires_python` | Implementation Sequence §1 | `pyproject.toml` with `requires-python = ">=3.12"` → image tag resolves to `3.12`; absent/unparseable → `3.13` default |
| `test_result_contract_unchanged_shape` | FR-5 | Returned object is a `SubprocessResult` with the same fields as host-mode, `PythonQARunner`'s parsing logic needs no branching |
| `test_tach_precheck_skipped_in_container_mode` | Finding #1 | `PythonQARunner` with a `ContainerSubprocessExecutor` → `shutil.which("tach")` NOT called on the host |
| `test_tach_precheck_still_runs_in_host_mode` | Finding #1 | `PythonQARunner` with a plain `SubprocessExecutor` → host-side `shutil.which("tach")` check unchanged |
| `test_container_engine_unavailable_becomes_synthetic_failure` | Finding #7 | `ContainerEngineUnavailableError` raised during `run_tests` → returns a `TestRunResult` with a `<sandbox>`-nodeid `TestFailure`, not an unhandled exception |
| `test_resolve_runner_threads_executor_to_python` | FR-1, AD-2 | `factory.resolve_runner(cwd, executor=mock)` → `PythonQARunner._executor is mock` |
| `test_resolve_runner_warns_on_non_python_container_executor` | Finding #9 | `resolve_runner` with a TS-project cwd + a `ContainerSubprocessExecutor` → warning logged, `TypeScriptRunner` still constructed (no crash, no silent no-op) |
| `test_qa_runner_atom_host_mode_default_unchanged` | FR-9, NFR-7 | `QARunnerAtom(cwd=...)` (no `sandbox_settings`) → behavior/executor identical to pre-SF-01 |
| `test_qa_runner_atom_container_mode_builds_container_executor` | FR-1, AD-2 | `QARunnerAtom(cwd=..., sandbox_settings=SandboxSettings(execution_mode="container"))` → `ContainerSubprocessExecutor` constructed with mounts derived from `cwd` |
| `test_load_toml_sandbox_parses_execution_mode` | Data model (Finding #4) | `specweaver.toml` with `[sandbox]\nexecution_mode = "container"` → `SandboxSettings(execution_mode="container")` |
| `test_load_toml_sandbox_defaults_on_missing_section` | NFR-7 | No `[sandbox]` table → `SandboxSettings()` (host default) |
| `test_load_toml_sandbox_defaults_on_parse_error` | Error handling | Malformed TOML → logged exception, default `SandboxSettings()`, no crash |
| `test_validate_tests_handler_passes_sandbox_settings` | Pipeline integration | `RunContext.config.sandbox` set → `QARunnerAtom` receives it |
| `test_lint_fix_handler_passes_sandbox_settings` | Pipeline integration | Same, for `LintFixHandler` |
| `test_scaffold_gitignore_sandbox_appends_once` | Finding #5 | `.gitignore` gets `.specweaver/.sandbox/` appended; re-running scaffold doesn't duplicate the line |
| **Integration** `test_real_container_execution_round_trip` | FR-1..FR-8 | Real `podman`/`docker run` (skip if neither engine detected+live), executes a trivial fixture command, asserts RO-mount write attempt fails, RW-scratch write succeeds, container removed after |

## FR / NFR / AD Coverage

| ID | Covered by |
|----|-----------|
| FR-1 | `ContainerSubprocessExecutor` construction gated on `execution_mode`; tests: `test_qa_runner_atom_container_mode_builds_container_executor`, `test_resolve_runner_threads_executor_to_python` |
| FR-2 | `--read-only` + `-v source:/workspace:ro`; test: `test_read_only_source_mount_flag_present` |
| FR-3 | `-v scratch:/scratch:rw`; test: `test_writable_scratch_mount_flag_present` |
| FR-4 | Artifact-path redirection in `runner.py` (COVERAGE_FILE/junitxml/cache-dir/PYTHONDONTWRITEBYTECODE → `/scratch`) — covered by the integration round-trip test (host-level unit mocking can't meaningfully assert real file writes land under `/scratch`) |
| FR-5 | `super().execute()` return value passed through unchanged; test: `test_result_contract_unchanged_shape` |
| FR-6 | Engine auto-detection + rootless-Podman preference; tests: `test_engine_detection_prefers_podman`, `test_engine_detection_falls_back_to_docker` |
| FR-7 | `ContainerEngineUnavailableError`; tests: `test_engine_unavailable_raises_typed_error`, `test_engine_on_path_but_not_live_raises`, `test_container_engine_unavailable_becomes_synthetic_failure` |
| FR-8 | Pre/post `rm -f`; tests: `test_cleanup_runs_before_and_after_execution`, `test_cleanup_runs_on_super_execute_exception` |
| FR-9 | `QARunnerAtom` default-`None` `sandbox_settings`; test: `test_qa_runner_atom_host_mode_default_unchanged` |
| NFR-1 | Engine-liveness caching (#2) keeps steady-state overhead low; not independently unit-tested (a latency assertion in a mocked test is meaningless) — validated qualitatively during the integration round-trip test's wall-clock, noted in Backlog as a manual perf check |
| NFR-2 | `--read-only` + scoped mounts; test: `test_read_only_source_mount_flag_present` |
| NFR-3 | `--network none` on execute phase only; test: `test_network_none_by_default`, `test_prepare_phase_has_network_execute_phase_does_not` |
| NFR-4 | `--cap-drop ALL --security-opt no-new-privileges` + non-root `--user` matching the invoking host UID/GID on non-Windows (corrected into scope — see Post-Planning Correction below); tests: `test_non_root_capabilities_dropped`, `test_user_flag_matches_invoking_uid_on_linux`, `test_user_flag_omitted_on_windows_with_warning` |
| NFR-5 | `--memory`/`--pids-limit` matching `BashActionAtom`; test: `test_resource_limits_match_bash_action_atom_defaults` |
| NFR-6 | Pre+post `rm -f`, not `--rm` alone; tests: `test_cleanup_runs_before_and_after_execution`, `test_cleanup_runs_on_super_execute_exception` |
| NFR-7 | Default `execution_mode="host"` byte-identical behavior; tests: `test_qa_runner_atom_host_mode_default_unchanged`, `test_load_toml_sandbox_defaults_on_missing_section` |
| NFR-8 | `logger.info` of engine/image/mounts — implemented inline in `execute()`, not separately unit-tested beyond existing logging conventions (matches how `SubprocessExecutor.execute()`'s own `logger.debug` call isn't separately tested either) |
| NFR-9 | Typed `ContainerEngineUnavailableError`, distinguishable from a real test failure; test: `test_container_engine_unavailable_becomes_synthetic_failure` |
| NFR-10 | Unit tests mock at `super().execute()`; integration test `skipif`s when no engine; CI provisioning itself is Backlog (#10) |
| NFR-11 | Native-Linux-primary scope; non-root `--user` mapping explicitly deferred (see Implementation Sequence §5 note) — no Windows-specific test added, consistent with the resolved scope |
| AD-1 | `ContainerSubprocessExecutor(SubprocessExecutor)` subclass, overriding only `execute()` |
| AD-2 | `factory.resolve_runner`/`QARunnerAtom.__init__` DI widening; tests throughout |
| AD-3 | `ReadOnlyWorkspaceBoundary`/`WorkspaceBoundary` reuse for mount validation |
| AD-4 | `BashActionAtom`'s 2 GiB/128-process defaults reused verbatim |
| AD-5 | Artifact-path redirection (FR-4) |
| AD-6 | Podman-preferred engine ordering; test: `test_engine_detection_prefers_podman` |
| AD-7 | Prepare/execute phase split + lockfile-hash gating; tests: `test_prepare_phase_skipped_when_lockfile_hash_unchanged`, `test_prepare_phase_reruns_on_lockfile_change` |
| AD-8 | Deterministic name + pre/post `rm -f`; tests: `test_deterministic_name_includes_run_id_and_uuid_suffix`, `test_cleanup_runs_before_and_after_execution` |
| AD-9 | Network split between phases; test: `test_prepare_phase_has_network_execute_phase_does_not` |

## Backlog (deferred, out of scope for SF-01)

- **CI container-engine provisioning** (NFR-10, Finding #10): integration/e2e tests `skipif` cleanly today without it, but the containerized path won't actually be exercised in CI until a runner with Podman/Docker is provisioned. Ops follow-up, not `dev`-skill code.
- **`Containerfile.sandbox` CI build+publish automation** (Finding #6): the declarative image spec ships with SF-01; the GitHub Actions workflow to build and push it to GHCR (alongside the existing `D-EXEC-01` `sw serve` image pipeline) is a separate follow-up. Until it ships, `execution_mode: "container"` requires an operator to build `Containerfile.sandbox` locally and tag it to match SF-01's resolved image-name convention.
- **`validation_hydrator.py` / `facades.py` container wiring** (Finding #8): the other 2 of 4 `QARunnerAtom` call sites; deferred for scope discipline, same treatment as `run_debugger`'s deferred containerization in the design doc.
- **`run_debugger` containerization**: already flagged in the design doc's Refactoring Opportunities as a fast-follow, not part of SF-01.
- **`engine`/`image` override fields on `SandboxSettings`** (Finding #4): add if/when a real need surfaces (e.g. from SF-02's network-policy work).
- **NFR-1 latency validation**: no automated perf assertion; manually time a warm-image containerized run vs. host-mode during pre-commit and note the delta in the walkthrough.

## Post-Planning Correction (pre-approval)

The original Phase-4-resolved draft of this plan deferred non-root `--user` UID/GID mapping to Backlog "as a follow-up spike," reasoning it needed a general host-UID↔container-UID mapping strategy. On review, this was wrong on two counts: (1) the design doc's own **NFR-4** already states the container "SHALL run as a non-root user" — a hard requirement approved before this plan existed, not a discretionary nice-to-have this plan was free to defer; (2) the perceived complexity was for the *general* case (arbitrary container UID vs. arbitrary mount owner), which doesn't apply here — `ContainerSubprocessExecutor` creates `scratch_root`/`cache_root` itself, as the invoking host user, so running the container `--user`-pinned to that same UID/GID has no ownership mismatch to solve on native Linux (NFR-11's already-agreed primary target). Folded back into scope: Implementation Sequence §5 (`user_flag` construction), Test Plan (2 new tests), and the NFR-4 coverage row above. Not promoted to SF-02/SF-03 or a separate TECH story — it isn't a technical blocker for either (neither touches container identity), but it's cheaper to land correctly now, in the same file, than to reopen `_build_container_cmd` after more logic depends on it.

## Phase 5: Final Consistency Check

**5.0 Pre-check**: All 9 FRs, all 11 NFRs, and all 9 ADs from the design doc's SF-01 scope are accounted for in the coverage table above.

**5.1 Open questions**: None remaining — all 11 Phase 4 findings were resolved via the user's "proceed with all proposals," and every resolution is merged into Research Notes / Resolved Audit Findings / Implementation Sequence / Backlog above.

**5.1a Agent Handoff Risk**: A fresh agent starting only from this document has: the exact subclass boundary (`ContainerSubprocessExecutor(SubprocessExecutor)`, override `execute()` only), the exact wrapped-argv shape (Implementation Sequence §5), the exact 4-call-site scope cut (2 wired, 2 explicitly deferred with reasons), and the exact test file paths (confirmed via direct search, not assumed). The one thing left genuinely open for implementation-time judgment: the precise regex/`tomllib` logic for parsing `requires-python` version constraints into a `{3.11, 3.12, 3.13}` tag — described at the algorithm level (Implementation Sequence §1), not fully pinned to exact string-parsing code, since that's a mechanical `dev`-skill detail, not a design decision.

**5.2 Architecture and future compatibility**: No circular imports — `container_executor.py` imports only from its own sibling `executor.py`/`models.py` and `sandbox.security`; `qa_runner/core/{atom,factory}.py` import `sandbox.execution.container_executor` (existing, already-legal direction, sandbox-internal); `core/config/{settings,settings_loader}.py` gain a pure-data model with no new I/O mechanism reaching into `sandbox` (the `forbids: specweaver/sandbox/*` rule in `core/config/context.yaml` is respected — `config` never imports `sandbox`, only the reverse); `core/flow/handlers/{validation,lint_fix}.py` read an already-present `RunContext.config` field, no new import needed beyond a `TYPE_CHECKING`-guarded type hint. No `tach.toml` change required (internal sandbox-to-sandbox wiring, confirmed in Research Notes). Compatible with `SF-02`/`SF-03`/`SF-04` (all attach to this SF's `ContainerSubprocessExecutor`/mount contract per the design doc).

**5.2a Architecture Principles**: **DDD** — stays within `sandbox` + the already-established `core.config`↔`core.flow` relationship; no new bounded context. **KISS** — one subclass overriding one method; no speculative abstraction layer for "pluggable container engines" beyond the two (podman/docker) actually needed. **DRY** — reuses `SubprocessExecutor`, `WorkspaceBoundary`/`ReadOnlyWorkspaceBoundary`, `BashActionAtom`'s resource-limit numbers, and the `_load_toml_standards`/`_scaffold_gitignore_vault` patterns verbatim rather than reinventing any of them. **Hexagonal** — `ContainerSubprocessExecutor` is itself an adapter; no domain logic leaks into it. **Separation of Concerns** — mount/engine/cleanup concerns live entirely in the new executor; `PythonQARunner` only gains the minimal conditional logic (tach pre-check skip, exception catch, artifact-path redirection) it structurally cannot avoid owning itself.

**5.3 Internal consistency**: Every FR/NFR/AD maps to at least one concrete change and at least one test. The 20-file Proposed Changes list matches every file referenced in Research Notes, Resolved Audit Findings, and Implementation Sequence — no orphaned references.

### Red/Blue Team Review (2 cycles run)

**Cycle 1** —
- 🔴 **HIGH**: `_ensure_prepared()`'s lockfile-hash stamp file lives under `cache_root` (`.specweaver/.sandbox/cache/.prepared_hash`) — but `cache_root` is also the mount target for the prepare-phase container's `UV_CACHE_DIR`. Does `uv sync` ever wipe or reorganize the directory it's pointed at as a cache dir in a way that could delete the stamp file, causing every subsequent run to needlessly re-prepare (correctness-safe, but silently defeats the whole amortization point of AD-7)? **Blue**: VALID — FIX REQUIRED. Store the stamp file in a *sibling* location, not inside the directory passed as `UV_CACHE_DIR` itself — e.g. `.specweaver/.sandbox/.prepared_hash` (one level up, alongside `scratch/`/`cache/`, not inside `cache/`). Updated Implementation Sequence §3 wording above already reflects this (stamp file is described as living at `cache_root / ".prepared_hash"` — **correcting now**: it should be a sibling of `cache_root`, not inside it). Noted as a required fix to §3's description before Phase 5 sign-off.
- 🔴 **MEDIUM**: The central non-Python-warning in `factory.py` (finding #9's resolution) — does it fire even in **host mode**, where a `ContainerSubprocessExecutor` was never constructed at all? **Blue**: INVALID — NO ACTION. The warning check (`isinstance(executor, ContainerSubprocessExecutor)`) is inherently `False` for the default `None`/plain-`SubprocessExecutor` host-mode path — it can only ever fire when a `ContainerSubprocessExecutor` was actually passed in, which only happens via `QARunnerAtom`'s container-mode branch. No fix needed, already correctly scoped by construction.
- 🔴 **LOW**: `_build_container_cmd`'s `--memory`/`--pids-limit` values are hardcoded integers matching `BashActionAtom`'s constants, duplicated rather than imported from a shared location. **Blue**: VALID — ACCEPTED as a Backlog item (already listed: "extract a shared `ResourceLimits`/`MountSpec` value object," design doc's Refactoring Opportunities) — not worth a cross-cutting refactor inside this already-large SF; duplication of two integer literals is a low-cost, explicitly-tracked debt, not a defect.

**Cycle 2** — re-examined Cycle 1's fix plus a fresh pass:
- 🔴 **MEDIUM**: With the stamp file corrected to live alongside (not inside) `cache_root`, is there a TOCTOU race if two pipeline steps under the *same* `run_id` (e.g. `run_linter` then `run_tests` in a lint-fix reflection loop) both call `_ensure_prepared()` concurrently against the same stamp file? **Blue**: VALID — ACCEPTED RISK, not a fix. `QARunnerAtom`'s own methods are invoked sequentially within a single pipeline run today (no evidence of concurrent `execute()` calls from the *same* atom instance) — this only becomes a real hazard under `C-FLOW-03` fan-out running fully independent `run_id`s in parallel, and each of those has its own independent project checkout / worktree per the existing Git Worktree Bouncer (`D-EXEC-02`) design, hence independent `cache_root` paths — no shared-file race across fan-out branches. Documented here as a verified-safe assumption, not silently glossed over.
- No new findings below the continuation threshold (0 CRITICAL, 0 HIGH, 1 MEDIUM, 0 LOW this cycle). Review converges.

**Corrections made**: Implementation Sequence §3's stamp-file location corrected from "under `cache_root`" to "a sibling of `cache_root`" (`.specweaver/.sandbox/.prepared_hash`, not `.specweaver/.sandbox/cache/.prepared_hash`) — reflected in the description above. No other code-shape changes required.

---

## HITL Gate — Approval Required

This plan is ready for your review. Summary: 20 files (3 new source, 1 new declarative Containerfile, 8 modified source, 8 test files new/modified), zero changes to `tach.toml`, all 11 Phase-4-resolved findings merged, Red/Blue review ran 2 cycles and caught one real bug (stamp-file placement) before implementation started, and a post-planning correction restored non-root `--user` mapping into SF-01 scope (it was mistakenly deferred against the design doc's own NFR-4).

Reply with approval to mark this plan `APPROVED` and proceed to the `dev` skill for SF-01's TDD implementation.

---

## Commit Boundary 1 Progress Notes (in-progress — SF-01 continues to Commit Boundaries 2-4)

**Landed as planned** (T1-T6): `ContainerMounts` (`models.py`), `ContainerEngineUnavailableError` + `ContainerSubprocessExecutor` (`container_executor.py`) — engine detection/liveness caching, lazy mount-dir creation, `requires-python`-derived image tagging, `_build_container_cmd()`, `execute()` override with pre/post idempotent cleanup, `_ensure_prepared()`'s lockfile-hash-gated `uv sync` prepare phase.

**Deviation from the plan's original file placement**: none — `ContainerSubprocessExecutor` was placed flat at `sandbox/execution/container_executor.py` exactly as Research Notes specified (sibling to `executor.py`, not nested under `execution/core/`).

**Test coverage exceeded the plan**: the Phase 2 test-gap analysis (pre-commit gate) found 9 real branch gaps beyond the plan's original Test Plan table (version-clamping boundaries, a `TypeError` hostile-input path, `_ensure_engine`'s partial-fallback case, `uv sync` failure handling, the `pyproject.toml`-only prepare branch, and `input_text`/`timeout_seconds` forwarding) — all 9 implemented. The user additionally requested pulling the real-engine integration test forward from Commit Boundary 4 into Commit Boundary 1; `tests/integration/sandbox/execution/test_container_executor_integration.py` (5 tests) now exists and — since both Podman and Docker are live on the implementing machine — actually ran against a real engine rather than skipping, positively confirming RO-mount write-blocking, RW-scratch write-allowance, `--network none` egress-blocking, and post-execution container cleanup. Commit Boundary 4's own T16 entry in `task.md` is superseded by this file; no duplicate test will be added there.

**Documentation updated this commit**: `docs/dev_guides/subprocess_execution.md` (new "Containerized QA Execution" section — the guide this design doc's own "Developer Guides Required" table committed to), `docs/dev_guides/special_patterns_and_adaptations.md` (§23, the executor-subclassing pattern), `docs/dev_guides/testing_guide.md` (new external-tool-skip entry). **Deliberately NOT updated yet**: `README.md`'s "Zero-Trust Security" bullet, `master_story_roadmap.md`/`capability_matrix.md` status flips — both premature until `execution_mode: container` is reachable end-to-end (Commit Boundary 2+) and, for any `✅` status flip, until a passing e2e test exists to satisfy the roadmap's Proof Mandate. Will be addressed at SF-01's final commit boundary.
