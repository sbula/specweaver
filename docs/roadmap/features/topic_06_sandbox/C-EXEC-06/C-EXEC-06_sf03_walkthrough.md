# C-EXEC-06 SF-03 — Walkthrough

**Commit boundary:** single **CB-1** (direct to `main`), `bd5cedd2` · Plan:
[sf03](C-EXEC-06_sf03_implementation_plan.md) (APPROVED 2026-07-20) · **Completes** `C-EXEC-06`;
resolves `TECH-012`.

## Delivered

The composition-root half: SF-01/SF-02 built the consumer, SF-03 populates
`session_isolation` + `allowed_paths`.

| File | Change |
|---|---|
| `core/config/settings.py` | `SandboxSettings.enforce_session_isolation` (opt-in, default off) + `session_allowed_paths` (override). No loader change — the `[sandbox]` TOML splat parses the new keys |
| `core/flow/engine/runner_utils.py` | `_derive_allowed_paths(spec_path)` → `["src/<stem>.py", "tests/test_<stem>.py"]`, `stem = spec_path.stem.replace("_spec","")`, **byte-matched to `generation.py`** (C1), forward slashes. `apply_session_policy(context, settings, logger)` sets `session_isolation` and, **only when on**, `allowed_paths` (override, else derived). Off ⇒ `allowed_paths` stays `[]`, so the per-step INT-US-09 `strip_merge` is unaffected (NFR-2). Compute-then-assign (C2): a failure never leaves "session on, empty allow-list". Never raises |
| `core/flow/interfaces/cli.py` | `_execute_run` and `resume` resolve settings once and call `apply_session_policy` beside `enforce_isolation`, inside the best-effort `try` |

Since moved (`c3f36d54`): the helpers live in `core/flow/engine/isolation.py`, the e2e under
`tests/e2e/capabilities/sandbox/`.

## Proof

**Verifiable Proof (FR-8):** `tests/e2e/sandbox/test_session_worktree_isolation_e2e.py` +
`tests/integration/core/flow/engine/test_session_policy_fullchain.py`.

| Level | File | Cases |
|-------|------|-------|
| Unit | `test_settings_loader.py` (extended) | +11 (fields, defaults, TOML load, type rejection, independence) |
| Unit | `tests/unit/core/flow/engine/test_session_policy.py` (new) | 13 direct (`_derive_allowed_paths` C1/dotfile/fwd-slash; `apply_session_policy` NFR-2/C2/C3/degradation) |
| Integration | `tests/integration/core/flow/test_cli_config_integration.py` (extended) | +7 (run+resume policy, NFR-2 guard, both-knobs, malformed-toml) |
| Integration | `test_session_policy_fullchain.py` (new, G2) | 2 (real toml → `apply_session_policy` → real session run → reconcile) |
| E2E | `test_session_worktree_isolation_e2e.py` (new) | 4 (multi-step persistence + reconcile; NFR-4 `secret.py` stripped; G1 `docs/` hard-block over allow-list; un-isolated control; non-git fail-loud) |

| Check | Result |
|-------|--------|
| Unit / integration / e2e | **4727** · **481** · **148** — **5356 passed, 0 failures**, 21 skipped |
| ruff / mypy (303 files) / C901 / file-size (0 errors) / tach | ✅ |

Post-commit: C-EXEC-06 → ✅ in `capability_matrix` + `master_story_roadmap` (Verifiable Proof recorded); `pipeline_engine_guide.md §7` documents the per-run model.

Red/Blue on the code: no critical findings (traversal-safe, NFR-2 preserved, C2/C3 fail-closed).

## Findings still open

- API composition roots don't resolve the policy → **`TECH-013`**.
- Dotfile spec: `Path(".md").stem == ".md"`, so it derives `src/.md.py` — safe, matches nothing.
