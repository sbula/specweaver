# B-EXEC-01 SF-01 — Core Containerized Execution Engine

**Status**: APPROVED. Committed as `68c34359`. · **FRs owned**: FR-2, FR-3, FR-5, FR-6, FR-7,
FR-8 · **Depends on**: none · Design: [B-EXEC-01_design.md](B-EXEC-01_design.md) §Sub-features →
SF-01

## Goal

`ContainerSubprocessExecutor` — a `SubprocessExecutor` subclass that runs a command in an ephemeral
Podman/Docker container instead of on the host: RO source mount, RW scratch mount, `--network
none`, non-root `--user`, deterministic naming + guaranteed cleanup, and the AD-7/AD-9
prepare/execute split for `uv sync`. Self-contained; not yet wired into `QARunnerAtom` (SF-02).

- **Inputs**: host source root + a derived scratch/cache directory pair; installed
  `podman`/`docker` CLI.
- **Outputs**: a `SubprocessResult`-compatible response for any command, produced inside an
  ephemeral, auto-removed container.

## Where it plugs in

| Fact | Where |
|---|---|
| `QARunnerAtom` — the dispatcher | `src/specweaver/sandbox/qa_runner/core/atom.py:64` |
| `PythonQARunner` — the DI seam `executor: SubprocessExecutor \| None = None` | `src/specweaver/sandbox/language/core/python/runner.py:131` |
| `SubprocessExecutor` | `src/specweaver/sandbox/execution/executor.py:75` |
| `ResourceLimits`: frozen dataclass, `max_memory_bytes`, `max_processes`, `max_file_size_bytes`, all default `None` | `sandbox/execution/models.py` |
| `BashActionAtom` sets `ResourceLimits(max_memory_bytes=2_147_483_648, max_processes=128)` | `sandbox/execution/core/atom.py:24` |

- `SubprocessExecutor.execute()` (`sandbox/execution/executor.py:90`):
  `execute(cmd: list[str], *, timeout_seconds: int | None = None, extra_env: dict[str,str] | None = None, cwd_override: Path | None = None, input_text: str | None = None) -> SubprocessResult`.
  Constructor:
  `__init__(cwd: Path, timeout_seconds: int = 120, resource_limits: ResourceLimits | None = None, env_allowlist: frozenset[str] | None = None, strip_credentials: bool = True)`.
- `sandbox/security.py`: `WorkspaceBoundary(roots: list[Path], api_paths: list[Path] | None = None)`,
  `.validate_path(requested: Path) -> Path` (raises `WorkspaceBoundaryError`);
  `ReadOnlyWorkspaceBoundary(api_paths: list[Path])` — a subclass with no write roots,
  `.is_read_only` always `True`.
- **Limits apply to two different processes.** `resource_limits`/`preexec_fn`/Windows Job Objects
  on the parent limit the **local `podman`/`docker` CLI client**, not the containerized process.
  Container limits are `--memory`/`--pids-limit` flags in the wrapped argv. So AD-4's numbers go
  into those flags, not into a `ResourceLimits` passed to the parent.
- **Placement.** `execution/core/` (where `BashActionAtom` lives) holds Atom-tier orchestration;
  `SubprocessExecutor` sits flat at `execution/executor.py`. The new class is executor-tier, so it
  goes flat at **`sandbox/execution/container_executor.py`**. That also keeps it inside the TID251
  subprocess-import-ban exemption glob (`"src/specweaver/sandbox/execution/*.py"`, flat and
  non-recursive in `pyproject.toml`) — though it never imports raw `subprocess`, only
  `super().execute()`.
- **Mounts map onto the boundaries (AD-3).** `ReadOnlyWorkspaceBoundary(api_paths=[source_root])`
  validates the RO source; `WorkspaceBoundary(roots=[scratch_root, cache_root])` the RW mounts.
- **`MCPAtom`** (`sandbox/mcp/core/atom.py`) already enforces "must run through docker/podman"
  (`NFR-2 Boundary Violation` check on `command[0]`), documented in
  `mcp_implementation_patterns.md`. Not reusable: it validates an externally pre-built command and
  bridges long-lived bidirectional JSON-RPC over stdio. Precedent for the convention only.
- **tach.toml**: `specweaver.sandbox` is a **flat** tach module; sandbox-internal imports are not
  gated by `[[interfaces]]`. The consumers (SF-02's `qa_runner/core/factory.py`/`atom.py`) are
  inside `sandbox`, so **no `tach.toml` change**. `container_executor.py` imports only its siblings
  `executor.py`/`models.py` and `sandbox.security` — no cycles.

## Changes

`ContainerEngineUnavailableError(Exception)` — raised when neither engine is detected and live.

`ContainerMounts` (in `models.py`): frozen dataclass, `source_root: Path`, `scratch_root: Path`,
`cache_root: Path`.

`ContainerSubprocessExecutor(SubprocessExecutor)`:

1. `__init__(self, cwd, mounts: ContainerMounts, image: str | None = None, timeout_seconds=120, resource_limits=None)`:
   - call `super().__init__(cwd=cwd, timeout_seconds=timeout_seconds, resource_limits=resource_limits)`;
   - validate `mounts.source_root` via `ReadOnlyWorkspaceBoundary(api_paths=[mounts.source_root])`,
     `mounts.scratch_root`/`cache_root` via `WorkspaceBoundary(roots=[...])` (AD-3);
   - create `scratch_root`/`cache_root` if missing (`mkdir(parents=True, exist_ok=True)`);
   - if `image` is `None`, read `requires-python` from `cwd / "pyproject.toml"` (best-effort
     regex/`tomllib`), map to the closest of `{3.11, 3.12, 3.13}`, default `3.13` on absence or
     parse failure;
   - `self._engine: str | None = None` (unresolved).
2. `_ensure_engine(self) -> str` — lazy, memoized. For `"podman"` then `"docker"`: resolve via
   `shutil.which(name)` (absolute path, never the bare string); if found, liveness-probe
   `[resolved_path, "info"]` through `super().execute(..., timeout_seconds=5)`; on `exit_code == 0`
   memoize and return. Neither live → raise `ContainerEngineUnavailableError` naming both engines.
3. `_ensure_prepared(self) -> None` — hash `cwd / "uv.lock"` (fallback `pyproject.toml`) if
   present; compare with the stamp file `.specweaver/.sandbox/.prepared_hash`; unchanged → return.
   Else run a **network-enabled** prepare container (omit `--network none`) invoking `uv sync`:
   source RO at `/workspace`, `cache_root` RW at `/cache` (`UV_CACHE_DIR=/cache`), no scratch
   mount, no LLM-generated code. Write the new hash on success (AD-7/AD-9).
4. `execute(self, cmd, *, timeout_seconds=None, extra_env=None, cwd_override=None, input_text=None) -> SubprocessResult`
   (override):
   - `self._ensure_engine()` (propagates `ContainerEngineUnavailableError`), then
     `self._ensure_prepared()`;
   - `name = f"specweaver-qa-{run_id}-{uuid4().hex[:8]}"`;
   - pre-emptive `[engine, "rm", "-f", name]` via `super().execute(...)`, result ignored (AD-8);
   - `result = super().execute(wrapped, timeout_seconds=timeout_seconds, input_text=input_text)`;
   - `extra_env` becomes `-e KEY=VAL` flags inside `wrapped` — it must reach the *container's*
     env, not the local CLI client's;
   - `cwd_override` non-`None` → `logger.warning`, ignored;
   - `finally`: `[engine, "rm", "-f", name]` again via `super().execute()`, errors from the
     cleanup itself swallowed (AD-8).
5. `_build_container_cmd(self, name, cmd, extra_env) -> list[str]`:
   `[engine, "run", "--rm", "--name", name, "--read-only", "-v", f"{source_root}:/workspace:ro", "-v", f"{scratch_root}:/scratch:rw", "--tmpfs", "/tmp:size=100m,mode=1777", "--network", "none", "--cap-drop", "ALL", "--security-opt", "no-new-privileges:true", "--memory", "2147483648", "--pids-limit", "128", *user_flag, *(f"-e" then f"{k}={v}" for k, v in (extra_env or {}).items()), "--workdir", "/workspace", image, *cmd]`.
   - **`user_flag` (NFR-4)**: on non-Windows (`sys.platform != "win32"`),
     `["--user", f"{os.getuid()}:{os.getgid()}"]`. No ownership mismatch to solve:
     `ContainerSubprocessExecutor.__init__` creates `scratch_root`/`cache_root` as the invoking
     host user, so the container runs as the UID that owns every mount. On Windows,
     `user_flag = []` (image default/root) with a one-time `logger.warning`.

| File | Change | Purpose |
|------|--------|---------|
| `src/specweaver/sandbox/execution/container_executor.py` | `[NEW]` | `ContainerSubprocessExecutor(SubprocessExecutor)` + `ContainerEngineUnavailableError` |
| `src/specweaver/sandbox/execution/models.py` | `[MODIFY]` | Add `ContainerMounts` frozen dataclass (`source_root`, `scratch_root`, `cache_root`) |
| `tests/unit/sandbox/execution/test_container_executor.py` | `[NEW]` | Unit tests (mocked at `super().execute()` boundary — no real container spawn) |
| `tests/integration/sandbox/execution/test_container_executor_integration.py` | `[NEW]` | Real `podman`/`docker` run, `@pytest.mark.integration`, `skipif` no engine detected |

## Tests

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
| `test_extra_env_becomes_dash_e_flags_not_host_env` | Where it plugs in | `extra_env={"X": "1"}` → `-e X=1` present in wrapped argv, NOT forwarded to `super().execute()`'s own `extra_env` param |
| `test_cwd_override_ignored_with_warning` | Where it plugs in | `cwd_override` passed → logged warning, no crash, container still runs against the constructor's `source_root` |
| `test_prepare_phase_skipped_when_lockfile_hash_unchanged` | AD-7 | Stamp file present + matching hash → no `uv sync` container invocation |
| `test_prepare_phase_reruns_on_lockfile_change` | AD-7 | Stamp file hash mismatch → `uv sync` invoked, stamp updated |
| `test_prepare_phase_has_network_execute_phase_does_not` | AD-9 | Prepare-phase argv omits `--network none`; execute-phase argv includes it |
| `test_image_defaults_from_requires_python` | Changes §1 | `pyproject.toml` with `requires-python = ">=3.12"` → image tag resolves to `3.12`; absent/unparseable → `3.13` default |
| `test_result_contract_unchanged_shape` | FR-5 | Returned object is a `SubprocessResult` with the same fields as host-mode |
| **Integration** `test_real_container_execution_round_trip` (×5) | FR-1..FR-8 | Real `podman`/`docker run` (skip if neither engine detected+live), executes a trivial fixture command, asserts RO-mount write attempt fails, RW-scratch write succeeds, `--network none` blocks a live-socket connection attempt, container removed after |

Coverage beyond tests:
- **NFR-1** — engine-liveness caching keeps steady-state overhead low; no automated perf assertion.
  Time a warm-image containerized run vs. host mode manually.
- **NFR-9** — typed `ContainerEngineUnavailableError`. **NFR-10** — unit tests mock at
  `super().execute()`; the integration test `skipif`s with no engine. **NFR-11** — native Linux
  primary; non-root `--user` in scope.
- **AD-1** — subclass overriding only `execute()`. **AD-3** — boundary reuse for mount validation.
  **AD-4** — `BashActionAtom`'s 2 GiB/128-process numbers verbatim.

## Decisions (audit)

| # | Question | Chosen | Severity |
|---|----------|--------|----------|
| R1 | Where does the lockfile-hash stamp live? `uv sync` may wipe or reorganize its `UV_CACHE_DIR`, deleting a stamp stored there and forcing a re-prepare every run. | A **sibling** of `cache_root`: `.specweaver/.sandbox/.prepared_hash`, not `.specweaver/.sandbox/cache/.prepared_hash` | HIGH |
| R2 | Does the non-Python container-mode warning fire in host mode? | No — it lives in SF-02's `factory.py`, gated on `isinstance(executor, ContainerSubprocessExecutor)` | MEDIUM |
| R3 | `--memory`/`--pids-limit` are integers duplicated from `BashActionAtom`, not imported. | Accepted debt — a cross-cutting refactor is not worth it in this SF. Tracked: shared `ResourceLimits`/`MountSpec` value object | LOW |
| R4 | TOCTOU if two steps under the same `run_id` call `_ensure_prepared()` at once? | Accepted risk. `QARunnerAtom` methods run sequentially within a run; parallel fan-out uses independent `run_id`s, each with its own checkout/worktree per `D-EXEC-02`, hence its own `cache_root` | MEDIUM |
| R5 | Non-root `--user` mapping — defer? | In scope. NFR-4 already requires non-root; the "hard" general UID-mapping case does not apply because the executor creates its own mounts (Changes §5) | — |

Out of scope: CI container-engine provisioning (tests `skipif` cleanly until a runner with an
engine exists; ops follow-up); `engine`/`image` override fields (add if a need surfaces).

## As built

- Landed as planned: `ContainerMounts` (`models.py`); `ContainerEngineUnavailableError` +
  `ContainerSubprocessExecutor` (`container_executor.py`) — engine detection/liveness caching, lazy
  mount-dir creation, `requires-python`-derived image tag, `_build_container_cmd()`, `execute()`
  with pre/post idempotent cleanup, `_ensure_prepared()`'s lockfile-hash-gated `uv sync`.
- **The prepare container is hardened like the execute container.** A shared `_baseline_flags()`
  gives both phases the same cap-drop/resource/user flags, and the prepare phase gets the same
  deterministic name + pre/post cleanup — `uv sync` can execute arbitrary sdist build code from
  PyPI, and `--rm` alone is what AD-8 rules out.
- Tests: 47 (33 planned + 9 gap-fill + 5 real-engine integration). Gap-fill: version-clamping
  boundaries, a `TypeError` hostile-input path, `_ensure_engine`'s partial fallback, `uv sync`
  failure handling, the `pyproject.toml`-only prepare branch, `input_text`/`timeout_seconds`
  forwarding. The integration tests ran against real Podman and Docker, confirming RO-mount write
  blocking, RW-scratch writes, `--network none` egress blocking and cleanup.
- Suite at commit: unit 4574 passed/15 skipped, integration 433 passed/5 skipped/15 deselected, e2e
  139 passed/1 skipped. `ruff`/`mypy` (303 files)/`tach check` clean.
- Docs: `docs/dev_guides/subprocess_execution.md` ("Containerized QA Execution"),
  `docs/dev_guides/special_patterns_and_adaptations.md` (§23, executor subclassing),
  `docs/dev_guides/testing_guide.md` (external-tool-skip entry).
