# Implementation Plan: Autonomous Implementation Integration — SF-03: Zero-Trust Isolation + Verifiable Proof

- **Feature ID**: INT-US-03
- **Sub-Feature**: SF-03 — Zero-Trust Isolation + Verifiable Proof
- **Design Document**: docs/roadmap/features/topic_08_integration/INT-US-03/INT-US-03_design.md
- **Design Section**: §Sub-Feature Breakdown → SF-03
- **Implementation Plan**: docs/roadmap/features/topic_08_integration/INT-US-03/INT-US-03_sf03_implementation_plan.md
- **Status**: APPROVED — re-scoped + approved by Steve Bula 2026-07-21 (**UNBLOCKED**). Old architectural fork
  resolved: per-run (session) worktree isolation was built as **`C-EXEC-06`** (SF-01/02/03 committed) +
  integrated by **`INT-US-09-SF05`** (✅). Isolation policy for `sw implement` = **Option C — opt-in default +
  DAL-driven auto-escalation** at threshold **`DAL_B`**, opt-in per caller (implement only). AD-5's blanket
  default-on is **superseded** by AD-8. All audit questions resolved.
- **Depends on**: SF-01 ✅, SF-02 ✅, **`C-EXEC-06` + `INT-US-09-SF05`** ✅.

## Scope (from the Design Document)
Make the autonomous `sw implement` loop run **worktree-bounded** so untrusted, freshly-generated code is
executed inside a git-worktree sandbox and reconciled back through the single authorized gate — **but only
when the risk warrants it**, so small/low-assurance projects keep today's friction-free host behavior.

**Isolation policy (AD-8 — Option C): opt-in default + DAL-driven auto-escalation.** Per-run session
isolation stays **off by default** (no worktree/reconcile friction for small projects), and the shared session
policy **auto-escalates to session isolation when the touched code's resolved DAL is `DAL_B` or stricter**
(`is_strict` — severe/critical). Operators can still force always-on (`[sandbox] enforce_session_isolation`)
or change/disable the threshold (`[sandbox] auto_isolate_min_dal`). Because the friction (ephemeral worktree +
`chore(sandbox)` reconcile commit + clean-tree requirement) then appears **only** on high-assurance code, it
lands exactly where it is justified and never on small projects. **FRs owned: FR-5, FR-8.**

**AD-7 superseded.** Session mode runs the whole loop in ONE worktree, so generated code persists in-tree
across steps with a single end-of-run reconcile — no per-step `allowed_paths` carry, no pipeline-step changes.

## Research Notes (Phase 0)

1. **Session mechanism is built and already reachable from `sw implement`.** `sw implement`
   (`workflows/implementation/interfaces/cli.py`) loads `settings` (`:193`), builds a `RunContext`
   (`:238-248`), runs via `PipelineRunner(pipeline, context).run()` (`:251-252`); `PipelineRunner.run()`
   → `execute_run` (`runner.py:133`) dispatches on `context.session_isolation` (`runner_utils.py:38`).
   Missing piece: `sw implement` never sets the session policy.
2. **The policy helper exists** — `apply_session_policy(context, settings, logger)` (`runner_utils.py`) sets
   `session_isolation` from `[sandbox] enforce_session_isolation` and, when on, populates `allowed_paths` via
   `_derive_allowed_paths(spec_path)` → `src/<stem>.py` + `tests/test_<stem>.py`. SF-03 adds the DAL escalation
   as an **opt-in parameter** (`dal_auto_escalate=False` default): **`sw implement` passes `True`;
   `sw run`/`sw resume` keep `False` (unchanged).** This is deliberate — escalation must fire only where
   untrusted code is generated. A blanket escalation in the shared helper would wrongly isolate benign
   `sw run` pipelines (e.g. `validate_only`) on high-DAL projects — pointless worktree overhead + a reconcile
   commit for a read-only run. Scoping it to implement avoids that.
3. **DAL machinery is ready.** `DALResolver(project_root).resolve(target_path) -> DALLevel | None`
   (`core/config/dal_resolver.py`) walks up `context.yaml` files reading `operational.dal_level`; missing/none
   ⇒ `None` (small projects). `DALLevel` (`commons/enums/dal.py`) has `is_strict` (True for `DAL_A`/`DAL_B`) but
   **no ordering** — a configurable threshold needs a strictness rank (A>B>C>D>E).
4. **Timing:** `PipelineRunner.__init__` resolves `context.dal_level` (`runner.py:84-91`, from
   `spec_path if exists else project_path`) — but that runs **after** the composition root calls
   `apply_session_policy`. So the policy must resolve DAL **itself** (via `DALResolver`), and should **cache it
   onto `context.dal_level`** (the runner then skips its re-resolution — one resolution, consistent target).
5. **`sw implement` generates exactly the two allow-listed files** (`src/<stem>.py`, `tests/test_<stem>.py`;
   lint-fix edits src in place; run_tests/validate create nothing) — so the tight `allowed_paths` never strips
   a legitimately-generated file. No stripping surprise.
6. **Backward-compat (NFR-2, NFR-4):** off ⇒ host loop exactly as SF-01/SF-02. Non-git project when isolation
   engages ⇒ degrade to host + warn (Q3), never break `sw implement`.

### External deps: git + bash (existing, proof only). No new tool, no pipeline-step change.

## Implementation Approach
> Pseudocode / ordered steps only.

### Change 1 — DAL strictness ordering (FR-5) · `commons/enums/dal.py`
Add a strictness rank to `DALLevel` beside `is_strict` (natural home) so thresholds are comparable —
e.g. a `rank` property: `DAL_A=5, DAL_B=4, DAL_C=3, DAL_D=2, DAL_E=1`. "≥ threshold in strictness" ⇒
`dal.rank >= threshold.rank`.

### Change 2 — settings knob (FR-5) · `core/config/settings.py`
Add to `SandboxSettings`: `auto_isolate_min_dal: str = "DAL_B"` — a `DALLevel` name (touched-code DAL at this
strictness or stricter auto-enables session isolation), or a disable sentinel (`"off"`, case-insensitive) for
pure opt-in. Validate it is a valid `DALLevel` name or `"off"`. Parsed by the existing `[sandbox]` TOML splat.

### Change 3 — DAL auto-escalation in `apply_session_policy` (FR-5) · `core/flow/engine/runner_utils.py`
Add a keyword-only `dal_auto_escalate: bool = False` param; keep the helper's C2 compute-then-assign + NFR-2 gating:
1. `session_on = enforce_session_isolation` (existing force-on).
2. **If not on AND `dal_auto_escalate`**, escalate: `session_on = _dal_requires_isolation(context, sandbox, logger)`.
3. `_dal_requires_isolation`: read `auto_isolate_min_dal`; if `"off"`/empty → `False`. Else resolve
   `dal = context.dal_level or DALResolver(context.project_path).resolve(<spec_path if exists else project_path>)`,
   cache it onto `context.dal_level`, and return `dal is not None and dal.rank >= DALLevel(threshold).rank`.
4. When `session_on`, populate `allowed_paths` as today. Whole thing stays inside the best-effort `try`
   (a DAL-resolution failure ⇒ falls back to off, run never crashes).
Default `dal_auto_escalate=False` ⇒ **`sw run`/`sw resume` behavior is byte-identical** (they don't pass it).

### Change 4 — wire the policy into `sw implement` (FR-5) · `workflows/implementation/interfaces/cli.py`
After the `RunContext(...)` build (`:238-248`): `apply_session_policy(context, settings, logger, dal_auto_escalate=True)`
(import from `core.flow.engine.runner_utils`; `workflows/implementation` already `consumes core.flow`). Implement
opts into DAL escalation; `sw run`/`sw resume` do not.

### Change 5 — verifiable proof (FR-8) · new test
Prove the implement loop runs QA on freshly-generated code worktree-bounded under isolation, with an
un-isolated control (NFR-6). Generation handler stubbed to emit deterministic files; `run_tests` runs for real.

### Files to modify
| File | Change | FR |
|------|--------|----|
| `src/specweaver/commons/enums/dal.py` | `DALLevel.rank` strictness ordering | FR-5 |
| `src/specweaver/core/config/settings.py` | `SandboxSettings.auto_isolate_min_dal` (default `"DAL_B"`) | FR-5 |
| `src/specweaver/core/flow/engine/runner_utils.py` | DAL auto-escalation in `apply_session_policy` (+ `_dal_requires_isolation`) | FR-5 |
| `src/specweaver/workflows/implementation/interfaces/cli.py` | call `apply_session_policy` in the implement `RunContext` | FR-5 |
| `tests/...` | see Test Plan | FR-5, FR-8 |
No pipeline-YAML / step changes. No new module.

## Test Plan (4 Adversarial Buckets)

**Unit — `DALLevel.rank`:** [Happy] `DAL_A.rank > DAL_B.rank > … > DAL_E.rank`; [Boundary] threshold-equality
(`DAL_B.rank >= DAL_B.rank`).

**Unit — settings knob:** [Happy] default `"DAL_B"`; round-trips a valid level + `"off"`; [Hostile] an invalid
value (`"DAL_Z"`) rejected.

**Unit — `apply_session_policy` DAL escalation (direct):** [Happy] `dal_auto_escalate=True` + force-off +
`auto_isolate_min_dal="DAL_B"` + touched DAL `DAL_A` → `session_isolation=True` + derived `allowed_paths`;
[Happy] DAL `DAL_B` → on (equality); [Boundary] DAL `DAL_C` → **off** (below threshold), `allowed_paths == []`
(NFR-2); [Boundary] DAL `None` (small project) → off; **[Boundary] `dal_auto_escalate=False` (the `sw run`
default) + DAL `DAL_A` → off** (escalation is caller-opt-in — proves `sw run`/`sw resume` are unaffected);
[Boundary] `auto_isolate_min_dal="off"` + escalate + DAL `DAL_A` → off (threshold disabled); [Boundary]
`enforce_session_isolation=true` → on regardless of DAL (force wins); [Degradation] `DALResolver` raises →
best-effort off, no crash; caches resolved DAL onto `context.dal_level`.

**Integration — implement composition (real):** [Happy] a project whose `context.yaml` marks `DAL_B` →
`sw implement` context gets `session_isolation=True` + derived allow-list; [Boundary] no DAL marker (small
project) → session off, host mode; [Boundary] `[sandbox] auto_isolate_min_dal="off"` → session off even at DAL_B.

**E2E — verifiable proof (FR-8, real git+bash):** [Happy] implement loop under session isolation (generation
stub writes `src/<stem>.py`+`tests/test_<stem>.py`): `run_tests` pytest runs **worktree-bounded** (probe: cwd ∈
`.worktrees` AND the generated file present in-tree), reconcile lands only allow-listed files; [Control]
isolation off → loop on host, probe FAILS at real root (no 0-collected false pass); [Hostile/NFR-4] a stub that
also writes `secret.py` → stripped, absent from real repo; [Degradation/NFR-4] git/bash absent → skips clean;
non-git under escalation → degrades to host (Q3).

## Audit (Phase 2) — resolved
| # | Question | Resolution |
|---|----------|-----------|
| Q1 | Default-on vs opt-in for `sw implement`. | **Option C (AD-8, approved 2026-07-21):** opt-in default **+ DAL-driven auto-escalation** at threshold **`DAL_B`**. Small/low-DAL projects stay host; high-assurance (A/B) code auto-sandboxes. Folded into SF-03 as a shared enhancement to `apply_session_policy`. |
| Q2 | Stem transform `.removesuffix` (implement CLI) vs `.replace` (`_derive_allowed_paths`). | Accept — identical for real `<name>_spec.md` inputs; unifying is a separate low-value refactor (C-EXEC-06 backlog). |
| Q3 | Escalation on a **non-git** project — hard-fail or degrade? | **Degrade to host + warn** — an isolation mode we auto-enabled must never break `sw implement`. (Explicit `enforce_session_isolation=true` may still fail-closed, matching `execute_run`.) |

## Architecture Verification (Phase 3)
- Changes: `commons/enums/dal.py` (additive property, lowest layer), `core/config/settings.py` (additive field),
  `core/flow/engine/runner_utils.py` (extend existing helper — new runtime use of `DALResolver`, already in
  `core.config`, which `core.flow` consumes), `workflows/implementation/interfaces/cli.py` (one call; module
  already `consumes core.flow`), `tests/`. **No new cross-layer edge, no boundary change, no architectural
  switch** (the switch was `C-EXEC-06`). `tach`/`ruff`/`mypy --strict` stay green. The DAL escalation is a
  policy-layer behavior in the shared helper — no parallel isolation logic. **Verdict:** no CRITICAL violation.

## Session Handoff
**Current status**: DRAFT re-scoped to Option C (2026-07-21), UNBLOCKED, all audit questions resolved. Ready
for Phase 5 finalization → `/specweaver-dev`. Closing SF-03 closes the US-3 base contract.
