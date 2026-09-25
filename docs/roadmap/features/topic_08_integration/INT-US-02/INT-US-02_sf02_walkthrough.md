# INT-US-02 SF-02 — Walkthrough

**Commit boundary:** single **CB-1** (direct to `main`) · **Date:** 2026-07-23 · Plan:
[sf02](INT-US-02_sf02_implementation_plan.md) (APPROVED 2026-07-22; Q1 sharpened post-TECH-006,
Q2–Q4 = a)

## Delivered

`sw run new_feature` now co-authors in a terminal; before, no `context_provider` was wired at the
`run`/`resume` composition roots, so it could only PARK at a missing spec.

1. **Core seam** (`core/flow/interfaces/cli.py`) — the generic interaction-channel seam:
   `set_context_provider_factory()` + `_maybe_attach_provider()` at both composition sites. Core is
   terminal-agnostic: the factory owns interactivity and may return None; a caller-set provider always
   wins; a factory failure never breaks a run. Declared in tach.toml's `[[interfaces]]` — the designed
   surface declared, imports not widened. Future channels (`D-INTL-07` interview engine, `C-FLOW-11`
   work-unit channels) register through the same seam.
2. **Delivery factory** (`interfaces/cli/main.py`) — `_interactive_context_provider()`: TTY (patchable
   `_stdin_isatty()`) → `HITLProvider`; headless → None. TTY knowledge lives with the console.
3. **Parked runs exit 0** — `sw run`'s broad `except Exception` swallowed `typer.Exit(code=0)` (click's
   Exit is a RuntimeError subclass), so every PARKED run exited 1 with "Error: Exit:". An
   `except typer.Exit: raise` passthrough fixes it; found by G1.

## Proof

| Tests | Cases |
|---|---|
| Seam units (R1 reset fixture for the module-global) | 5 |
| Delivery-factory units (R4: registration proven end-to-end) | 3 |
| Composition integrations (TTY run + resume attach; headless None) | 3 |
| **G1** behavior test | headless `sw run new_feature` parks through the REAL runner, exit 0, nothing drafted |

The whole 5420-test suite runs non-TTY = the global FR-5 control.

| Check | Result |
|---|---|
| Full suite | unit 4768 · integration 502 · e2e 150 — **5420 passed, 0 failures** |
| Quality | ruff ✅ · mypy ✅ (303) · C901 ✅ · file-size ✅ · tach ✅ (incl. the interface declaration) · roadmap-sync ✅ |

Approvals: plan Q1 = (a) sharpened to the post-TECH-006 orientation (user-directed: generic seam name,
delivery-owned interactivity), Q2–Q4 = (a). Dev task list approved with R1 + R4. Pre-commit: user
approved G1 (fixed per the fix-inherited-failures rule). No gate bypassed.
