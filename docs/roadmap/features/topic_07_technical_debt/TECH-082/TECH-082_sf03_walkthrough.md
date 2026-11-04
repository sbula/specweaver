# Walkthrough: TECH-082 SF-03 — Arbitration home and thin handlers

## CB-1: the arbiter's model work moves; no handler calls a model (FR-5, FR-6, NFR-1, NFR-2, NFR-4)

**What changed**
- New module `workflows/arbitration` (AD-2), one file `verdict.py`: `ArbitrateVerdict`,
  `ArbitrateResult`, `ARBITRATE_INSTRUCTIONS`, `evidence_text`, `arbitrate(adapter, config, prompt)`
  and `UnreadableVerdictError` (a reply with no JSON). The text guards moved too (D-6, the user):
  `SCENARIO_VOCABULARY`, `guard_coding_feedback`, `scenario_safe`, `code_trace`, `with_trace`. Two
  names lost their `_` because they now cross a module.
- `ArbitrateVerdictHandler` keeps the evidence checks, the trace filter (it needs `sandbox`), the
  prompt build and the routing. `execute` was split (`_nothing_ran`, `_no_failures`, `_judge`,
  `_route`, `_scenario_error`) and lost its `# noqa: C901` (it was 14).
- tach: new module (`infrastructure.llm`, `workspace.ast.parsers` for the filter type), its
  `[[interfaces]]` block equal to the manifest's `exposes`; `core.flow.handlers` gains the edge.
  `core/flow/context.yaml` consumes `workflows/arbitration`, so the handlers' edge is not a widening
  (FR-15).
- Tests: the verdict and guard tests moved to `tests/unit/workflows/arbitration/test_verdict.py`;
  4 other test files changed only an import.
- Mutants: B-FLOW-01 `no-trace`, `check-frames-kept`, `banned-words-pass` moved file;
  `scenario-report-unfiltered` and `set-not-kept` re-anchored in `_scenario_error` and
  `_no_failures`. All 5 still caught. 0 stale.
- Docs: `module_dependency_graph.md` (arbitration paragraph), `layer_isolation_and_di.md` ("A handler
  is a shell"), the design's guides rows.

**Tests**
- `test_no_handler_calls_a_model.py` (8), red first on `arbiter.py:300` (the `noqa`).
- `test_verdict.py` (9 new), red first (no module).
- `test_arbitration_has_its_own_home.py` (6), red first. It scans `arbiter.py` for definitions,
  because the handler imports the names.
- Phase 2 gaps, now in `test_arbiter.py` (3): a model that names an unknown verdict, one that answers
  `"error"`, and one that fails all give ERROR and keep the evidence.
- `test_arbiter_integration.py` (1): the real handler reads a verdict wrapped in a sentence. Added
  because the extract mutant was silent at the integration tier.

**Mutants** (TECH-082 corpus):
- FR-5 `verdict-in-prose-unread` → unit and integration object.
- FR-5 `scenario-error-not-routed` → `test_scenario_integration_dispatch.py` objects.
- FR-6 `handler-calls-the-model` → the guard objects.

**Coverage matrix**

| Function | Unit | Integration | E2E |
|---|---|---|---|
| `arbitrate` | ✅ | ✅ `test_arbiter_integration.py` | ✅ `test_scenario_verification_e2e.py` |
| `evidence_text` | ✅ | ✅ through the handler (errors-only) | — |
| guards (`guard_coding_feedback`, `scenario_safe`, `code_trace`, `with_trace`) | ✅ | ✅ `test_scenario_report_filtered.py`, `test_scenario_integration_dispatch.py` | ✅ same e2e |
| `ArbitrateVerdictHandler` branches | ✅ | ✅ | ✅ |
| the FR-6 guard | ✅ | — | — |

Composition: the order evidence → filter → prompt → `arbitrate` → guard → route is driven by the
integration and e2e tests. Agreement: nothing else in the repo arbitrates.

**Red/blue (7.5)**, 2 cycles
- R1 (LOW, accepted) The moved guard still logs "ArbitrateVerdictHandler: Vocabulary leak caught"
  under the new module's logger. No test reads it; the text stays (NFR-1).
- R2 (LOW, accepted) `arbitrate` keeps the greedy `\{.*\}` extract: a reply with a second `{...}`
  after the JSON fails to parse, as before (NFR-1).
- R3 (LOW) `code_trace` and `SCENARIO_VOCABULARY` are exposed though only tests import them; they are
  the guard's public rules. No change.
- Cycle 2: challenged the split (does `_judge` change any order?) — filter, profile, prompt, model,
  route run in the old order; challenged the new tach edge — `StackTraceFilterInterface` is already
  public in the parsers. No new finding above LOW.
