# Implementation Plan: Ephemeral Podman Sub-Containers [SF-01: Core Containerized Execution Engine]

- **Feature ID**: B-EXEC-01
- **Sub-Feature**: SF-01 — Core Containerized Execution Engine
- **Design Document**: docs/roadmap/features/topic_06_sandbox/B-EXEC-01/B-EXEC-01_design.md
- **Design Section**: §Sub-Feature Breakdown → SF-01
- **Implementation Plan**: docs/roadmap/features/topic_06_sandbox/B-EXEC-01/B-EXEC-01_sf01_implementation_plan.md
- **Status**: APPROVED

## Scope

Build `ContainerSubprocessExecutor` — a `SubprocessExecutor` subclass that routes a command
through an ephemeral Podman/Docker container (RO source mount, RW scratch mount, `--network
none`, non-root `--user`, deterministic naming + guaranteed cleanup, the AD-7/AD-9 prepare/execute
phase split for `uv sync` bootstrapping) instead of the host. This is the foundational,
self-contained executor — no other component depends on it existing yet, and it doesn't yet wire
into `QARunnerAtom` (SF-02).

**FRs covered**: FR-2, FR-3, FR-5, FR-6, FR-7, FR-8.
**Inputs**: host source root + a derived scratch/cache directory pair; installed `podman`/`docker`
CLI.
**Outputs**: A `SubprocessResult`-compatible response for any command, produced inside an
ephemeral, auto-removed container.
**Depends on**: none.

## Research Notes

- **`SubprocessExecutor.execute()` exact signature** (`sandbox/execution/executor.py:90`):
  `execute(cmd: list[str], *, timeout_seconds: int | None = None, extra_env: dict[str,str] | None
  = None, cwd_override: Path | None = None, input_text: str | None = None) -> SubprocessResult`.
  Constructor: `__init__(cwd: Path, timeout_seconds: int = 120, resource_limits: ResourceLimits |
  None = None, env_allowlist: frozenset[str] | None = None, strip_credentials: bool = True)`.
  `resource_limits`/`preexec_fn`/Windows Job Objects apply to the **local `podman`/`docker` CLI
  client process**, not the containerized process — container-side limits are separate
  `--memory`/`--pids-limit` flags baked into the wrapped argv. Do not conflate the two.
- **`ResourceLimits`** (`sandbox/execution/models.py`): frozen dataclass, `max_memory_bytes`,
  `max_processes`, `max_file_size_bytes`, all default `None`. `BashActionAtom`
  (`sandbox/execution/core/atom.py:24`) sets `ResourceLimits(max_memory_bytes=2_147_483_648,
  max_processes=128)` as its own local default — this plan reuses these same numbers for the
  container's `--memory`/`--pids-limit` flags (AD-4), not by passing `ResourceLimits` to the
  parent `SubprocessExecutor` (which would only limit the local CLI client, per the point above).
- **Placement**: `execution/core/` (where `BashActionAtom` lives) only holds Atom-tier
  orchestration; `SubprocessExecutor` itself lives flat at `execution/executor.py`.
  `ContainerSubprocessExecutor` is executor-tier, not atom-tier, so it belongs flat at
  **`sandbox/execution/container_executor.py`**, sibling to `executor.py` — this also keeps it
  inside the TID251 subprocess-import-ban exemption glob (`"src/specweaver/sandbox/execution/*.py"`,
  confirmed flat/non-recursive in `pyproject.toml`), though the override design below never
  imports raw `subprocess` anyway (it only ever calls `super().execute()`).
- **`WorkspaceBoundary` / `ReadOnlyWorkspaceBoundary`** (`sandbox/security.py`):
  `WorkspaceBoundary(roots: list[Path], api_paths: list[Path] | None = None)`,
  `.validate_path(requested: Path) -> Path` (raises `WorkspaceBoundaryError`).
  `ReadOnlyWorkspaceBoundary(api_paths: list[Path])` — a subclass with no write roots,
  `.is_read_only` always `True`. This maps directly onto the two mounts:
  `ReadOnlyWorkspaceBoundary(api_paths=[source_root])` validates the RO source mount path, plain
  `WorkspaceBoundary(roots=[scratch_root, cache_root])` validates the RW mounts — reused, not
  reinvented (AD-3).
- **`MCPAtom`** (`sandbox/mcp/core/atom.py`) already enforces "must run through docker/podman"
  (`NFR-2 Boundary Violation` check on `command[0]`), and `mcp_implementation_patterns.md`
  documents this as an existing mandate. **Not directly reusable**: `MCPAtom` validates an
  *externally pre-built* command list and bridges long-lived bidirectional JSON-RPC over stdio —
  a different execution model from this SF's one-shot, programmatically-mount-constructed
  container run. Cited as related precedent for the "must go through an isolated engine"
  convention, not as reusable argv-building code.
- **tach.toml**: `specweaver.sandbox` is a **flat** tach module — internal sandbox-to-sandbox
  imports aren't gated by `[[interfaces]]`. `ContainerSubprocessExecutor` is consumed entirely
  *within* `sandbox` (by SF-02's `qa_runner/core/factory.py`/`atom.py`), so **no `tach.toml`
  change is needed** for this SF.

## Proposed Changes

| File | Change | Purpose |
|------|--------|---------|
| `src/specweaver/sandbox/execution/container_executor.py` | `[NEW]` | `ContainerSubprocessExecutor(SubprocessExecutor)` + `ContainerEngineUnavailableError` |
| `src/specweaver/sandbox/execution/models.py` | `[MODIFY]` | Add `ContainerMounts` frozen dataclass (`source_root`, `scratch_root`, `cache_root`) |
| `tests/unit/sandbox/execution/test_container_executor.py` | `[NEW]` | Unit tests (mocked at `super().execute()` boundary — no real container spawn) |
| `tests/integration/sandbox/execution/test_container_executor_integration.py` | `[NEW]` | Real `podman`/`docker` run, `@pytest.mark.integration`, `skipif` no engine detected |

## Implementation Sequence (pseudocode)

`ContainerEngineUnavailableError(Exception)` — raised when neither engine is detected+live.

`ContainerMounts` (in `models.py`): frozen dataclass, `source_root: Path`, `scratch_root: Path`,
`cache_root: Path`.

`ContainerSubprocessExecutor(SubprocessExecutor)`:
1. `__init__(self, cwd, mounts: ContainerMounts, image: str | None = None, timeout_seconds=120, resource_limits=None)`: call `super().__init__(cwd=cwd, timeout_seconds=timeout_seconds, resource_limits=resource_limits)`; validate `mounts.source_root` via `ReadOnlyWorkspaceBoundary(api_paths=[mounts.source_root])`, `mounts.scratch_root`/`cache_root` via `WorkspaceBoundary(roots=[...])` (AD-3); create `scratch_root`/`cache_root` on disk if missing (`mkdir(parents=True, exist_ok=True)`); resolve `image` if `None` by reading `requires-python` from `cwd / "pyproject.toml"` (best-effort regex/`tomllib` parse; map to closest of `{3.11, 3.12, 3.13}`, default `3.13` on absence/parse failure); store `self._engine: str | None = None` (unresolved).
2. `_ensure_engine(self) -> str` (lazy, memoized): if `self._engine` is set, return it. Else, for `"podman"` then `"docker"`: resolve via `shutil.which(name)` (absolute path, never the bare string); if found, run a liveness probe (`[resolved_path, "info"]`) through `super().execute(..., timeout_seconds=5)`; if `exit_code == 0`, memoize and return. If neither engine is live, raise `ContainerEngineUnavailableError` naming both attempted engines.
3. `_ensure_prepared(self) -> None`: compute a hash of `cwd / "uv.lock"` (fallback `pyproject.toml`) if present; compare against a stamp file at `.specweaver/.sandbox/.prepared_hash` (a **sibling** of `cache_root`, not inside it — see Red/Blue Cycle 1 below); if unchanged, return immediately. Else run a **network-enabled** prepare container (`--network` default, i.e. omit `--network none`) invoking `uv sync` with `cwd`'s source mounted RO at `/workspace`, `cache_root` mounted RW at `/cache` (`UV_CACHE_DIR=/cache`), no scratch mount, no LLM-generated code executed — write the new hash to the stamp file on success (AD-7/AD-9's two-phase split).
4. `execute(self, cmd, *, timeout_seconds=None, extra_env=None, cwd_override=None, input_text=None) -> SubprocessResult` (override): call `self._ensure_engine()` (propagates `ContainerEngineUnavailableError`); call `self._ensure_prepared()`; build `name = f"specweaver-qa-{run_id}-{uuid4().hex[:8]}"`; pre-emptively `[engine, "rm", "-f", name]` via `super().execute(...)`, ignoring its result (idempotent, AD-8); build the wrapped argv (see below); call `result = super().execute(wrapped, timeout_seconds=timeout_seconds, input_text=input_text)` — `extra_env` entries become `-e KEY=VAL` flags baked into `wrapped` (they must reach the *container's* env, not the local CLI client's); `cwd_override` is ignored with a `logger.warning` if non-`None`; in a `finally` block, run `[engine, "rm", "-f", name]` again via `super().execute()` unconditionally (post-run cleanup, AD-8), swallowing any error from the cleanup call itself.
5. `_build_container_cmd(self, name, cmd, extra_env) -> list[str]`: `[engine, "run", "--rm", "--name", name, "--read-only", "-v", f"{source_root}:/workspace:ro", "-v", f"{scratch_root}:/scratch:rw", "--tmpfs", "/tmp:size=100m,mode=1777", "--network", "none", "--cap-drop", "ALL", "--security-opt", "no-new-privileges:true", "--memory", "2147483648", "--pids-limit", "128", *user_flag, *(f"-e" then f"{k}={v}" for k, v in (extra_env or {}).items()), "--workdir", "/workspace", image, *cmd]`.
   - **`user_flag` (NFR-4 — non-root, not deferred; see Post-Planning Correction)**: on non-Windows (`sys.platform != "win32"`), `["--user", f"{os.getuid()}:{os.getgid()}"]` — tractable at low complexity because `scratch_root`/`cache_root` are created by `ContainerSubprocessExecutor.__init__` itself as the invoking host user, so the container runs as the same UID that already owns every mount it touches. On Windows, `user_flag = []` (falls back to image default/root), with a one-time `logger.warning`.

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
| `test_image_defaults_from_requires_python` | Implementation Sequence | `pyproject.toml` with `requires-python = ">=3.12"` → image tag resolves to `3.12`; absent/unparseable → `3.13` default |
| `test_result_contract_unchanged_shape` | FR-5 | Returned object is a `SubprocessResult` with the same fields as host-mode |
| **Integration** `test_real_container_execution_round_trip` (×5) | FR-1..FR-8 | Real `podman`/`docker run` (skip if neither engine detected+live), executes a trivial fixture command, asserts RO-mount write attempt fails, RW-scratch write succeeds, `--network none` blocks a live-socket connection attempt, container removed after |

## FR / NFR / AD Coverage

| ID | Covered by |
|----|-----------|
| FR-2 | `--read-only` + `-v source:/workspace:ro`; test: `test_read_only_source_mount_flag_present` |
| FR-3 | `-v scratch:/scratch:rw`; test: `test_writable_scratch_mount_flag_present` |
| FR-5 | `super().execute()` return value passed through unchanged; test: `test_result_contract_unchanged_shape` |
| FR-6 | Engine auto-detection + rootless-Podman preference; tests: `test_engine_detection_prefers_podman`, `test_engine_detection_falls_back_to_docker` |
| FR-7 | `ContainerEngineUnavailableError`; tests: `test_engine_unavailable_raises_typed_error`, `test_engine_on_path_but_not_live_raises` |
| FR-8 | Pre/post `rm -f`; tests: `test_cleanup_runs_before_and_after_execution`, `test_cleanup_runs_on_super_execute_exception` |
| NFR-1 | Engine-liveness caching keeps steady-state overhead low; not independently unit-tested — validated qualitatively during the integration round-trip test's wall-clock, noted in Backlog as a manual perf check |
| NFR-2 | `--read-only` + scoped mounts; test: `test_read_only_source_mount_flag_present` |
| NFR-3 | `--network none` on execute phase only; test: `test_network_none_by_default`, `test_prepare_phase_has_network_execute_phase_does_not` |
| NFR-4 | `--cap-drop ALL --security-opt no-new-privileges` + non-root `--user` matching the invoking host UID/GID on non-Windows; tests: `test_non_root_capabilities_dropped`, `test_user_flag_matches_invoking_uid_on_linux`, `test_user_flag_omitted_on_windows_with_warning` |
| NFR-5 | `--memory`/`--pids-limit` matching `BashActionAtom`; test: `test_resource_limits_match_bash_action_atom_defaults` |
| NFR-6 | Pre+post `rm -f`, not `--rm` alone; tests: `test_cleanup_runs_before_and_after_execution`, `test_cleanup_runs_on_super_execute_exception` |
| NFR-9 | Typed `ContainerEngineUnavailableError` | 
| NFR-10 | Unit tests mock at `super().execute()`; integration test `skipif`s when no engine |
| NFR-11 | Native-Linux-primary scope; non-root `--user` mapping in scope (not deferred, see Post-Planning Correction) |
| AD-1 | `ContainerSubprocessExecutor(SubprocessExecutor)` subclass, overriding only `execute()` |
| AD-3 | `ReadOnlyWorkspaceBoundary`/`WorkspaceBoundary` reuse for mount validation |
| AD-4 | `BashActionAtom`'s 2 GiB/128-process defaults reused verbatim |
| AD-6 | Podman-preferred engine ordering; test: `test_engine_detection_prefers_podman` |
| AD-7 | Prepare/execute phase split + lockfile-hash gating; tests: `test_prepare_phase_skipped_when_lockfile_hash_unchanged`, `test_prepare_phase_reruns_on_lockfile_change` |
| AD-8 | Deterministic name + pre/post `rm -f`; tests: `test_deterministic_name_includes_run_id_and_uuid_suffix`, `test_cleanup_runs_before_and_after_execution` |
| AD-9 | Network split between phases; test: `test_prepare_phase_has_network_execute_phase_does_not` |

## Backlog (deferred, out of scope for SF-01)

- **CI container-engine provisioning**: integration tests `skipif` cleanly today without it, but
  the containerized path won't actually be exercised in CI until a runner with Podman/Docker is
  provisioned. Ops follow-up, not `dev`-skill code.
- **`engine`/`image` override fields**: add if/when a real need surfaces.
- **NFR-1 latency validation**: no automated perf assertion; manually time a warm-image
  containerized run vs. host-mode during pre-commit and note the delta in the walkthrough.
- **Shared `ResourceLimits`/`MountSpec` value object**: `--memory`/`--pids-limit` values are
  hardcoded integers duplicated from `BashActionAtom`'s constants rather than imported from a
  shared location — accepted as low-cost, explicitly-tracked debt (see Red/Blue Cycle 1).

## Post-Planning Correction (pre-approval)

The original Phase-4-resolved draft of this plan deferred non-root `--user` UID/GID mapping to
Backlog "as a follow-up spike," reasoning it needed a general host-UID↔container-UID mapping
strategy. On review, this was wrong on two counts: (1) the design doc's own **NFR-4** already
states the container "SHALL run as a non-root user" — a hard requirement approved before this
plan existed, not a discretionary nice-to-have this plan was free to defer; (2) the perceived
complexity was for the *general* case (arbitrary container UID vs. arbitrary mount owner), which
doesn't apply here — `ContainerSubprocessExecutor` creates `scratch_root`/`cache_root` itself, as
the invoking host user, so running the container `--user`-pinned to that same UID/GID has no
ownership mismatch to solve on native Linux (NFR-11's already-agreed primary target). Folded back
into scope: Implementation Sequence §5 (`user_flag` construction), Test Plan (2 new tests), and
the NFR-4 coverage row above.

## Phase 5: Final Consistency Check

**5.0 Pre-check**: All 6 FRs, all 11 NFRs (those assigned to this SF), and the container-core ADs
from the design doc's scope are accounted for above.

**5.1 Open questions**: None remaining.

**5.2 Architecture and future compatibility**: No circular imports — `container_executor.py`
imports only from its own sibling `executor.py`/`models.py` and `sandbox.security`. No `tach.toml`
change required. Consumed by SF-02 (`qa_runner/core/{atom,factory}.py`), an existing, already-legal
sandbox-internal import direction.

**5.2a Architecture Principles**: **DDD** — stays within `sandbox`. **KISS** — one subclass
overriding one method; no speculative abstraction layer for "pluggable container engines" beyond
the two (podman/docker) actually needed. **DRY** — reuses `SubprocessExecutor`,
`WorkspaceBoundary`/`ReadOnlyWorkspaceBoundary`, `BashActionAtom`'s resource-limit numbers.
**Hexagonal** — `ContainerSubprocessExecutor` is itself an adapter; no domain logic leaks into it.

**5.3 Internal consistency**: Every FR/NFR/AD assigned to this SF maps to at least one concrete
change and at least one test.

### Red/Blue Team Review (2 cycles run, before implementation started)

**Cycle 1** —
- 🔴 **HIGH**: `_ensure_prepared()`'s lockfile-hash stamp file lives under `cache_root`
  (`.specweaver/.sandbox/cache/.prepared_hash`) — but `cache_root` is also the mount target for
  the prepare-phase container's `UV_CACHE_DIR`. Does `uv sync` ever wipe or reorganize the
  directory it's pointed at as a cache dir in a way that could delete the stamp file, causing
  every subsequent run to needlessly re-prepare? **Blue**: VALID — FIX REQUIRED. Store the stamp
  file in a *sibling* location, not inside the directory passed as `UV_CACHE_DIR` itself — e.g.
  `.specweaver/.sandbox/.prepared_hash` (one level up, alongside `scratch/`/`cache/`, not inside
  `cache/`). Reflected in Implementation Sequence §3 above.
- 🔴 **MEDIUM**: Does a non-Python-runner container-mode warning fire even in **host mode**, where
  a `ContainerSubprocessExecutor` was never constructed at all? **Blue**: INVALID — NO ACTION
  (this check lives in SF-02's `factory.py`, gated on `isinstance(executor,
  ContainerSubprocessExecutor)`, inherently `False` for the host-mode path).
- 🔴 **LOW**: `_build_container_cmd`'s `--memory`/`--pids-limit` values are hardcoded integers
  matching `BashActionAtom`'s constants, duplicated rather than imported from a shared location.
  **Blue**: VALID — ACCEPTED as a Backlog item — not worth a cross-cutting refactor inside this
  already-large SF.

**Cycle 2** — re-examined Cycle 1's fix plus a fresh pass:
- 🔴 **MEDIUM**: With the stamp file corrected to live alongside (not inside) `cache_root`, is
  there a TOCTOU race if two pipeline steps under the *same* `run_id` both call
  `_ensure_prepared()` concurrently against the same stamp file? **Blue**: VALID — ACCEPTED RISK,
  not a fix. `QARunnerAtom`'s own methods are invoked sequentially within a single pipeline run
  today — this only becomes a real hazard under fan-out running fully independent `run_id`s in
  parallel, and each of those has its own independent project checkout/worktree per the existing
  Git Worktree Bouncer (`D-EXEC-02`) design, hence independent `cache_root` paths.
- No new findings below the continuation threshold. Review converges.

**Corrections made**: Implementation Sequence §3's stamp-file location corrected from "under
`cache_root`" to "a sibling of `cache_root`."

---

## HITL Gate — Approval Required

This plan is ready for review. Summary: 4 files (2 new source, 2 new test), zero changes to
`tach.toml`, Red/Blue review ran 2 cycles and caught one real bug (stamp-file placement) before
implementation started, and a post-planning correction restored non-root `--user` mapping into
scope (it was mistakenly deferred against the design doc's own NFR-4).

Reply with approval to mark this plan `APPROVED` and proceed to the `dev` skill for SF-01's TDD
implementation.

---

## Post-Implementation Notes

**Landed as planned**: `ContainerMounts` (`models.py`), `ContainerEngineUnavailableError` +
`ContainerSubprocessExecutor` (`container_executor.py`) — engine detection/liveness caching, lazy
mount-dir creation, `requires-python`-derived image tagging, `_build_container_cmd()`,
`execute()` override with pre/post idempotent cleanup, `_ensure_prepared()`'s
lockfile-hash-gated `uv sync` prepare phase.

**File placement**: placed flat at `sandbox/execution/container_executor.py` (sibling to
`executor.py`, not nested under `execution/core/`), exactly as planned.

**Test coverage exceeded the plan**: the pre-commit gate's test-gap analysis found 9 real branch
gaps beyond this plan's original Test Plan table (version-clamping boundaries, a `TypeError`
hostile-input path, `_ensure_engine`'s partial-fallback case, `uv sync` failure handling, the
`pyproject.toml`-only prepare branch, and `input_text`/`timeout_seconds` forwarding) — all 9
implemented. The real-engine integration test
(`tests/integration/sandbox/execution/test_container_executor_integration.py`, 5 tests) actually
ran against a real engine (both Podman and Docker were live on the implementing machine) rather
than skipping, positively confirming RO-mount write-blocking, RW-scratch write-allowance,
`--network none` egress-blocking, and post-execution container cleanup.

**Additional bugs caught by pre-commit's own Red/Blue review (Phase 7.5, post-implementation)**:
the `uv sync` prepare-phase container initially lacked the same cap-drop/resource/user hardening
as the execute-phase container, despite `uv sync` being able to execute arbitrary sdist build code
from PyPI; and it relied on `--rm` alone with no deterministic name or pre/post cleanup — the
exact anti-pattern AD-8 exists to prevent. Both fixed: extracted a shared `_baseline_flags()` used
by both phases, and gave the prepare phase the same name+cleanup treatment as the execute phase.
3 new tests added (47 unit tests total for this sub-feature), all green.

**Documentation updated**: `docs/dev_guides/subprocess_execution.md` (new "Containerized QA
Execution" section), `docs/dev_guides/special_patterns_and_adaptations.md` (§23, the
executor-subclassing pattern), `docs/dev_guides/testing_guide.md` (new external-tool-skip entry).

**Test counts**: 47 new tests (33 initial + 9 gap-fill + 5 real-engine integration), all green.
Full suite after this sub-feature: unit 4574 passed/15 skipped, integration 433 passed/5
skipped/15 deselected, e2e 139 passed/1 skipped — zero regressions. `ruff`/`mypy`(303 files)/
`tach check` all clean.

**Committed as**: `68c34359`.
