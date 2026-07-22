# Implementation Plan: Interactive Drafter Integration — SF-02: Composition-Root Provider Wiring (TTY-Gated)

- **Feature ID**: INT-US-02
- **Sub-Feature**: SF-02 — Composition-Root Provider Wiring
- **Design Document**: docs/roadmap/features/topic_08_integration/INT-US-02/INT-US-02_design.md
- **Design Section**: §Sub-Feature Breakdown → SF-02
- **Implementation Plan**: docs/roadmap/features/topic_08_integration/INT-US-02/INT-US-02_sf02_implementation_plan.md
- **Status**: APPROVED — approved by Steve Bula on 2026-07-22. Q1 = (a) **sharpened to the post-TECH-006 orientation** (generic seam, delivery owns interactivity); Q2–Q4 = (a). Single CB-1.

## Scope (from the Design Document)
Wire the interactive `HITLProvider` into the `sw run` / `sw resume` composition roots **when attached to an
interactive terminal (TTY)** so `sw run new_feature <name>` co-authors instead of parking (FR-4), while
headless behavior stays byte-identical — parking remains the headless contract (FR-5). Mechanism per AD-2
(engine-neutral, per the execution-discipline note). **FRs owned: FR-4, FR-5.**

## Research Notes (Phase 0)

1. **The two composition sites** — `core/flow/interfaces/cli.py` `_execute_run` (`RunContext` build
   `:251-259`-era; now with `apply_session_policy` beneath) and `resume` (`:452-460`-era). Neither sets
   `context_provider`; `DraftSpecHandler` therefore always parks there (SF-01 left this untouched).
2. **NEW FACT vs. the design's premise:** `core/flow/interfaces/cli.py` **already imports
   `specweaver.interfaces.cli._core`** (`:19`) — the "no core→delivery import" constraint in AD-2 was
   written believing that edge didn't exist; it does (it's exactly `TECH-006` Finding 2's cross-interface
   spider-web, documented debt). Decision consequence: a direct `HITLProvider` import would ADD to that
   documented debt; the factory-setter keeps new code out of it (Q1).
3. **`RunContext.context_provider: Any = None`** (`base.py:50`) — no typing import needed; the
   `ContextProvider` ABC lives in `workspace/context/provider.py` and is only needed by the delivery side.
4. **Wiring point for the setter:** `interfaces/cli/main.py:121-123` imports `flow_cli` and `add_typer`s
   it — the natural place for the delivery layer to hand the factory over, one line after the import.
5. **TTY detection:** `sys.stdin.isatty()` — questions need *input*; CliRunner/CI/piped runs report False,
   so **the entire existing test suite doubles as the headless-regression control** (no test churn).
6. **Inertness:** `context_provider` is read only by drafting/decompose handlers — injecting it on every
   TTY run is harmless for non-draft pipelines (stays unused).

### External deps: none. No new module.

## Implementation Approach
> Pseudocode / ordered steps only.

### Change 1 — context-provider-factory seam in the flow CLI (FR-4) · `core/flow/interfaces/cli.py`
**Post-TECH-006 orientation (Q1, HITL-resolved):** the seam is the durable, GENERIC interaction-channel
registration — named after the `RunContext` field, with core fully terminal-agnostic:
1. `_context_provider_factory: Callable[[], Any] | None = None` +
   `set_context_provider_factory(factory)` (public; docstring declares it THE channel seam — future
   channels (`D-INTL-07` interview engine, `C-FLOW-11` work-unit channels) register here too).
2. `_maybe_attach_provider(context)`: if a factory is registered AND `context.context_provider is None`
   → `provider = factory()`; attach only if non-None. **The factory decides interactivity** (may return
   None) — core holds zero TTY/terminal knowledge. Best-effort (`try/except` → leave None; a channel
   failure must never break a run).
3. Call it at BOTH sites, right after the `RunContext(...)` construction.
No new `_core`/HITL/Rich imports in core — the seam survives the TECH-006 spider-web dissolution.

### Change 2 — delivery-layer registration (FR-4, FR-5) · `interfaces/cli/main.py`
After `from ...flow.interfaces.cli import flow_cli`: register a factory that returns
`HITLProvider(console=_core.console)` **when `sys.stdin.isatty()` else None** — the TTY gate lives in the
delivery layer, next to the terminal knowledge (lazy `HITLProvider` import inside the factory).

### Change 3 — nothing else
No handler, pipeline, or yaml changes. FR-5 is satisfied by the gate itself (no TTY → no factory call →
`None` → the existing park path, byte-identical — proven by the untouched existing suite plus explicit tests).

### Files to modify
| File | Change | FR |
|------|--------|----|
| `src/specweaver/core/flow/interfaces/cli.py` | factory seam + `_maybe_attach_provider` at both sites | FR-4, FR-5 |
| `src/specweaver/interfaces/cli/main.py` | one-line factory registration | FR-4 |
| `tests/...` | see Test Plan | all |

## Test Plan (4 Adversarial Buckets)

**Unit — the seam (direct):** [Happy] factory set + returns provider → attached (factory called once);
[Boundary] factory returns None (delivery says non-interactive) → context stays None; [Boundary] no factory
registered → None; [Boundary] `context_provider` already set → NOT overwritten (factory not called);
[Degradation] factory raises → provider stays None, no crash. **Unit — the delivery factory (direct):**
isatty True → HITLProvider instance; isatty False → None (Q4: stdin).

**Integration — composition (real `sw run` invocation, `PipelineRunner` mocked, capture context):**
[Happy] isatty patched True + registered factory → captured context has the provider; [Boundary/FR-5]
isatty False (CliRunner default) → `context_provider is None` (headless park contract intact) — for BOTH
`sw run` and `sw resume`; [Happy] real `main.py` registration actually ran (the factory produces an
`HITLProvider` instance when invoked).

**Regression:** entire existing suite (CliRunner = non-TTY everywhere) doubles as the byte-identical
headless control.

(The end-to-end "new_feature co-authors instead of parking" proof with a scripted provider = SF-03/FR-8.)

## Audit (Phase 2) — resolved at Phase 4 HITL (2026-07-22): Q1 = (a) post-TECH-006-oriented (generic `set_context_provider_factory`, delivery-owned interactivity); Q2–Q4 = (a)
| # | Question | Options | Proposal | Severity |
|---|----------|---------|----------|----------|
| Q1 | AD-2 mechanism, given the NEW fact that `core.flow.interfaces → interfaces.cli._core` already exists (documented TECH-006 debt). | (a) **factory-setter seam** [rec] — honors AD-2's approved wording, engine-neutral (any future channel registers the same way), trivially testable, adds nothing to the debt TECH-006 must undo; (b) direct lazy `HITLProvider` import in the flow CLI — 3 lines, mirrors the existing debt edge. | **(a)** — (b) deepens a documented anti-pattern to save ~10 lines. | MEDIUM |
| Q2 | Inject on every TTY run, or only for pipelines containing a DRAFT step? | (a) every TTY run [rec] — provider is inert elsewhere; step-sniffing adds coupling; (b) draft-pipelines only. | **(a)**. | LOW |
| Q3 | Wire additional flow entry points (e.g. gate-decision paths)? | (a) `run` + `resume` only, per FR-4 [rec]; (b) more. | **(a)** — API roots remain `TECH-013`. | LOW |
| Q4 | TTY source: `sys.stdin.isatty()` vs stdout. | (a) stdin [rec] — the provider READS answers. | **(a)**. | LOW |

## Architecture Verification (Phase 3)
- The seam lives in `core.flow.interfaces` (a composition root); the delivery layer calls INTO it
  (`interfaces.cli → core.flow.interfaces` — correct direction, existing edge class). No new core→delivery
  import; `HITLProvider`/Rich stay in the delivery layer (NFR-6). `tach`/`ruff`/`mypy --strict` stay green.
- Engine-neutral per the execution-discipline note: `D-INTL-07`'s future channel registers via the same setter.
- **Verdict:** no CRITICAL violation.

## Session Handoff
**Current status**: APPROVED (2026-07-22) — ready for `/specweaver-dev`, single CB-1.
**Next step**: on approval → `/specweaver-dev` SF-02, then SF-03 (proof) closes the contract.
