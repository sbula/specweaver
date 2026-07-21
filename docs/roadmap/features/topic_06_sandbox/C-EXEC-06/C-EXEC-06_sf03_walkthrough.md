# Walkthrough — C-EXEC-06 SF-03: Composition-Root Policy + Allow-List Population + Verifiable Proof

- **Commit boundary**: single **CB-1** (direct to `main`).
- **Impl plan**: `C-EXEC-06_sf03_implementation_plan.md` (APPROVED 2026-07-20).
- **Completes** `C-EXEC-06` (the per-run/session worktree isolation capability). Resolves `TECH-012`.

## What changed and why

SF-01/SF-02 built the *consumer* of per-run isolation — `RunContext.session_isolation` + `allowed_paths`,
and `execute_run`'s one-worktree lifecycle + authorized reconcile. **Nothing populated those fields.** SF-03
adds the *producer* / composition-root half:

1. **Settings knob (FR-7)** — `SandboxSettings.enforce_session_isolation` (opt-in, default off) +
   `session_allowed_paths` (allow-list override). `core/config/settings.py`. No loader change (the existing
   `[sandbox]` TOML splat parses the new keys).
2. **Composition-root helpers (FR-5)** — `core/flow/engine/runner_utils.py`:
   - `_derive_allowed_paths(spec_path)` → `["src/<stem>.py", "tests/test_<stem>.py"]`, `stem =
     spec_path.stem.replace("_spec","")`, **byte-matched to `generation.py`** so the allow-list equals the
     path the run actually generates (C1). Forward slashes (git `--name-only` form on all platforms).
   - `apply_session_policy(context, settings, logger)` — sets `session_isolation`; **only when on** populates
     `allowed_paths` (override, else derived). **NFR-2 guard**: off ⇒ `allowed_paths` stays `[]` so the
     per-step INT-US-09 `strip_merge` is unaffected. **C2**: compute-then-assign so a failure never leaves a
     half-applied "session on, empty allow-list" state (which would silently drop all generated code).
     Best-effort; never raises.
3. **CLI wiring (FR-5, FR-7)** — `core/flow/interfaces/cli.py`: both composition sites (`_execute_run`,
   `resume`) resolve settings once and call `apply_session_policy` next to the existing `enforce_isolation`
   line, inside the best-effort `try`.
4. **Verifiable proof (FR-8, NFR-4)** — a multi-step real-git e2e + a full-chain integration test.

**Deferred (documented):** API composition roots don't resolve the policy — minted as **`TECH-013`**.

## Tests

| Level | File | Cases |
|-------|------|-------|
| Unit | `test_settings_loader.py` (extended) | +11 (fields, defaults, TOML load, type rejection, independence) |
| Unit | `test_session_policy.py` (new) | 13 direct (`_derive_allowed_paths` C1/dotfile/fwd-slash; `apply_session_policy` NFR-2/C2/C3/degradation) |
| Integration | `test_cli_config_integration.py` (extended) | +7 (run+resume policy, NFR-2 guard, both-knobs, malformed-toml) |
| Integration | `test_session_policy_fullchain.py` (new, G2) | 2 (real toml → `apply_session_policy` → real session run → reconcile) |
| E2E | `test_c_exec_06_session_isolation_e2e.py` (new) | 4 (multi-step persistence + reconcile; NFR-4 `secret.py` stripped; G1 `docs/` hard-block over allow-list; un-isolated control; non-git fail-loud) |

**Full suite (re-run in Phase 4, from scratch):** unit **4727** · integration **481** · e2e **148** —
**5356 passed, 0 failures**, 21 skipped.

**Quality gates (Phase 5, re-run):** ruff ✅ · mypy ✅ (303 files) · C901 ✅ · file-size ✅ (0 errors) · tach ✅.

## HITL gate decisions

- **Impl-plan Phase 4 (audit)** — Q1 API scope: user chose **CLI-only + mint a roadmap ticket** → `TECH-013`
  created. Q6 commit boundary: user chose **single CB**. Q2–Q5: accepted as proposed.
- **Impl-plan Phase 5 (Red/Blue)** — found + fixed the **NFR-2 leak** (populating `allowed_paths` when session
  off would alter the per-step path); gated + directly tested.
- **Dev Phase 2 (task list)** — user pushed on "corner cases? graceful failure? e2e? integration?"; the matrix
  was expanded with C1/C2/C3 corner cases, degradation, and the integration/e2e split before approval.
- **Pre-commit Phase 2 (test gap)** — user approved **both G1 (docs hard-block e2e) + G2 (full-chain
  integration)**; both implemented in Phase 3.
- **Pre-commit Phase 3** — tests listed and approved before Phase 4.
- No gate was bypassed.

## Notes
- One test-expectation correction during dev: `Path(".md").stem == ".md"` (pathlib), so a dotfile spec derives
  `src/.md.py` — safe; the test asserts the true value.
- `.codebase-memory/` index artifacts are intentionally left out of the feature commit (committed standalone).
