# Implementation Plan: Zero-Trust Sandbox — Base Integration Contract (INT-US-09)

- **Feature ID**: INT-US-09
- **Design Document**: docs/roadmap/features/topic_08_integration/INT-US-09/INT-US-09_design.md
- **Implementation Plan**: docs/roadmap/features/topic_08_integration/INT-US-09/INT-US-09_implementation_plan.md
- **Status**: APPROVED — approved by Steve Bula on 2026-07-16

> Single, non-decomposed feature (no `_sfNN_` suffix — the `INT-US-09-SF01..SF04` labels are
> reserved for the excluded add-on sub-stories). Organized internally by 4 commit boundaries.

## Scope

Wire the three built Core-Required capabilities — **US-5** (Git Worktree Bouncer), **E-EXEC-01**
(SubprocessExecutor), **C-EXEC-02** (BashActionAtom) — into one enforceable, **container-free**
host-execution flow. When an opt-in US-9 isolation policy is on, the untrusted-**execution**
surfaces (`action: bash` and `run_tests`/pytest) run inside an ephemeral git worktree with the
`SubprocessExecutor` boundary rebound to the worktree source tree; static-analysis QA (ruff/tach)
and all other handlers are unchanged. Covers **FR-1…FR-6**.

**Strictly excluded**: containerization (`B-EXEC-01`/`D-EXEC-01`/Podman), and INT-US-09-SF01..SF04.

## Research Notes

Exact current signatures/locations (research findings — quoted, not authored):

- **`RunContext`** — Pydantic v2 `BaseModel` at `src/specweaver/core/flow/handlers/base.py:30`
  (`model_config = ConfigDict(arbitrary_types_allowed=True)`). Has `project_path: Path` (:47),
  `output_dir: Path | None = None` (:55), `config: Any = None  # SpecWeaverSettings | None` (:53).
  **No** `execution_root` field today. `Path` is imported at runtime (`base.py:10`), so a new
  `Path | None` field needs no import. QA handlers read the policy via `context.config.sandbox`.
- **`PipelineStep`** — `src/specweaver/core/flow/engine/models.py:202`; `use_worktree: bool = False`
  at **`:221`** (exact).
- **Runner gate** — `src/specweaver/core/flow/engine/runner.py:314-337`; the branch
  `if getattr(step_def, "use_worktree", False):` at **`:320`** dispatches to `execute_in_sandbox`,
  else `await handler.execute(step_def, self._context)`. `self._context` is the single shared
  RunContext, mutated in place each step (`:316-318`).
- **`execute_in_sandbox`** — `src/specweaver/core/flow/engine/runner_utils.py:136`; builds
  `isolated_context = copy.copy(context)` then sets `isolated_context.output_dir =
  context.project_path / wt_path` (**`:160-162`**). `wt_path = f".worktrees/{task_id}"` (:151).
  Drives `GitAtom` intents `worktree_add`/`worktree_sync`/`strip_merge`/`worktree_teardown`; teardown
  in a `finally` (:183-185).
- **`setup_sandbox_caches`** — `runner_utils.py:89`; symlinks caches incl. **`.specweaver`** (:103)
  into the worktree → `.specweaver/scripts` resolves *within* the worktree; but `.specweaver` is a
  shared symlink (reservations/vault are shared — the documented shared-cache seam, AD-4).
- **`SandboxSettings`** — `src/specweaver/core/config/settings.py:114-122`; one field today
  (`execution_mode: Literal["host","container"] = "host"`). `SpecWeaverSettings` (:125-133) exposes
  `sandbox: SandboxSettings = SandboxSettings()`. Pydantic v2 `BaseModel` (no strict).
- **TOML loader** — `settings_loader.py:73-91`; `_load_toml_sandbox` does
  `SandboxSettings(**sandbox_data)` (:88) → a new field is auto-loaded from `[sandbox]`; no loader
  change strictly required (docstring/test update only).
- **Composition roots that BUILD RunContext** (critical — H1): the primary run/resume paths
  **do NOT set `config=`**: `src/specweaver/core/flow/interfaces/cli.py:251` (run) and `:435`
  (resume); API `src/specweaver/interfaces/api/v1/pipelines.py:84`, `:225`, `:312`. So
  `context.config.sandbox` is `None` on real `sw run`/API runs and the policy would never be read.
  The pattern to mirror is `src/specweaver/workflows/implementation/interfaces/cli.py:142`
  (`config=settings`). `load_settings` is already imported in `cli.py` (:261/273/276).
- **In-scope handlers** (untrusted execution): `BashActionHandler._get_atom` returns
  `BashActionAtom(cwd=context.project_path)` (`core/flow/handlers/bash_action.py:68`);
  `ValidateTestsHandler._get_atom` returns
  `QARunnerAtom(cwd=context.project_path, sandbox_settings=...)`
  (`core/flow/handlers/validation.py:403-408`) and calls `atom.run({"intent": "run_tests", ...})`
  (`:367-369`). **`LintFixHandler`** calls `{"intent": "run_linter"}` (`lint_fix.py:74`) — **ruff,
  static, out of scope**. `BashActionAtom.__init__(cwd)` sets `_scripts_root = cwd/.specweaver/scripts`
  (`sandbox/execution/core/atom.py:65-67`); executor built as `SubprocessExecutor(cwd=self._cwd,...)`
  (`:106`).
- **Test patterns**: `tests/integration/core/flow/engine/test_runner_sandbox.py` patches
  `GitAtom.run` (autospec) and asserts intent order `[worktree_add, worktree_sync, strip_merge,
  worktree_teardown]` and that the handler sees `".worktrees" in str(ctx.output_dir)`.
  `tests/e2e/sandbox/test_executor_e2e.py` drives a real `SubprocessExecutor` (no marker).

## Proposed Changes

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
| `tests/e2e/sandbox/test_int_us_09_isolation_e2e.py` | NEW | Real-worktree unmocked proof (FR-6). |
| `tests/unit/**` + `tests/integration/**` | NEW/MODIFY | Unit + integration coverage per Test Plan. |
| `docs/dev_guides/pipeline_engine_guide.md`, `subprocess_execution.md` | MODIFY | Doc updates (pre-commit). |

## Implementation Sequence (by commit boundary — pseudocode)

### CB-1 — Config surface + composition-root wiring (foundational)
*Rationale: nothing downstream can read the policy until `context.config.sandbox` is populated on the real run path.*
1. Add the field to `SandboxSettings` (one line; mirrors `execution_mode`).
2. **CLI (must-do, the primary `sw run` surface):** at `cli.py:251` and `:435`, resolve settings
   once (composition root, ADR-002) and pass `config=`:
   ```
   settings = load_settings(db, project)      # already imported at cli.py:261/273/276
   context = RunContext(..., db=db, config=settings)   # add config=
   ```
3. **API:** wire `config=` at the 3 `pipelines.py` sites **iff** settings are readily resolvable
   there (check what the API already loads). If it would require a non-trivial API refactor, do NOT
   force it into this CB — record it as an explicit Backlog gap ("API-launched runs do not yet honor
   `enforce_worktree_isolation`") so the limitation is documented, **not silently dropped**.
4. Verify/add any new `tach.toml` edge introduced by these imports (esp. `interfaces.api` →
   `core.config` if new) and run `tach check`. (`cli.py` already imports `load_settings` → no new edge.)
5. Confirm no code path asserts `context.config is None` on these paths (grep guard).

### CB-2 — Execution-root field + tri-state flag + gate resolution
1. `RunContext`: add `execution_root: Path | None = None` (semantics: the root untrusted processes
   bind their `cwd` to; `None` ⇒ callers fall back to `project_path`).
2. `PipelineStep.use_worktree`: `bool` → `bool | None`, default `None`.
3. Runner gate (`runner.py:320`) — replace the plain `getattr` with an ordered resolver:
   ```
   step_val = step_def.use_worktree                 # True | False | None
   policy_on = bool(context.config and context.config.sandbox
                    and context.config.sandbox.enforce_worktree_isolation)
   should_isolate = step_val if step_val is not None else policy_on
   if should_isolate: result = await execute_in_sandbox(...)
   else:              result = await handler.execute(step_def, self._context)
   ```
4. `execute_in_sandbox`: alongside `output_dir`, set
   `isolated_context.execution_root = context.project_path / wt_path` (the worktree root, so
   `.specweaver/scripts` resolves under it).

### CB-3 — Boundary hand-off in the two untrusted handlers
1. `bash_action.py:68`: `BashActionAtom(cwd=context.execution_root or context.project_path)`.
2. `validation.py:408` (ValidateTests): `QARunnerAtom(cwd=context.execution_root or context.project_path, sandbox_settings=...)`.
3. No change to `BashActionAtom`/`QARunnerAtom` internals — they already accept `cwd`; the
   `.specweaver/scripts` `WorkspaceBoundary` and `shutil.which("bash")` resolution stay intact
   (they re-derive from the passed `cwd`, which now points inside the worktree).
4. Explicitly do **not** touch `lint_fix.py`, `validation_hydrator.py`, `facades.py`, or the
   LanguageAtom/CodeStructure handlers (static or out-of-scope).

> [!CAUTION]
> Handlers must read `execution_root` off the **context parameter passed to `execute()`/`_get_atom()`**
> (the `isolated_context` that `execute_in_sandbox` builds), NOT `self._context`/`runner._context`.
> Research-confirmed: `execute_in_sandbox` calls `handler.execute(step_def, isolated_context)` and
> `_get_atom(context)` uses that passed context. `copy.copy` is shallow, which is fine — the new
> `execution_root` is set on the isolated copy only; the original context's `execution_root` stays
> `None` (non-isolated steps keep `project_path`).

> [!NOTE]
> Edge case: `.specweaver` is symlinked into the worktree only `if src.exists()`
> (`setup_sandbox_caches`). A project that runs `action: bash` from `.specweaver/scripts` necessarily
> has `.specweaver`, so the symlink exists before the bash handler runs — but note this dependency.

### CB-4 — Verifiable proof (e2e) + fail-closed check + docs
1. `execute_in_sandbox` fail-closed (H3): the existing code already raises `RuntimeError` when
   `worktree_add` returns non-success. Improve the message **using GitAtom's actual failure**
   (`add_res.message`) — do NOT add a raw `.git` filesystem probe in the engine (that would violate
   NFR-2/AD-1 — all git status goes through `GitAtom`). Append an actionable hint when isolation was
   policy-/flag-triggered: `f"US-9 worktree isolation could not start ({add_res.message}). Ensure
   <project> is a git repository, or disable [sandbox].enforce_worktree_isolation."` — surface the
   real cause (may be non-git, worktree-exists, disk-full, etc.), not an assumed one.
2. New e2e test (see Test Plan) — real git repo + real worktree + real `action: bash`.
3. Docs: `pipeline_engine_guide.md` §7 (isolation now rebinds execution, not just `output_dir`;
   policy switch) and `subprocess_execution.md` (execution-root convention).

## Test Plan (TDD — red first)

**Unit**
- `SandboxSettings.enforce_worktree_isolation` defaults `False`; TOML `[sandbox]
  enforce_worktree_isolation = true` loads `True` (extend `test_settings_loader.py`).
- `PipelineStep.use_worktree` accepts `True`/`False`/`None`; default `None` (model test).
- Gate resolver truth table (parametrized): (step=None, policy=off)→host; (None, on)→isolate;
  (True, off)→isolate; (False, on)→host; (True, on)→isolate.
- `execute_in_sandbox` sets `isolated_context.execution_root` to `.worktrees/...` (assert via the
  existing `GitAtom.run` patch pattern from `test_runner_sandbox.py`).
- `bash_action._get_atom` / `validation.ValidateTests._get_atom`: with `context.execution_root` set,
  atom `cwd` == execution_root; with it `None`, `cwd` == `project_path` (unchanged-behavior guard).
- Composition root: RunContext built by `sw run` path carries `config.sandbox` (not `None`).

**Integration**
- Policy-on run with a `use_worktree=None` bash step routes through `execute_in_sandbox`
  (intent order asserted); policy-off + `None` does not (backward-compat).
- Fail-closed: policy-on run against a non-git tmp project raises the actionable error.

**E2E (FR-6 — primary proof, real + unmocked)** — `tests/e2e/sandbox/test_int_us_09_isolation_e2e.py`
- `git init` a real project in `tmp_path` with a `.specweaver/scripts/<name>.sh` that writes a
  sentinel to a **source-tree** path (e.g. `<root>/marker.txt` or `src/marker.py`) — **not** under
  `.specweaver/` (that dir is a shared symlink per AD-4 and would escape the worktree, giving a
  false result). Pipeline of one `action: bash` step, `config` with `enforce_worktree_isolation=True`;
  run via a real `PipelineRunner` (real `GitAtom`, real worktree).
- Assert: the sentinel lands under `.worktrees/...` (worktree source tree) and the **real** source
  root's `marker.txt` is absent (source root not directly mutated); worktree torn down after.
  Additional best-effort case: a `run_tests` step runs with `cwd` inside the worktree.
- Follow the local `tests/e2e/sandbox/` convention (no `@pytest.mark.e2e`); guard/skip cleanly at
  collection if `git` **or** `bash` is unavailable (`shutil.which` — mirrors the existing
  engine-availability skip pattern).

## FR / NFR / AD Coverage

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

## Backlog (deferred, out of scope)

- Rebind the remaining process-spawning handlers (`generation`/`scenario` LanguageAtom,
  `context_assembler`, `validation_hydrator`, `facades`) to execution-root — incremental adoption.
- `run_tests`-in-worktree dependency/venv resolution robustness (M2) — if pytest can't resolve the
  project venv from the worktree, add explicit dep-path handling.
- Per-run (vs per-step) worktree isolation optimization (M3).
- Container + worktree composition (owned by INT-US-09-SF01, not this contract) (M4).
- Optional `sw run --sandbox` CLI override (M5).
- `master_story_roadmap.md` INT-US-09 status flip — only after this feature is committed.

## Phase 5: Final Consistency Check

- **5.0 FR/NFR/AD coverage** — all FR-1…FR-6, applicable NFRs, and AD-1…AD-5 mapped in the Coverage table. None missing.
- **5.1 Open questions** — All resolved and documented inline. HITL-approved resolutions: H1 (wire `config` — CLI must-do, API best-effort-else-Backlog), H2 (isolate-all-by-default + explicit per-step opt-out), H3 (fail-closed with actionable message via GitAtom's real failure), H4 (scope = bash + `run_tests` only; `lint_fix`/static excluded), H5 (tri-state `use_worktree`), M1–M5 + L1–L3 as banked.
- **5.1a Agent-handoff risk** — Low. Every seam has an exact `file:line` and current signature in Research Notes; the gate resolver, tri-state, and rebind are given as pseudocode. Residual flagged: the API `pipelines.py` `config` wiring feasibility is a runtime check the dev step must confirm (else Backlog) — documented, not hidden.
- **5.2 Architecture & future compat** — Wiring only in `core.flow` + composition root; atom surfaces only; one-way `flow → sandbox.core`; new imports get `tach.toml` edges + `tach check` (CB-1.4). Forward-compatible: the `execution_root` + policy seam is exactly what SF01 (container) / SF02 (egress) would extend.
- **5.2a Principles** — *DDD*: US-9 ubiquitous language (worktree/executor/bash), no new bounded context. *KISS*: reuses `execute_in_sandbox`/`GitAtom`/`BashActionAtom`; adds one field + one gate resolver, no new subsystem. *DRY*: `execution_root or project_path` is the single rebind idiom; policy read centralized in the gate. *Hexagonal*: engine orchestrates, atoms adapt I/O, config is a passive port. *SoC*: config change (settings), gate change (runner), rebind (handlers) are distinct CBs.
- **5.2b Red/Blue** — 2 cycles run (below); corrections merged into CB-1/CB-4/Test Plan/CB-3 notes above.
- **5.3 Internal consistency** — Proposed-Changes tags (`NEW`/`MODIFY`) match the sequence; test names map to the code they exercise; no DB migration involved.
- **5.3a Code-detail limit** — Re-read every code block: all are pseudocode, gate-resolver logic, or signatures quoted from *existing* code (research findings). No ready-to-paste new-code class/algorithm bodies. ✅

### Red/Blue Team Review (2 cycles, pre-implementation)

- **RED-1.2 (HIGH)** API `config` wiring may force an API refactor → **fixed**: CLI is must-do; API best-effort with an explicit documented Backlog gap (no silent drop). (CB-1.3)
- **RED-1.5 (HIGH)** raw `.git` probe in the engine violates NFR-2/AD-1 → **fixed**: fail-closed routes through `GitAtom`'s real failure message. (CB-4.1)
- **RED-1.3 (MED)** e2e sentinel could target symlinked `.specweaver` → **fixed**: sentinel writes to a source-tree path; assert real root unmutated. (Test Plan)
- **RED-1.6 (MED)** e2e needs a `bash` skip guard → **fixed**: `shutil.which("git"/"bash")` collection-time skip. (Test Plan)
- **RED-2.2 (MED)** new imports need `tach` edges → **fixed**: CB-1.4 adds edge check + `tach check`.
- **RED-2.3 (MED)** handlers must read the isolated context, not `self._context` → **fixed**: CB-3 CAUTION note.
- **RED-2.4 (MED)** fail-closed must not assume the cause → **fixed**: surface GitAtom's actual message. (CB-4.1)
- **RED-1.1 (LOW)** `use_worktree` `bool→bool|None` serialization → only reader is the gate (research-confirmed); model test covers all 3 states.
- Converged: 0 CRITICAL / 0 HIGH / (MED below threshold) after 2 cycles.

## HITL Gate — Approval Required

Implementation plan complete. Awaiting explicit approval before any code is written (TDD via the `dev` skill).
