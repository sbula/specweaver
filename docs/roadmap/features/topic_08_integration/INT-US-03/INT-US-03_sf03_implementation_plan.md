# INT-US-03 SF-03 — Zero-Trust Isolation + Verifiable Proof

**Status**: APPROVED — re-scoped + approved by Steve Bula 2026-07-21 (**UNBLOCKED**). Old
architectural fork resolved: per-run (session) worktree isolation was built as **`C-EXEC-06`**
(SF-01/02/03 committed) + integrated by **`INT-US-09-SF05`** (✅). Isolation policy for `sw implement`
= **Option C — opt-in default + DAL-driven auto-escalation** at threshold **`DAL_B`**, opt-in per
caller (implement only). AD-5's blanket default-on is **superseded** by AD-8. All audit questions
resolved. Implemented 2026-07-21. · **FRs owned**: FR-5, FR-8 · **Depends on**: SF-01 ✅, SF-02 ✅,
**`C-EXEC-06` + `INT-US-09-SF05`** ✅ · Design: [INT-US-03_design.md](INT-US-03_design.md)
§Sub-features → SF-03

## Goal

The autonomous `sw implement` loop runs **worktree-bounded** — untrusted, freshly-generated code
executes inside a git-worktree sandbox and is reconciled back through the single authorized gate —
**only when the risk warrants it**. Small/low-assurance projects keep friction-free host behavior.

**Policy (AD-8 — Option C):** per-run session isolation is **off by default**; the shared session
policy **auto-escalates when the touched code's resolved DAL is `DAL_B` or stricter** (`is_strict` —
severe/critical). Operators force always-on with `[sandbox] enforce_session_isolation` or
change/disable the threshold with `[sandbox] auto_isolate_min_dal`. The friction (ephemeral worktree
+ `chore(sandbox)` reconcile commit + clean-tree requirement) lands only on high-assurance code.

Session mode runs the whole loop in ONE worktree, so generated code persists in-tree across steps
with a single end-of-run reconcile — no per-step `allowed_paths` carry, no pipeline-step changes
(AD-7 superseded).

## Where it plugs in

| Fact | Where |
|---|---|
| `sw implement` loads `settings` (`:193`), builds a `RunContext` (`:238-248`), runs `PipelineRunner(pipeline, context).run()` (`:251-252`). It never sets the session policy — the missing piece | `workflows/implementation/interfaces/cli.py` |
| `PipelineRunner.run()` → `execute_run`, which dispatches on `context.session_isolation` | `runner.py:133`, `runner_utils.py:38` |
| `apply_session_policy(context, settings, logger)` sets `session_isolation` from `[sandbox] enforce_session_isolation` and, when on, populates `allowed_paths` via `_derive_allowed_paths(spec_path)` → `src/<stem>.py` + `tests/test_<stem>.py` | `runner_utils.py` |
| `DALResolver` walks up `context.yaml` files reading `operational.dal_level`; missing/none ⇒ `None` (small projects) | `core/config/dal_resolver.py` |
| `DALLevel.is_strict` (True for `DAL_A`/`DAL_B`) — but **no ordering**; a configurable threshold needs a strictness rank (A>B>C>D>E) | `commons/enums/dal.py` |
| `PipelineRunner.__init__` resolves `context.dal_level` from `spec_path if exists else project_path` — **after** the composition root calls `apply_session_policy`. So the policy resolves DAL **itself** and **caches it onto `context.dal_level`** (the runner then skips re-resolution — one resolution, consistent target) | `runner.py:84-91` |

- `DALResolver(project_root).resolve(target_path) -> DALLevel | None` is the resolution entry point.
- `sw implement` generates exactly the two allow-listed files (`src/<stem>.py`,
  `tests/test_<stem>.py`; lint-fix edits src in place; run_tests/validate create nothing), so the
  tight `allowed_paths` never strips a legitimately-generated file.
- Why escalation is **opt-in per caller**: a blanket escalation in the shared helper would isolate
  benign `sw run` pipelines (e.g. `validate_only`) on high-DAL projects — pointless worktree overhead
  + a reconcile commit for a read-only run.
- Backward-compat (NFR-2, NFR-4): off ⇒ host loop exactly as SF-01/SF-02. Non-git project when
  isolation engages ⇒ degrade to host + warn (Q3).

External: git + bash (existing, proof only). No new tool, no pipeline-step change.

## Changes

Single commit boundary **CB-1**, foundation-first: ordering → settings → policy → wiring → proof.

1. **DAL strictness ordering** (FR-5) · `commons/enums/dal.py` — a `rank` property beside
   `is_strict`: `DAL_A=5, DAL_B=4, DAL_C=3, DAL_D=2, DAL_E=1`. "≥ threshold in strictness" ⇒
   `dal.rank >= threshold.rank`.
2. **Settings knob** (FR-5) · `core/config/settings.py` — `SandboxSettings.auto_isolate_min_dal: str =
   "DAL_B"`: a `DALLevel` name, or the disable sentinel `"off"` (case-insensitive) for pure opt-in.
   Validated. Parsed by the existing `[sandbox]` TOML splat.
3. **DAL auto-escalation in `apply_session_policy`** (FR-5) · `core/flow/engine/runner_utils.py` —
   keyword-only `dal_auto_escalate: bool = False`; keeps the helper's C2 compute-then-assign + NFR-2
   gating:
   1. `session_on = enforce_session_isolation` (existing force-on).
   2. **If not on AND `dal_auto_escalate`**: `session_on = _dal_requires_isolation(context, sandbox, logger)`.
   3. `_dal_requires_isolation`: read `auto_isolate_min_dal`; `"off"`/empty → `False`. Else resolve
      `dal = context.dal_level or DALResolver(context.project_path).resolve(<spec_path if exists else project_path>)`,
      cache it onto `context.dal_level`, return `dal is not None and dal.rank >= DALLevel(threshold).rank`.
   4. When `session_on`, populate `allowed_paths` as today. All inside the best-effort `try` (a
      DAL-resolution failure ⇒ off, run never crashes).

   Default `dal_auto_escalate=False` ⇒ **`sw run`/`sw resume` byte-identical**.
4. **Wire the policy into `sw implement`** (FR-5) · `workflows/implementation/interfaces/cli.py` —
   after the `RunContext(...)` build (`:238-248`):
   `apply_session_policy(context, settings, logger, dal_auto_escalate=True)`, imported from
   `core.flow.engine.runner_utils` (`workflows/implementation` already `consumes core.flow`).
5. **Verifiable proof** (FR-8) · new e2e — QA on freshly-generated code runs worktree-bounded under
   isolation, with an un-isolated control (NFR-6). Generation stubbed to emit deterministic files;
   `run_tests` runs for real.

| File | Change | FR |
|------|--------|----|
| `src/specweaver/commons/enums/dal.py` | `DALLevel.rank` strictness ordering | FR-5 |
| `src/specweaver/core/config/settings.py` | `SandboxSettings.auto_isolate_min_dal` (default `"DAL_B"`) | FR-5 |
| `src/specweaver/core/flow/engine/runner_utils.py` | DAL auto-escalation in `apply_session_policy` (+ `_dal_requires_isolation`) | FR-5 |
| `src/specweaver/workflows/implementation/interfaces/cli.py` | call `apply_session_policy` in the implement `RunContext` | FR-5 |
| `tests/...` | see Tests | FR-5, FR-8 |

No pipeline-YAML / step changes. No new module.

## Tests

| Tier | Bucket | Case |
|---|---|---|
| Unit — `DALLevel.rank` (`tests/unit/commons/enums/test_dal.py`) | Happy | `DAL_A.rank > DAL_B.rank > … > DAL_E.rank` |
| | Boundary | threshold equality (`DAL_B.rank >= DAL_B.rank`) |
| | Hostile | every level ranked (no KeyError) |
| Unit — settings knob (`tests/unit/core/config/test_settings_loader.py`) | Happy | default `"DAL_B"`; round-trips a valid level + `"off"`; TOML load |
| | Degradation | malformed TOML → default |
| | Hostile | invalid value (`"DAL_Z"`) rejected |
| Unit — `apply_session_policy` (`tests/unit/core/flow/engine/test_session_policy.py`) | Happy | `dal_auto_escalate=True` + force-off + `auto_isolate_min_dal="DAL_B"` + touched DAL `DAL_A` → `session_isolation=True` + derived `allowed_paths`; `DAL_B` → on (equality) |
| | Boundary | `DAL_C` → **off**, `allowed_paths == []` (NFR-2); DAL `None` (small project) → off; **`dal_auto_escalate=False` (the `sw run` default) + `DAL_A` → off**; `auto_isolate_min_dal="off"` + escalate + `DAL_A` → off; `enforce_session_isolation=true` → on regardless of DAL |
| | Degradation | `DALResolver` raises → best-effort off, no crash; resolved DAL cached onto `context.dal_level` |
| Integration — implement composition (real) | Happy | `context.yaml` marks `DAL_B` → `sw implement` context gets `session_isolation=True` + derived allow-list |
| | Boundary | no DAL marker → session off, host mode; `[sandbox] auto_isolate_min_dal="off"` → off even at DAL_B |
| | Degradation | settings failure → off, run not crashed |
| E2E — proof (FR-8, real git+bash, skipif) | Happy | generation stub writes `src/<stem>.py`+`tests/test_<stem>.py`; `run_tests` pytest runs **worktree-bounded** (probe: cwd ∈ `.worktrees` AND the generated file present in-tree; guard `passed==1`); reconcile lands only allow-listed files |
| | Control | isolation off → loop on host, probe FAILS at real root (no 0-collected false pass) |
| | Hostile (NFR-4) | a stub that also writes `secret.py` → stripped, absent from real repo |
| | Degradation (NFR-4) | git/bash absent → skips clean; non-git under escalation → degrades to host (Q3) |

## Decisions (audit)

| # | Question | Resolution |
|---|----------|-----------|
| Q1 | Default-on vs opt-in for `sw implement`. | **Option C (AD-8, approved 2026-07-21):** opt-in default **+ DAL-driven auto-escalation** at threshold **`DAL_B`**. Small/low-DAL projects stay host; high-assurance (A/B) code auto-sandboxes. Folded into SF-03 as a shared enhancement to `apply_session_policy`. |
| Q2 | Stem transform `.removesuffix` (implement CLI) vs `.replace` (`_derive_allowed_paths`). | Accept — identical for real `<name>_spec.md` inputs; unifying is a separate low-value refactor (C-EXEC-06 backlog). |
| Q3 | Escalation on a **non-git** project — hard-fail or degrade? | **Degrade to host + warn** — an isolation mode we auto-enabled must never break `sw implement`. (Explicit `enforce_session_isolation=true` may still fail-closed, matching `execute_run`.) |

Red/Blue on the task list, folded in: R1 (DAL target = runner-consistent), R5 (settings survives the
adapter — verified), R6 (e2e via a committed bash generator + DAL `context.yaml`, no LLM).

Architecture check: `commons/enums/dal.py` (additive property, lowest layer),
`core/config/settings.py` (additive field), `core/flow/engine/runner_utils.py` (extends the existing
helper — new runtime use of `DALResolver`, already in `core.config`, which `core.flow` consumes),
`workflows/implementation/interfaces/cli.py` (one call). **No new cross-layer edge, no boundary
change, no architectural switch** (the switch was `C-EXEC-06`). `tach`/`ruff`/`mypy --strict` stay
green. No parallel isolation logic. No CRITICAL violation.

## As built (2026-07-21)

As planned, plus Q3: DAL auto-escalation **git-repo-checks** the project and **degrades to host**
(with a warning) on a non-git project. An explicit `enforce_session_isolation=true` still
fails-closed at `execute_run`.

- `commons/enums/dal.py` — `DALLevel.rank` (A=5…E=1) beside `is_strict`.
- `core/config/settings.py` — `SandboxSettings.auto_isolate_min_dal: str = "DAL_B"` + a validator
  (valid `DALLevel` name or `"off"`).
- `core/flow/engine/runner_utils.py` — `apply_session_policy` keyword `dal_auto_escalate=False`;
  `_dal_requires_isolation` resolves the run DAL (reusing/caching `context.dal_level`), True iff
  `dal.rank >= threshold.rank`.
- `workflows/implementation/interfaces/cli.py` — one `apply_session_policy(...,
  dal_auto_escalate=True)` call after the `RunContext` build.

**Verifiable Proof (FR-8):** `tests/e2e/sandbox/test_implement_loop_worktree_isolation_e2e.py` +
`tests/integration/interfaces/cli/test_cli_implement_isolation.py`. Tests and results:
[walkthrough](INT-US-03_sf03_walkthrough.md). Committed `64d44a71`.

**Since moved** (`c3f36d54`, 2026-08-12, `runner_utils` retired): `apply_session_policy` and
`_dal_requires_isolation` → `core/flow/engine/isolation.py`; `execute_run` →
`core/flow/engine/session.py`. Line refs above are as of the plan's date.
