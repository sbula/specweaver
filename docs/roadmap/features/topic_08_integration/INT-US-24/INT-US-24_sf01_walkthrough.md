# Walkthrough — INT-US-24 SF-01: Make the Chain Executable

- **Commit boundary**: single **CB-1** (direct to `main`). Impl plan APPROVED 2026-07-23
  (Q1–Q5 as proposed; user edge-sweep refinements E1–E4 folded in).
- First bite of INT-US-24: the shipped B-FLOW-01 scenario chain becomes actually executable.

## What changed and why

`scenario_integration.yaml` was dead on arrival: its dual-pipeline step dispatched to the
decomposition orchestrator (which demands a `DecompositionPlan` nothing ever sets), the arbiter
read a feedback key nothing ever wrote, and a `kind: scenario` test run silently deselected every
generated test (`pytest -m scenario` with no such marker → "All 0 tests passed"). Three surgical
handler edits make the chain real:

1. **Dispatch (FR-1, `decompose.py` + `registry.py`)** — `OrchestrateComponentsHandler` delegates
   `params.mode == "dual_pipeline"` to `ArbitrateDualPipelineHandler` BEFORE the plan guard (lazy
   in-package import; INFO log). A set-but-unrecognized mode logs a WARNING and falls through
   byte-identically. The dual handler is now registered in `__all__` and guards
   `context.pipeline_runner is None` with a named failure instead of an `AttributeError` artifact.
2. **Evidence contract (FR-2, `validation.py` + `arbiter.py`)** — for scenario runs,
   `ValidateTestsHandler` ALWAYS publishes the raw QA export under the reserved key
   `context.feedback["scenario_test_failures"]` (pass, fail, zero-collected, and the timeout
   `{}`-exports shape alike). `ArbitrateVerdictHandler` consumes it **on verdict**: popped on
   `no_failures`/`code_bug`/`scenario_error`; retained on `spec_ambiguity` (park → `sw run
   --resume` re-arbitrates) and on ERROR (retry re-reads). Short-circuits:
   `total>0 ∧ failed==0 ∧ errors==0` → PASSED with **zero LLM calls**; `total==0`/empty evidence →
   FAILED "no scenario tests executed" (closes the continue-gate green-leak); absent key → loud
   wiring ERROR; malformed shapes (non-dict, non-int counts, non-list/non-dict failures) → ERROR.
   The evidence text now comes from the real `TestFailure` payloads (nodeid + message +
   stacktrace, stack-trace-filtered), with an aggregate fallback line for errors-only runs
   (collection/import crashes). The dead `if context.spec_path.exists(): pass` fell out with the
   rewrite.
3. **False-green fix (FR-3, `validation.py`)** — `kind: "scenario"` is a flow-level category, not
   a pytest marker: suppressed at the atom-call site only (`_resolve_targets` keeps the original
   kind), and a scenario run collecting 0 tests is FAILED, scenario-kind-scoped (the atom's
   pristine-targets SUCCESS for unit kinds is untouched). Verified: the four non-python runners
   ignore `kind` entirely, so `""` is safe across all five languages.

## Edge contracts pinned (from the user's gate challenge)

- **E1** collection errors (`failed==0, errors>0`) arbitrate — never short-circuit green.
- **E2** `total==0` (incl. timeout `{}` exports) fails loud at BOTH the step and the arbiter.
- **E3** consume-on-verdict — `spec_ambiguity` park→resume re-arbitrates instead of ERRORing.
- **E4** hostile evidence shapes → clean ERROR, no crash, no LLM spend.

## Tests

- Unit: 6 scenario-kind semantics + 5 evidence-publication (`test_validate_tests_handler.py`,
  15→24 tests) · 3 dispatch + existing byte-identical pins (`test_decompose.py`) · 2 wiring pins
  incl. the reserved-key collision guard (`test_dual_pipeline.py`) · arbiter migrated off the old
  fictional feedback shape + 11 evidence-contract tests (`test_arbiter.py`, 10→20 tests).
- Integration (NEW `test_scenario_integration_dispatch.py`): `scenario_integration.yaml` through
  the REAL registry — real dispatch → real evidence → real arbitration; green path completes with
  `llm.generate` never awaited; red path arbitrates real evidence, loops back
  (2 sub-runs x 2 rounds), and the routed coding feedback is scenario-vocabulary-free. The real
  `GenerateContractHandler` runs unmocked against the fixture spec.
- Migrated (fix-forward, old shape was fiction): `test_arbiter_integration.py`,
  `test_caller_migration*.py`, `test_build_base_prompt_profiles.py` fixtures now seed real QA
  evidence.

**Full suite (pre-commit Phase 4, re-run from scratch):** unit 4805 · integration 504 · e2e 157 —
**5466 passed, 0 failures.**
**Quality:** ruff ✅ · mypy ✅ (303 files) · C901 ✅ · file-size 0 errors · tach ✅ · roadmap-sync ✅.

## Red/Blue (Phase 7.5) — findings & dispositions

- Prompt-injection via failing-test output into the arbiter prompt: **pre-existing class**, in
  scope for `E-VAL-03` (queue Candidate 4), not widened by this change (the old code also fed raw
  messages). Accepted here.
- `bool` passes the `isinstance(x, int)` counts check; `passed` count is not type-validated in the
  green output. Both LOW/cosmetic — no behavioral hole (bool coerces arithmetically; `passed`
  is display-only in the no-failures output).
- Shared-context stamping race during the concurrent dual window and hung-sub-pipeline timeout
  ownership: documented accepted risks in the impl plan (pre-existing patterns).

## Not in SF-01 (by design)

Scenario-regeneration feedback awareness + opacity e2e pins → **SF-02**; the `sw run
scenario_integration` CLI journey + 6-scenario verifiable proof + dev-guide currency update →
**SF-03**; `max_retries_hitl` revival + arbiter JSON hardening → `B-INTL-07`/TECH intake.
