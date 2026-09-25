# C-SENS-02 SF-05 — Dependency Injection Remediation

**Feature ID**: 3.32b · **Depends on**: SF-04 · Design: [C-SENS-02_design.md](C-SENS-02_design.md)
§Sub-features → SF-05

## Goal

Remove the `AnalyzerFactory` globals that still bypassed SF-04's DI at the orchestrator boundaries.

## Changes

1. **`RunContext`** · `core/flow/handlers/base.py` — add `analyzer_factory: Any = None` to the
   Pydantic model, so `PipelineRunner` can pass the polyglot DI objects to every node.
2. **`PipelineRunner`** · `core/flow/engine/runner.py` — inject `self._analyzer_factory` into each
   `RunContext` it builds (in `execute` / the loop).
3. **`ToolDispatcher`** · `core/loom/dispatcher.py` — the LLM dispatcher imported `AnalyzerFactory`
   globally, a boundary violation:
   - add `analyzer_factory: Any = None` to `ToolDispatcher.factory()`;
   - remove the static import; add `exclude_dirs` / `exclude_patterns` only when `analyzer_factory`
     is passed.
4. **Validation executor** · `assurance/validation/executor.py` — `execute_validation_pipeline`
   accepts `context: dict[str, Any] | None = None` and sets `rule.context = context` before each
   `rule.check()`, so the factory reaches `rule.context`.
5. **Validation handlers** · `core/flow/handlers/validation.py` — `ValidateSpecHandler.execute` and
   `ValidateCodeHandler.execute` read `analyzer_factory = context.analyzer_factory` and pass it into
   `_run_validation`, down to the rules.
6. **`C09TraceabilityRule`** · `assurance/validation/rules/code/c09_traceability.py`:
   - drop `from specweaver.workspace.analyzers.factory import AnalyzerFactory`;
   - `_find_and_parse_tests()` takes the factory from `self.context.get("analyzer_factory")`. Without
     an orchestrator (unit tests), fall back to a mock or a local import — no global binding.

Order: 1–2 (`RunContext`), 3 (`dispatcher.py`), 4–6 (`executor.py` → `c09_traceability.py`), then
confirm existing integration tests still pass.

**Since moved** (noted 2026-09-25): `analyzer_factory` now sits on `AnalysisContext` in
`core/flow/handlers/run_context.py`; `core/loom/dispatcher.py` → `sandbox/dispatcher.py`.

## Decisions (audit)

- **Missing `analyzer_factory` in `ToolDispatcher`**: fail, or degrade and skip the file-exclusion
  optimization? Suggested: degrade (fallback), so unit tests without an orchestrator still run.
