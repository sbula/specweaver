# INT-US-24 SF-01 — Walkthrough

**Commit boundary:** single **CB-1** (direct to `main`) · **Plan:**
[sf01](INT-US-24_sf01_implementation_plan.md), APPROVED 2026-07-23 (Q1–Q5 as proposed; user
edge-sweep refinements E1–E4 folded in)

## Delivered

The shipped B-FLOW-01 scenario chain now executes. Three handler edits:

| Change | Where | What |
|---|---|---|
| Dispatch (FR-1) | `decompose.py` + `registry.py` | `OrchestrateComponentsHandler` delegates `params.mode == "dual_pipeline"` to `ArbitrateDualPipelineHandler` BEFORE the plan guard (lazy in-package import; INFO log). Set-but-unrecognized mode → WARNING, falls through byte-identically. Dual handler exported in `__all__`; guards `context.pipeline_runner is None` with a named failure instead of an `AttributeError`. Replaces routing to the decomposition orchestrator, which demanded a `DecompositionPlan` nothing sets. |
| Evidence contract (FR-2) | `validation.py` + `arbiter.py` | Scenario runs ALWAYS publish the raw QA export under `context.feedback["scenario_test_failures"]` (pass, fail, zero-collected, timeout `{}`-exports alike). The arbiter consumes it **on verdict**: popped on `no_failures`/`code_bug`/`scenario_error`; retained on `spec_ambiguity` (park → `sw run --resume` re-arbitrates) and ERROR (retry re-reads). Short-circuits: `total>0 ∧ failed==0 ∧ errors==0` → PASSED with **zero LLM calls**; `total==0`/empty → FAILED "no scenario tests executed" (closes the continue-gate green-leak); absent key → wiring ERROR; malformed shapes (non-dict, non-int counts, non-list/non-dict failures) → ERROR. Evidence text is built from `TestFailure` payloads (nodeid + message + stacktrace, stack-trace-filtered), with an aggregate fallback line for errors-only runs (collection/import crashes). The dead `if context.spec_path.exists(): pass` is gone. |
| False-green fix (FR-3) | `validation.py` | `kind: "scenario"` is a flow-level category, not a pytest marker: suppressed at the atom-call site only (`_resolve_targets` keeps the original kind); a scenario run collecting 0 tests is FAILED, scenario-kind-scoped (unit-kind pristine-targets SUCCESS untouched). The four non-python runners ignore `kind`, so `""` is safe across all five languages. Replaces `pytest -m scenario` deselecting every test → "All 0 tests passed". |

Edge contracts pinned: **E1** collection errors (`failed==0, errors>0`) arbitrate, never
short-circuit green · **E2** `total==0` (incl. timeout `{}` exports) fails loud at BOTH the step
and the arbiter · **E3** consume-on-verdict — `spec_ambiguity` park→resume re-arbitrates ·
**E4** hostile evidence shapes → clean ERROR, no crash, no LLM spend.

Not in SF-01: scenario-regeneration feedback + opacity pins (SF-02); CLI journey, proof, dev-guide
update (SF-03); `max_retries_hitl` revival + arbiter JSON hardening (`B-INTL-07`/TECH intake).

## Proof

| Test | Cases |
|---|---|
| `test_validate_tests_handler.py` | 6 scenario-kind semantics + 5 evidence-publication (15→24 tests) |
| `test_decompose.py` | 3 dispatch + existing byte-identical pins |
| `test_dual_pipeline.py` | 2 wiring pins incl. the reserved-key collision guard |
| `test_arbiter.py` | migrated off the old feedback shape + 11 evidence-contract tests (10→20 tests) |
| `test_scenario_integration_dispatch.py` (NEW, integration) | `scenario_integration.yaml` through the REAL registry — real dispatch → evidence → arbitration; real `GenerateContractHandler` on the fixture spec; green path: `llm.generate` never awaited; red path: arbitrates real evidence, loops back (2 sub-runs x 2 rounds), routed coding feedback scenario-vocabulary-free |
| Migrated fixtures | `test_arbiter_integration.py`, `test_caller_migration*.py`, `test_build_base_prompt_profiles.py` now seed real QA evidence |

| Check | Result |
|---|---|
| Unit / integration / e2e | 4805 · 504 · 157 — **5466 passed, 0 failures** |
| ruff · mypy (303 files) · C901 · file-size · tach · roadmap-sync | ✅ · 0 errors |

## Findings still open

- Prompt injection via failing-test output into the arbiter prompt: pre-existing class, not
  widened; `E-VAL-03` scope (queue Candidate 4). Accepted.
- `bool` passes the `isinstance(x, int)` counts check; `passed` is not type-validated in the green
  output. LOW/cosmetic — bool coerces arithmetically; `passed` is display-only.
- Shared-context stamping race in the dual window and hung-sub-pipeline timeout ownership:
  accepted risks, see the plan.
