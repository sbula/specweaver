# Walkthrough — INT-US-02 SF-02: Composition-Root Provider Wiring

- **Commit boundary**: single **CB-1** (direct to `main`). Impl plan APPROVED 2026-07-22
  (Q1 sharpened post-TECH-006; Q2–Q4 = a).

## What changed and why

`sw run new_feature` could only PARK at a missing spec — no `context_provider` was ever wired at the
`run`/`resume` composition roots. SF-02 adds the **generic interaction-channel seam**
(post-TECH-006-oriented, per HITL):

1. **Core seam** (`core/flow/interfaces/cli.py`): `set_context_provider_factory()` +
   `_maybe_attach_provider()` at both composition sites. Core is terminal-agnostic — the factory owns
   interactivity and may return None; a caller-set provider always wins; factory failure never breaks a
   run. Declared in tach.toml's `[[interfaces]]` (the enforcement caught the undeclared symbol — fixed by
   declaring the designed surface, not widening imports). Future channels (`D-INTL-07` interview engine,
   `C-FLOW-11` work-unit channels) register through this same seam.
2. **Delivery factory** (`interfaces/cli/main.py`): `_interactive_context_provider()` — TTY (patchable
   `_stdin_isatty()`) → `HITLProvider`; headless → None. TTY knowledge lives with the console, not in core.

**Inherited defect found & fixed (via G1):** `sw run`'s broad `except Exception` swallowed
`typer.Exit(code=0)` — every PARKED run exited 1 with "Error: Exit:". Now parked runs exit 0 as the code
always intended (`except typer.Exit: raise` passthrough).

## Tests
5 seam units (R1 reset fixture) · 3 delivery-factory units (R4 registration proof) · 3 composition
integrations (TTY run+resume attach; headless None) · **G1**: headless `sw run new_feature` parks through
the REAL runner, exit 0, nothing drafted. The whole 5420-test suite runs non-TTY = global FR-5 control.

**Full suite:** unit 4768 · integration 502 · e2e 150 — 5420 passed, 0 failures.
**Quality:** ruff ✅ · mypy ✅ (303) · C901 ✅ · file-size ✅ · tach ✅ (incl. the interface declaration) ·
roadmap-sync ✅.

## HITL gate decisions
- Plan Phase 4: Q1 = (a) sharpened to the post-TECH-006 orientation (user-directed: generic seam name,
  delivery-owned interactivity); Q2–Q4 = (a).
- Dev Phase 2: task list approved; R1 (module-global leakage → reset fixture) + R4 (registration proven
  end-to-end) honored.
- Pre-commit Phase 2/3: user approved G1 → it immediately exposed the inherited park-exit defect (fixed,
  per the fix-inherited-failures rule). No gate bypassed.

## Deferred by design
SF-03: FR-8 e2e proof (scripted provider co-author flow + headless park control) — closes the contract
and the US-2 epic.
