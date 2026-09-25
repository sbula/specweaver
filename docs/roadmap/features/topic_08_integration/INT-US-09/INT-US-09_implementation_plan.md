# INT-US-09 — Zero-Trust Sandbox: Base Integration Contract — Implementation Plan

**Status**: APPROVED — approved by Steve Bula on 2026-07-16. Implemented 2026-07-17 in 4 commit
boundaries. · **FRs owned**: FR-1…FR-6 · **Depends on**: none · Design:
[INT-US-09_design.md](INT-US-09_design.md)

Single, non-decomposed feature: no `_sfNN_` suffix — the `INT-US-09-SF01..SF04` labels are reserved
for the excluded add-on sub-stories.

## Goal

Wire **US-5** (Git Worktree Bouncer), **E-EXEC-01** (SubprocessExecutor) and **C-EXEC-02**
(BashActionAtom) into one enforceable, **container-free** host-execution flow. With the opt-in
US-9 isolation policy on, the untrusted-**execution** surfaces (`action: bash` and
`run_tests`/pytest) run inside an ephemeral git worktree with the `SubprocessExecutor` boundary
rebound to the worktree source tree; static-analysis QA (ruff/tach) and all other handlers are
unchanged.

**Strictly excluded**: containerization (`B-EXEC-01`/`D-EXEC-01`/Podman) and INT-US-09-SF01..SF04.

## Where it plugs in

Verified 2026-07-16.

| Fact | Where |
|---|---|
| `PipelineStep` — `use_worktree: bool = False` at **`:221`**. No pipeline YAML sets it. | `src/specweaver/core/flow/engine/models.py:202` (`src/specweaver/core/flow/engine/models.py:221`) |
| Runner gate — `if getattr(step_def, "use_worktree", False):` at **`:320`** dispatches to `execute_in_sandbox`, else `await handler.execute(step_def, self._context)`. `self._context` is the single shared RunContext, mutated in place each step (`:316-318`). | `src/specweaver/core/flow/engine/runner.py:314-337` |
| `execute_in_sandbox` (body `:136-194`) — `isolated_context = copy.copy(context)`, then `isolated_context.output_dir = context.project_path / wt_path` (**`:160-162`**); `wt_path = f".worktrees/{task_id}"` (:151). Drives `GitAtom` intents `worktree_add`/`worktree_sync`/`strip_merge`/`worktree_teardown`; teardown in a `finally` (:183-185). | `src/specweaver/core/flow/engine/runner_utils.py:136-194` |
| `setup_sandbox_caches` — symlinks caches incl. **`.specweaver`** (:103) into the worktree → `.specweaver/scripts` resolves *within* the worktree; but `.specweaver` is a shared symlink (reservations/vault are shared — the shared-cache seam, AD-4). | `runner_utils.py:89` |
| `SandboxSettings` — one field (`execution_mode: Literal["host","container"] = "host"`). `SpecWeaverSettings` (:125-133) exposes `sandbox: SandboxSettings = SandboxSettings()`. Pydantic v2 `BaseModel` (no strict). | `src/specweaver/core/config/settings.py:114-122` |
| TOML loader — `_load_toml_sandbox` does `SandboxSettings(**sandbox_data)` (:88) → a new field auto-loads from `[sandbox]`; loader change: docstring/test only. | `settings_loader.py:73-91` |
| **Composition roots that BUILD RunContext** (H1): the run/resume paths **do NOT set `config=`** — so `context.config.sandbox` is `None` on real `sw run`/API runs. Pattern to mirror: `src/specweaver/workflows/implementation/interfaces/cli.py:142` (`config=settings`). `load_settings` already imported in `cli.py` (:261/273/276). | `src/specweaver/core/flow/interfaces/cli.py:251` (run), `:435` (resume); API `src/specweaver/interfaces/api/v1/pipelines.py:84`, `:225`, `:312` |
| The executor boundary is the constructor `cwd`. | `src/specweaver/sandbox/execution/executor.py:61` |
| `BashActionHandler._get_atom` (`:64-68`) returns `BashActionAtom(cwd=context.project_path)`. `BashActionAtom.__init__(cwd)` sets `_scripts_root = cwd/.specweaver/scripts`; executor built as `SubprocessExecutor(cwd=self._cwd,...)` (`:106`). | `src/specweaver/core/flow/handlers/bash_action.py:64-68`; `src/specweaver/sandbox/execution/core/atom.py:65-67,106` |
| `ValidateTestsHandler._get_atom` returns `QARunnerAtom(cwd=context.project_path, sandbox_settings=...)` and calls `atom.run({"intent": "run_tests", ...})` (`:367-369`). | `core/flow/handlers/validation.py:403-408` |
| **`LintFixHandler`** calls `{"intent": "run_linter"}` — **ruff, static, out of scope**. | `lint_fix.py:74` |
| Test patterns: `tests/integration/core/flow/engine/test_runner_sandbox.py` patches `GitAtom.run` (autospec), asserts intent order `[worktree_add, worktree_sync, strip_merge, worktree_teardown]` and that the handler sees `".worktrees" in str(ctx.output_dir)`. `tests/e2e/sandbox/test_executor_e2e.py` drives a real `SubprocessExecutor` (no marker). | tests |

`RunContext` (`src/specweaver/core/flow/handlers/base.py:30`) — Pydantic v2 `BaseModel`
(`model_config = ConfigDict(arbitrary_types_allowed=True)`). `project_path: Path` (:47),
`output_dir: Path | None = None` (:55), `config: Any = None  # SpecWeaverSettings | None` (:53).
**No** `execution_root` field. `Path` is imported at runtime (`base.py:10`), so a `Path | None`
field needs no import. QA handlers read the policy via `context.config.sandbox`.

**Since moved:** 2026-08-12 — `RunContext` → `core/flow/handlers/run_context.py` (`862cb0ff`);
2026-08-12 — `runner_utils` retired (`c3f36d54`): `execute_in_sandbox`, `setup_sandbox_caches` →
`core/flow/engine/sandboxed_execution.py`; 2026-08-17 — e2e tests → `tests/e2e/capabilities/`
(`5617d11c`; the proof is `tests/e2e/capabilities/sandbox/test_step_worktree_isolation_e2e.py`).
Line refs here are as of the plan's date.

## Changes

| File | Tag | Change |
|------|-----|--------|
| `src/specweaver/core/config/settings.py` | MODIFY | Add `enforce_worktree_isolation: bool = False` to `SandboxSettings`. |
| `src/specweaver/core/flow/interfaces/cli.py` | MODIFY | Pass `config=<loaded settings>` into `RunContext(...)` at `:251` and `:435`. |
| `src/specweaver/interfaces/api/v1/pipelines.py` | MODIFY | Pass `config=<loaded settings>` into `RunContext(...)` at `:84`, `:225`, `:312`. |
| `src/specweaver/core/flow/handlers/base.py` | MODIFY | Add `execution_root: Path \| None = None` to `RunContext`. |
| `src/specweaver/core/flow/engine/models.py` | MODIFY | `use_worktree: bool = False` → `use_worktree: bool \| None = None` (tri-state). |
| `src/specweaver/core/flow/engine/runner.py` | MODIFY | Replace the `:320` gate with a policy-aware resolver (tri-state ?? policy). |
| `src/specweaver/core/flow/engine/runner_utils.py` | MODIFY | In `execute_in_sandbox`: set `isolated_context.execution_root = worktree path`; add an early fail-closed git-repo check. |
| `src/specweaver/core/flow/handlers/bash_action.py` | MODIFY | `_get_atom` uses `cwd=context.execution_root or context.project_path`. |
| `src/specweaver/core/flow/handlers/validation.py` | MODIFY | `ValidateTestsHandler._get_atom` uses `cwd=context.execution_root or context.project_path`. |
| `tests/e2e/sandbox/test_step_worktree_isolation_e2e.py` | NEW | Real-worktree unmocked proof (FR-6). |
| `tests/unit/**` + `tests/integration/**` | NEW/MODIFY | Unit + integration coverage per Tests. |
| `docs/dev_guides/pipeline_engine_guide.md`, `subprocess_execution.md` | MODIFY | Doc updates (pre-commit). |

The config rows for `cli.py`/`pipelines.py` were superseded by the container-neutrality guard in
CB-1: the root sets `RunContext.enforce_isolation`, not `config=`.

### CB-1 — Config surface + composition-root wiring

Nothing downstream can read the policy until the composition root resolves it onto the run context.

> [!IMPORTANT]
> **Container-neutrality guard (user decision, Red/Blue finding).** The composition root does NOT
> populate `context.config` with the full settings — that would expose `[sandbox] execution_mode`
> and incidentally activate B-EXEC-01 container QA on `sw run` (out of INT-US-09's container-free
> scope; it also broke `test_lint_fix_retains_tag`). Instead it resolves **only** the isolation
> policy into a dedicated `RunContext.enforce_isolation: bool` flag. `context.config` stays `None`
> on `sw run` exactly as before (byte-identical; container opt-in stays dormant on this path).

1. Add `enforce_worktree_isolation: bool = False` to `SandboxSettings` (mirrors `execution_mode`).
2. Add `enforce_isolation: bool = False` to `RunContext` (`handlers/base.py`).
3. **CLI (must-do, the primary `sw run` surface):** at `cli.py` run + resume sites, resolve the
   policy at the composition root (ADR-002), graceful (never crash a run):
   ```
   try:
       context.enforce_isolation = load_settings(db, project_path.name).sandbox.enforce_worktree_isolation
   except Exception:
       logger.debug(...)   # policy falls back to default (off)
   ```
4. **API:** wire the 3 `pipelines.py` sites **iff** settings are readily resolvable there. If it
   would need a non-trivial API refactor, record an explicit Backlog gap ("API-launched runs do not
   yet honor `enforce_worktree_isolation`") — documented, **not silently dropped**.
5. Verify/add any new `tach.toml` edge (esp. `interfaces.api` → `core.config` if new) and run
   `tach check`. (`cli.py` already imports `load_settings` → no new edge.)
6. Confirm no code path asserts `context.config is None` on these paths (grep guard).

### CB-2 — Execution-root field + tri-state flag + gate resolution

1. `RunContext`: add `execution_root: Path | None = None` — the root untrusted processes bind their
   `cwd` to; `None` ⇒ callers fall back to `project_path`.
2. `PipelineStep.use_worktree`: `bool` → `bool | None`, default `None`.
3. Runner gate (`runner.py:320`) — an ordered resolver reading the **dedicated
   `context.enforce_isolation` flag** (set in CB-1), NOT `context.config.sandbox`:
   ```
   step_val = step_def.use_worktree                 # True | False | None
   should_isolate = step_val if step_val is not None else context.enforce_isolation
   if should_isolate: result = await execute_in_sandbox(...)
   else:              result = await handler.execute(step_def, self._context)
   ```
4. `execute_in_sandbox`: alongside `output_dir`, set
   `isolated_context.execution_root = context.project_path / wt_path` (the worktree root, so
   `.specweaver/scripts` resolves under it).

### CB-3 — Boundary hand-off in the two untrusted handlers

One rebind idiom everywhere: `execution_root or project_path`.


1. `bash_action.py:68`: `BashActionAtom(cwd=context.execution_root or context.project_path)`.
2. `validation.py:408` (ValidateTests): `QARunnerAtom(cwd=context.execution_root or context.project_path, sandbox_settings=...)`.
3. No change to `BashActionAtom`/`QARunnerAtom` internals — they already accept `cwd`; the
   `.specweaver/scripts` `WorkspaceBoundary` and `shutil.which("bash")` resolution re-derive from
   the passed `cwd`, which now points inside the worktree.
4. Do **not** touch `lint_fix.py`, `validation_hydrator.py`, `facades.py`, or the
   LanguageAtom/CodeStructure handlers (static or out of scope).

> [!CAUTION]
> Handlers must read `execution_root` off the **context parameter passed to `execute()`/`_get_atom()`**
> (the `isolated_context` that `execute_in_sandbox` builds), NOT `self._context`/`runner._context`.
> `execute_in_sandbox` calls `handler.execute(step_def, isolated_context)` and `_get_atom(context)`
> uses that passed context. `copy.copy` is shallow, which is fine — `execution_root` is set on the
> isolated copy only; the original context's stays `None` (non-isolated steps keep `project_path`).

> [!NOTE]
> `.specweaver` is symlinked into the worktree only `if src.exists()` (`setup_sandbox_caches`). A
> project running `action: bash` from `.specweaver/scripts` necessarily has `.specweaver`, so the
> symlink exists before the bash handler runs — but the dependency is real.

### CB-4 — Verifiable proof (e2e) + fail-closed check + docs

1. `execute_in_sandbox` fail-closed (H3): it already raises `RuntimeError` when `worktree_add`
   fails. Improve the message **using GitAtom's actual failure** (`add_res.message`) — no raw `.git`
   filesystem probe in the engine (violates NFR-2/AD-1). Append an actionable hint when isolation
   was policy-/flag-triggered: `f"US-9 worktree isolation could not start ({add_res.message}). Ensure
   <project> is a git repository, or disable [sandbox].enforce_worktree_isolation."` — surface the
   real cause (non-git, worktree-exists, disk-full, etc.), not an assumed one.
2. The e2e test (see Tests) — real git repo + real worktree + real `action: bash`.
3. Docs: `pipeline_engine_guide.md` §7 (isolation rebinds execution, not just `output_dir`; policy
   switch) and `subprocess_execution.md` (execution-root convention).

## Tests

TDD, red first.

| Tier | Case |
|---|---|
| Unit | `SandboxSettings.enforce_worktree_isolation` defaults `False`; TOML `[sandbox] enforce_worktree_isolation = true` loads `True` (extend `test_settings_loader.py`) |
| Unit | `PipelineStep.use_worktree` accepts `True`/`False`/`None`; default `None` |
| Unit | Gate resolver truth table (parametrized): (step=None, policy=off)→host; (None, on)→isolate; (True, off)→isolate; (False, on)→host; (True, on)→isolate |
| Unit | `execute_in_sandbox` sets `isolated_context.execution_root` to `.worktrees/...` (via the `GitAtom.run` patch pattern from `test_runner_sandbox.py`) |
| Unit | `bash_action._get_atom` / `validation.ValidateTests._get_atom`: with `context.execution_root` set, atom `cwd` == execution_root; with it `None`, `cwd` == `project_path` |
| Unit | Composition root: RunContext built by the `sw run` path carries `config.sandbox` (not `None`) — superseded by the CB-1 guard: it carries `enforce_isolation` |
| Integration | Policy-on run with a `use_worktree=None` bash step routes through `execute_in_sandbox` (intent order asserted); policy-off + `None` does not |
| Integration | Fail-closed: policy-on run against a non-git tmp project raises the actionable error |
| E2E (FR-6) | `tests/e2e/sandbox/test_step_worktree_isolation_e2e.py` — see below |

E2E, real and unmocked: `git init` a project in `tmp_path` with a `.specweaver/scripts/<name>.sh`
that writes a sentinel to a **source-tree** path (e.g. `<root>/marker.txt` or `src/marker.py`) —
**not** under `.specweaver/` (a shared symlink per AD-4, which would escape the worktree and give a
false result). Pipeline of one `action: bash` step, `config` with `enforce_worktree_isolation=True`,
run via a real `PipelineRunner` (real `GitAtom`, real worktree). Assert the sentinel lands under
`.worktrees/...`, the **real** root's `marker.txt` is absent, and the worktree is torn down.
Best-effort extra: a `run_tests` step runs with `cwd` inside the worktree. Follow the
`tests/e2e/sandbox/` convention (no `@pytest.mark.e2e`); skip cleanly at collection if `git` **or**
`bash` is unavailable (`shutil.which` — mirrors the engine-availability skip pattern).

| Item | Where covered |
|------|---------------|
| FR-1 (boundary hand-off) | CB-2 (execution_root) + CB-3 (handler rebind) |
| FR-2 (bash worktree containment) | CB-3 + e2e |
| FR-3 (isolation policy) | CB-1 (field + config wiring) + CB-2 (gate) |
| FR-4 (unified security boundary) | CB-3 — executor re-derived from worktree cwd, E-EXEC-01 guarantees intact |
| FR-5 (strip-merge preservation) | Unchanged US-5 path in `execute_in_sandbox`; integration test asserts intent order |
| FR-6 (verifiable proof) | CB-4 e2e |
| NFR-1 (backward compat) | Default policy off + `use_worktree=None` ⇒ host path; unchanged-behavior unit guards |
| NFR-2 (arch compliance) | Wiring in `core.flow`+composition root; atoms only; module-top imports |
| NFR-3 (security) | `.specweaver/scripts` containment + `shutil.which` preserved (CB-3) |
| NFR-4 (platform) | Reuses US-5 Windows-lock teardown |
| NFR-7 (proof tier) | Real-worktree unmocked e2e |
| AD-1..AD-5 | CB-1..CB-4 as mapped above |

## Decisions (audit)

HITL-approved: **H1** wire the policy at the composition root — CLI must-do, API best-effort else
Backlog · **H2** isolate-all-by-default when the policy is on, with explicit per-step opt-out ·
**H3** fail closed with an actionable message from GitAtom's real failure · **H4** scope = bash +
`run_tests` only; `lint_fix`/static excluded · **H5** tri-state `use_worktree` · M1–M5 + L1–L3
banked (see Backlog).

Red/Blue, 2 cycles, converged at 0 CRITICAL / 0 HIGH:

| Finding | Sev | Resolution |
|---|---|---|
| RED-1.2 API `config` wiring may force an API refactor | HIGH | CLI must-do; API best-effort with an explicit Backlog gap (CB-1 step 4) |
| RED-1.5 raw `.git` probe in the engine violates NFR-2/AD-1 | HIGH | Fail-closed routes through `GitAtom`'s real failure message (CB-4.1) |
| RED-1.3 e2e sentinel could target symlinked `.specweaver` | MED | Sentinel writes to a source-tree path; assert real root unmutated |
| RED-1.6 e2e needs a `bash` skip guard | MED | `shutil.which("git"/"bash")` collection-time skip |
| RED-2.2 new imports need `tach` edges | MED | CB-1 edge check + `tach check` |
| RED-2.3 handlers must read the isolated context, not `self._context` | MED | CB-3 CAUTION note |
| RED-2.4 fail-closed must not assume the cause | MED | Surface GitAtom's actual message (CB-4.1) |

RED-1.1 (LOW) `use_worktree` `bool→bool|None` serialization: only reader is the gate; model test
covers all 3 states.

Every code block above is pseudocode, gate logic, or a signature quoted from existing code. The
`execution_root` + policy seam is what SF01 (container) / SF02 (egress) would extend.

## As built (2026-07-17)

CB-1 `85d02be4` · CB-2 `f4077870` · CB-3 `bd6913c6` · CB-4 `474490ae`. The container-neutrality
guard shipped as written in CB-1.

Backlog (deferred, out of scope):

- **API-launched runs did not honor `enforce_worktree_isolation`**: `interfaces/api/v1/pipelines.py:84`
  (`start_pipeline_run`), `:225` (`resume_run`), `:312` (`submit_gate_decision`) set no policy.
  Resolvable via `db` + `body.project`/`run.project_name` using
  `await load_settings_async(db, <proj>)` (graceful try/except); needed an API background-run test
  harness. The CLI `sw run`/`resume` paths DO wire the policy. Closed by `TECH-013` (`ecb1afb0`,
  2026-08-19).
- Rebind the remaining process-spawning handlers (`generation`/`scenario` LanguageAtom,
  `context_assembler`, `validation_hydrator`, `facades`) to execution-root — incremental adoption.
- `run_tests`-in-worktree dependency/venv resolution robustness (M2) — if pytest can't resolve the
  project venv from the worktree, add explicit dep-path handling.
- Per-run (vs per-step) worktree isolation (M3) — delivered by `C-EXEC-06`.
- Container + worktree composition (M4) — owned by INT-US-09-SF01.
- Optional `sw run --sandbox` CLI override (M5).
- `master_story_roadmap.md` INT-US-09 status flip — only after this feature is committed (done, `795de2ad`).
