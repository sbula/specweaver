# INT-US-02 SF-02 — Composition-Root Provider Wiring (TTY-Gated)

**Status**: APPROVED — approved by Steve Bula on 2026-07-22. Q1 = (a) **sharpened to the post-TECH-006
orientation** (generic seam, delivery owns interactivity); Q2–Q4 = (a). Single CB-1. Implemented
2026-07-23. · **FRs owned**: FR-4, FR-5 · **Depends on**: none · Design:
[INT-US-02_design.md](INT-US-02_design.md) §Sub-features → SF-02

## Goal

Wire the interactive `HITLProvider` into the `sw run` / `sw resume` composition roots **when attached
to an interactive terminal (TTY)**, so `sw run new_feature <name>` co-authors instead of parking (FR-4).
Headless stays byte-identical — parking remains the headless contract (FR-5). Mechanism per AD-2,
engine-neutral per the execution discipline.

## Where it plugs in

| Fact | Where |
|---|---|
| The two composition sites: `_execute_run` (`RunContext` build, `:251-259`-era, now with `apply_session_policy` beneath) and `resume` (`:452-460`-era). Neither sets `context_provider`, so `DraftSpecHandler` always parks there. | `core/flow/interfaces/cli.py` |
| The flow CLI **already imports `specweaver.interfaces.cli._core`** (`:19`). AD-2's "no core→delivery import" assumed that edge did not exist; it does — `TECH-006` Finding 2's cross-interface spider-web, documented debt. A direct `HITLProvider` import would ADD to it (→ Q1). | `core/flow/interfaces/cli.py:19` |
| `RunContext.context_provider: Any = None` — no typing import needed. The `ContextProvider` ABC lives in `workspace/context/provider.py`, needed only on the delivery side. | `base.py:50` |
| Setter wiring point: `interfaces/cli/main.py:121-123` imports `flow_cli` and `add_typer`s it — the delivery layer hands over the factory one line after the import. | `interfaces/cli/main.py:121-123` |
| TTY detection: `sys.stdin.isatty()` — questions need *input*. CliRunner/CI/piped runs report False, so **the whole existing suite doubles as the headless-regression control**. | — |
| `context_provider` is read only by drafting/decompose handlers — injecting it on every TTY run is inert for other pipelines. | — |

**Since moved:** both sites now build their context through one `_build_run_context`, which calls
`_maybe_attach_provider` once (`core/flow/interfaces/cli.py:277`). Line refs above are as of the plan.

External deps: none. No new module.

## Changes

1. **Context-provider-factory seam** (FR-4) · `core/flow/interfaces/cli.py` — the generic
   interaction-channel registration (Q1), named after the `RunContext` field; core stays terminal-agnostic:
   1. `_context_provider_factory: Callable[[], Any] | None = None` + public
      `set_context_provider_factory(factory)`. Its docstring declares it THE channel seam; future
      channels (`D-INTL-07` interview engine, `C-FLOW-11` work-unit channels) register here too.
   2. `_maybe_attach_provider(context)`: factory registered AND `context.context_provider is None` →
      `provider = factory()`; attach only if non-None. **The factory decides interactivity** (may
      return None). Best-effort: `try/except` → leave None; a channel failure never breaks a run.
   3. Called at BOTH sites right after `RunContext(...)` is built. No new `_core`/HITL/Rich imports in
      core, so the seam survives the TECH-006 spider-web dissolution.
2. **Delivery-layer registration** (FR-4, FR-5) · `interfaces/cli/main.py` — after
   `from ...flow.interfaces.cli import flow_cli`, register a factory returning
   `HITLProvider(console=_core.console)` **when `sys.stdin.isatty()` else None** (lazy `HITLProvider`
   import inside the factory). The TTY gate lives next to the terminal knowledge.
3. Nothing else — no handler, pipeline or yaml change. No TTY → factory returns `None` → the existing
   park path, byte-identical (FR-5).

| File | Change | FR |
|------|--------|----|
| `src/specweaver/core/flow/interfaces/cli.py` | factory seam + `_maybe_attach_provider` at both sites | FR-4, FR-5 |
| `src/specweaver/interfaces/cli/main.py` | one-line factory registration | FR-4 |

## Tests

| Tier | Bucket | Case |
|---|---|---|
| Unit — the seam | Happy | factory set + returns provider → attached (factory called once) |
| | Boundary | factory returns None → context stays None; no factory registered → None; `context_provider` already set → NOT overwritten (factory not called) |
| | Degradation | factory raises → provider stays None, no crash |
| Unit — delivery factory | — | isatty True → HITLProvider instance; isatty False → None (Q4: stdin) |
| Integration — real `sw run`, `PipelineRunner` mocked, context captured | Happy | isatty patched True + registered factory → captured context has the provider |
| | Boundary/FR-5 | isatty False (CliRunner default) → `context_provider is None` — for BOTH `sw run` and `sw resume` |
| | Happy | the real `main.py` registration ran (the factory yields an `HITLProvider` when invoked) |
| Regression | — | entire existing suite (CliRunner = non-TTY) is the byte-identical headless control |

The end-to-end "new_feature co-authors instead of parking" proof = SF-03/FR-8.

## Decisions (audit)

| # | Question | Options | Chosen | Severity |
|---|----------|---------|--------|----------|
| Q1 | AD-2 mechanism, given `core.flow.interfaces → interfaces.cli._core` already exists (documented TECH-006 debt). | (a) **factory-setter seam** — honors AD-2's wording, engine-neutral (any future channel registers the same way), testable, adds nothing to the debt; (b) direct lazy `HITLProvider` import in the flow CLI — 3 lines, mirrors the debt edge. | **(a)**, as generic `set_context_provider_factory` with delivery-owned interactivity — (b) deepens a documented anti-pattern to save ~10 lines. | MEDIUM |
| Q2 | Inject on every TTY run, or only for pipelines with a DRAFT step? | (a) every TTY run — provider is inert elsewhere; step-sniffing adds coupling; (b) draft-pipelines only. | **(a)**. | LOW |
| Q3 | Wire other flow entry points (e.g. gate-decision paths)? | (a) `run` + `resume` only, per FR-4; (b) more. | **(a)** — API roots remain `TECH-013`. | LOW |
| Q4 | TTY source: `sys.stdin.isatty()` vs stdout. | (a) stdin — the provider READS answers. | **(a)**. | LOW |

Architecture check: the seam lives in `core.flow.interfaces` (a composition root); the delivery layer
calls INTO it (`interfaces.cli → core.flow.interfaces` — correct direction, existing edge class). No new
core→delivery import; `HITLProvider`/Rich stay in the delivery layer (NFR-6). `tach`/`ruff`/
`mypy --strict` green. `D-INTL-07`'s future channel registers via the same setter. No CRITICAL
violation.

## As built (2026-07-23)

| Where | What |
|---|---|
| `core/flow/interfaces/cli.py` | `set_context_provider_factory` (declared in tach.toml's `[[interfaces]]` expose list — tach's interface enforcement flagged the undeclared symbol) + `_maybe_attach_provider` at both composition sites. Zero new delivery imports |
| `interfaces/cli/main.py` | `_stdin_isatty()` (patchable indirection) + `_interactive_context_provider()` (TTY → `HITLProvider`, else None), registered next to the `flow_cli` add_typer |
| `sw run` command | `except typer.Exit: raise` passthrough ahead of the broad `except Exception`, so a PARKED run exits 0 as its `Exit(code=0)  # not an error, just parked` intends (the broad handler turned it into exit 1 "Error: Exit:") |

Proof and results: [SF-02 walkthrough](INT-US-02_sf02_walkthrough.md).
