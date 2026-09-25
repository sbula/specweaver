# INT-US-03 SF-03 — Walkthrough

**Commit boundary:** single **CB-1** (direct to `main`, `64d44a71`) · **Date:** 2026-07-21 · Plan:
[sf03](INT-US-03_sf03_implementation_plan.md) (APPROVED 2026-07-21)

## Delivered

`sw implement` runs its generate → QA → lint loop **worktree-bounded** when the risk warrants it, by
consuming the per-run session isolation `C-EXEC-06` already built (whole loop in one worktree,
single authorized reconcile). **No pipeline changes** — policy wiring + a proof. Closes the US-3
flagship base contract (autonomous implementation). Replaces host execution of untrusted,
LLM-generated code against the real source root.

**Policy (AD-8 — Option C): opt-in default + DAL-driven auto-escalation.**

1. `DALLevel.rank` — strictness ordering (A=5…E=1) so a threshold is comparable.
2. `SandboxSettings.auto_isolate_min_dal` — default `"DAL_B"`, `"off"` disables.
3. `apply_session_policy(..., dal_auto_escalate=True)` — when the explicit force-flag is off,
   session isolation auto-enables if the touched code's resolved DAL is at/above the threshold.
   **Opt-in per caller** — `sw implement` passes it; `sw run`/`sw resume` don't (byte-identical).
4. One-line wiring in the `sw implement` composition root.

Net: high-assurance (DAL_A/B) code auto-sandboxes; small/low-DAL projects stay on host. `TECH-012`
was already resolved by `C-EXEC-06`; SF-03 makes `sw implement` consume it.

- **Q3:** DAL auto-escalation git-repo-checks and **degrades to host** on a non-git project (never
  hard-fails); explicit force-on still fails-closed.
- Fixed inherited `MagicMock()`-settings failures in `test_cli_implement.py`,
  `workflows/implementation test_cli.py`, `test_cli_telemetry_flush.py` (a loose MagicMock made
  `enforce_session_isolation` read truthy) — they now use a real `SandboxSettings`.
- Docs: `pipeline_engine_guide.md §7` (DAL-escalation policy). Post-commit: US-3 → 🟢.

## Proof

| Level | File | Cases |
|-------|------|-------|
| Unit | `commons/enums/test_dal.py` (new) | 7 (`rank` ordering, threshold equality, is_strict alignment) |
| Unit | `test_settings_loader.py` (extended) | +6 (`auto_isolate_min_dal` default/levels/off/invalid/TOML) |
| Unit | `test_session_policy.py` (extended) | +13 (DAL_A/B/C/None, **non-git degrade**, no-escalate=sw-run-safe, off-threshold, force-on, cache, resolver-raises, **G4 configurable threshold**, **G1 invalid threshold**) |
| Integration | `test_cli_implement_isolation.py` (new) | 6 (DAL_B on, no-marker host, low-DAL host, off-threshold, **non-git degrade**) |
| Integration | `test_cli_config_integration.py` (extended) | +1 (**G2**: DAL_B project via `sw run` stays OFF — escalation is implement-only) |
| E2E | `test_implement_loop_worktree_isolation_e2e.py` (new) | 2 (DAL_B escalation → generated code runs QA worktree-bounded → reconcile lands only allow-listed; DAL_E control probe FAILS at real root) |

**Full suite:** unit **4750** · integration **487** · e2e **150** — **5387 passed, 0 failures**.
**Quality:** ruff ✅ · mypy ✅ (303) · C901 ✅ · file-size ✅ (0 err) · tach ✅.

Approvals: SF-03 re-scoped to consume `C-EXEC-06`; Option C chosen (threshold DAL_B), AD-5
superseded by AD-8; task list approved with Red/Blue R1/R5/R6; test gaps G1 + G2 + G4 approved and
implemented. No gate bypassed.

## Findings still open

- **Dirty-tree interaction** (Red/Blue on code, no critical findings): under escalation the
  reconcile fails loud on a dirty real tree. Left as-is: fail-loud protects uncommitted edits to the
  target.
