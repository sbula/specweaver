# Walkthrough — INT-US-03 SF-03: Zero-Trust Isolation + Verifiable Proof

- **Commit boundary**: single **CB-1** (direct to `main`).
- **Impl plan**: `INT-US-03_sf03_implementation_plan.md` (APPROVED 2026-07-21).
- **Closes** the US-3 flagship base contract (autonomous implementation). Consumes `C-EXEC-06` (per-run
  isolation); resolved the old architectural fork by *consuming* the shipped capability, not rebuilding it.

## What changed and why

`sw implement` ran its autonomous generate → QA → lint loop on the **host** — untrusted, LLM-generated code
executed against the real source root. SF-03 makes it run **worktree-bounded** when the risk warrants it,
reusing the per-run session isolation `C-EXEC-06` already built (whole loop in one worktree, single authorized
reconcile). The old SF-03 plan's AD-7 "crux" (carrying generated files across per-step worktrees) is moot under
per-run mode, so **no pipeline changes** were needed — just policy wiring + a proof.

**Policy (AD-8 — Option C): opt-in default + DAL-driven auto-escalation.**
1. `DALLevel.rank` — strictness ordering (A=5…E=1) so a threshold is comparable.
2. `SandboxSettings.auto_isolate_min_dal` — default `"DAL_B"`, `"off"` disables.
3. `apply_session_policy(..., dal_auto_escalate=True)` — new opt-in flag: when the explicit force-flag is off,
   session isolation auto-enables if the touched code's resolved DAL is at/above the threshold. **Opt-in per
   caller** — `sw implement` passes it; `sw run`/`sw resume` don't (byte-identical).
4. One-line wiring in the `sw implement` composition root.

**Net behavior:** high-assurance (DAL_A/B) code auto-sandboxes; small/low-DAL projects stay friction-free on
host — the worktree/reconcile cost lands only where the assurance level justifies it. `TECH-012` was already
resolved by `C-EXEC-06`; SF-03 makes `sw implement` actually consume it.

## Tests

| Level | File | Cases |
|-------|------|-------|
| Unit | `commons/enums/test_dal.py` (new) | 7 (`rank` ordering, threshold equality, is_strict alignment) |
| Unit | `test_settings_loader.py` (extended) | +6 (`auto_isolate_min_dal` default/levels/off/invalid/TOML) |
| Unit | `test_session_policy.py` (extended) | +13 (DAL_A/B/C/None, **non-git degrade**, no-escalate=sw-run-safe, off-threshold, force-on, cache, resolver-raises, **G4 configurable threshold**, **G1 invalid threshold**) |
| Integration | `test_cli_implement_isolation.py` (new) | 6 (DAL_B on, no-marker host, low-DAL host, off-threshold, **non-git degrade**) |
| Integration | `test_cli_config_integration.py` (extended) | +1 (**G2**: DAL_B project via `sw run` stays OFF — escalation is implement-only) |
| E2E | `test_int_us_03_isolation_e2e.py` (new) | 2 (DAL_B escalation → generated code runs QA worktree-bounded → reconcile lands only allow-listed; DAL_E control probe FAILS at real root) |

**Full suite (Phase 4, re-run):** unit **4750** · integration **487** · e2e **150** — **5387 passed, 0 failures**.
**Quality (Phase 5):** ruff ✅ · mypy ✅ (303) · C901 ✅ · file-size ✅ (0 err) · tach ✅.

## HITL gate decisions

- **Design intake:** established SF-03's original scope was delivered by C-EXEC-06; re-scoped to consume it.
  Isolation policy chosen as **Option C** (opt-in + DAL auto-escalation, threshold DAL_B), folded into SF-03.
  AD-5 (blanket default-on) superseded by AD-8.
- **Dev Phase 2 (task list):** approved; Red/Blue R1 (DAL target = runner-consistent), R5 (settings survives
  adapter — verified), R6 (e2e via committed bash generator + DAL context.yaml, no LLM) folded in.
- **Pre-commit Phase 2 (test gap):** user approved **G1 + G2 + G4**; implemented in Phase 3.
- **Pre-commit Phase 3:** tests listed and approved before Phase 4.
- No gate bypassed.

## Notes
- **Q3 (dev finding):** DAL auto-escalation git-repo-checks and **degrades to host** on a non-git project
  (never hard-fails); explicit force-on still fails-closed.
- Fixed inherited `MagicMock()`-settings failures in `test_cli_implement.py`, `workflows/implementation
  test_cli.py`, `test_cli_telemetry_flush.py` (a loose MagicMock made `enforce_session_isolation` read truthy).
