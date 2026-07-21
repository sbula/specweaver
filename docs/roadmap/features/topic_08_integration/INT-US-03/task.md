# Task List — INT-US-03 SF-03: Zero-Trust Isolation + Verifiable Proof

- **Impl Plan**: docs/roadmap/features/topic_08_integration/INT-US-03/INT-US-03_sf03_implementation_plan.md
- **FRs**: FR-5 (sandboxed QA under the per-run policy), FR-8 (verifiable proof)
- **Policy**: Option C (AD-8) — opt-in default + DAL-driven auto-escalation, threshold DAL_B, opt-in per caller.
- **Commit boundary**: single **CB-1**. Foundation-first (ordering → settings → policy → wiring → proof).
- **(SF-01/SF-02 task records preserved in git history + walkthroughs.)**

## Tasks

- [x] **T1 — `DALLevel.rank` strictness ordering** (FR-5)
  - src: `src/specweaver/commons/enums/dal.py` — `rank` property (`DAL_A=5 … DAL_E=1`) beside `is_strict`.
  - test: `tests/unit/commons/enums/test_dal.py` — A>B>C>D>E; equality (`DAL_B.rank >= DAL_B.rank`); every level ranked.

- [x] **T2 — `SandboxSettings.auto_isolate_min_dal`** (FR-5)
  - src: `src/specweaver/core/config/settings.py` — `auto_isolate_min_dal: str = "DAL_B"`; validate it is a
    valid `DALLevel` name or the disable sentinel `"off"` (case-insensitive).
  - test: `tests/unit/core/config/test_settings_loader.py` — default `"DAL_B"`; accepts a level + `"off"`;
    TOML load; rejects an invalid value (`"DAL_Z"`).

- [x] **T3 — DAL auto-escalation in `apply_session_policy`** (FR-5, opt-in per caller)
  - src: `src/specweaver/core/flow/engine/runner_utils.py` — add keyword `dal_auto_escalate: bool = False`;
    when force-off AND `dal_auto_escalate`, escalate via `_dal_requires_isolation(context, sandbox, logger)`
    (read `auto_isolate_min_dal`; `"off"`/empty→False; resolve `dal = context.dal_level or
    DALResolver(project_path).resolve(spec_path if exists else project_path)`, cache onto `context.dal_level`,
    return `dal is not None and dal.rank >= DALLevel(threshold).rank`). Keep C2 compute-then-assign + NFR-2
    gating; best-effort (never raises). Default False ⇒ `sw run`/`sw resume` byte-identical.
  - test: `tests/unit/core/flow/engine/test_session_policy.py` — escalate+DAL_A→on+derived; DAL_B→on
    (equality); DAL_C→off + `allowed_paths==[]`; DAL None→off; **`dal_auto_escalate=False`+DAL_A→off** (sw run
    unaffected); `auto_isolate_min_dal="off"`+escalate+DAL_A→off; `enforce_session_isolation=true`→on regardless;
    DALResolver raises→best-effort off; caches `context.dal_level`.

- [x] **T4 — Wire the policy into `sw implement`** (FR-5)
  - src: `src/specweaver/workflows/implementation/interfaces/cli.py` — after the `RunContext(...)` build
    (~:248): `apply_session_policy(context, settings, logger, dal_auto_escalate=True)` (import from
    `core.flow.engine.runner_utils`; same boundary as the existing `PipelineRunner`/`RunContext` imports).
  - test: `tests/integration/...` — a project whose `context.yaml` marks `DAL_B` → implement context gets
    `session_isolation=True` + derived allow-list; no DAL marker → session off (host); `auto_isolate_min_dal="off"`
    → session off even at DAL_B.

- [x] **T5 — Verifiable-proof e2e** (FR-8, NFR-6)
  - test: new `tests/e2e/.../test_int_us_03_isolation_e2e.py` (real git+bash, skipif). [Happy] implement loop
    under session isolation (generation stub writes `src/<stem>.py`+`tests/test_<stem>.py`): `run_tests` runs
    pytest **worktree-bounded** (probe: cwd ∈ `.worktrees` AND generated file in-tree; guard `passed==1`),
    reconcile lands only allow-listed files; [Control] isolation off → host, probe FAILS at real root;
    [Hostile/NFR-4] stub also writes `secret.py` → stripped/absent; [Degradation] git/bash absent → skip; non-git
    under escalation → degrade to host (Q3).

- [ ] **T6 — Full suite + pre-commit gate (CB-1)**
  - Full unit/integration/e2e; fix any regression project-wide. Run pre-commit skill. HITL commit stop (direct to master).

## Adversarial Test Matrix (per task — 4 buckets)
| Task | Happy | Boundary/Edge | Graceful Degradation | Hostile/Wrong Input |
|------|-------|---------------|----------------------|---------------------|
| T1 | A>B>C>D>E ranks | threshold equality (`B>=B`) | — (pure) | every level ranked (no KeyError) |
| T2 | knob round-trips | default "DAL_B"; "off" accepted | malformed TOML → default | invalid level ("DAL_Z") rejected |
| T3 | escalate+DAL_A→on | DAL_B equality→on; DAL_C→off; None→off | DALResolver raises→off, no crash | dal_auto_escalate=False+DAL_A→off (sw run safe); "off" threshold→off |
| T4 | DAL_B project→implement session on | no marker→host; "off"→off | settings failure→off, run not crashed | — |
| T5 | generated code runs QA worktree-bounded | reconcile lands only allowed | non-git/no git+bash → host/skip | `secret.py` stripped; control probe FAILS at root |

## Progress
- Phase 2 (task breakdown): approved (Red/Blue R1/R5/R6 folded in).
- T1–T4 done (TDD). **Dev finding (Q3):** escalation now git-repo-checks and DEGRADES to host on a
  non-git project (never hard-fails). Fixed inherited `test_cli_implement.py` MagicMock settings (now real
  SandboxSettings so `enforce_session_isolation` is a real False).
- T5 (e2e) done: `test_int_us_03_isolation_e2e.py` — DAL_B escalation → bounded QA → reconcile; DAL_E control.
- Full suite (Step A): unit 4748 · integration 486 · e2e 150 (5384 passed, 0 failures). No regressions.
  (Fixed inherited MagicMock-settings failures in test_cli_implement.py, test_cli.py, test_cli_telemetry_flush.py.)
- Pre-commit gate (Step B): _running_.
  - Phase 1 (architecture): [x] ✅ no violations (tach clean; no new cross-layer edge).
  - Phase 2 (test gap): [x] combined analysis; user approved G1 + G2 + G4.
  - Phase 3 (implement tests): [x] G2 (sw-run-not-escalated integration), G4 (configurable threshold), G1 (invalid-threshold degrade). ruff clean.
  - Phase 4 (full suite): [x] unit 4750 · integration 487 · e2e 150 (5387 passed, 0 failures).
  - Phase 5 (code quality): [x] ruff, mypy (303), C901, file-size (0 err), tach — all clean.
  - Phase 6 (docs): [x] pipeline_engine_guide §7 (DAL-escalation policy), impl-plan as-built, design tracker Dev ✅.
  - Phase 7 (walkthrough): [x] INT-US-03_sf03_walkthrough.md.
  - Phase 7.5 (Red/Blue on code): [x] no critical findings; documented dirty-tree interaction (recommend leave-as-is: fail-loud protects uncommitted edits to the target).
  - Phase 8 (commit boundary): ⏸ HITL — awaiting user commit (direct to master).
