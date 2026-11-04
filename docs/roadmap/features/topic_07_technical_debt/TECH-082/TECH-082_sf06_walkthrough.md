# Walkthrough: TECH-082 SF-06 — Feedback keys and names

## CB-1: declared feedback keys; one pop function; the arbiter uses the side table (FR-12, NFR-1, NFR-2, NFR-4)

**What changed**
- New `core/flow/run_state/feedback.py`: `SCENARIO_EVIDENCE`, `RESOLVED_MENTIONS` (each with its
  value type), `StepFindings`, `send_findings(context, to_step, from_step, findings)` and
  `pop_findings(context, step_name)`. A malformed entry is taken out, logged once, and treated as
  absent. `run_state/context.yaml` exposes the five names.
- `GateEvaluator.inject_feedback` writes through `send_findings`.
- Three pop functions are gone: `draft._pop_step_feedback`, `DraftSpecHandler._pop_feedback` (a
  third one, found in dev) and `generation._pop_findings`. Their callers use `pop_findings`.
- `dual_pipeline.side_step(side)` reads `_SIDES`. The arbiter sends its verdict to
  `side_step("coder")` / `side_step("scenario")`, with `from_step` set to its own step name (was the
  literal `"arbitrate_verdict"`).
- `arbiter.py`, `validation.py` use `SCENARIO_EVIDENCE`; `review.py` uses `RESOLVED_MENTIONS`.
- `scenario.py`: the unread `scenario_test_path` write is removed.
- Docs: `domain_flow_engine.md` (gate model), `pipeline_engine_guide.md` (reading findings),
  `scenario_pipelines.md` (evidence key), `developer_guide.html` (loop-back diagram).

**Tests**
- `run_state/test_feedback.py` (14), red first (no module): send then pop once; a later send
  replaces; empty, other step, no `feedback` attribute; entries with no or non-dict findings and
  non-dict entries are popped and give None; a dropped entry logs one warning; no entry logs nothing.
- `test_feedback_keys_declared_once.py` (5), red first on `arbiter.py`, `validation.py`,
  `review.py`, `scenario.py`: no literal key in `core/flow` outside `feedback.py` (subscript,
  `.get/.pop/.setdefault`, `in`); the arbiter names no side step; a name key passes; an unparsable
  file is named; every literal form is found.
- `test_dual_pipeline.py::TestSideStep` (3), red first (no `side_step`): each side step is that
  side's `generate` step in its YAML; an unknown side raises.
- `test_arbiter.py::TestTheVerdictNamesItsStep` (2, gap analysis): the verdict's `from_step` is the
  arbiter step's own name, for both sides.
- Test edits (F-1, NFR-1 exception): `test_draft_feature_handler.py` 5 calls and
  `test_draft_handler.py` 4 calls use `pop_findings`; the delegate test of `_pop_feedback` is
  removed with the delegate; `test_scenario_handlers.py:351` asserts no `scenario_test_path`.

**Mutants**
- 10 stale (B-FLOW-01 6, C-FLOW-06 1, D-VAL-05 1, TECH-082 2) re-run before the refresh: all
  OBJECTED. B-FLOW-01 FR-10 `park-forgotten` re-anchored on `SCENARIO_EVIDENCE`. 0 stale.
- TECH-082 FR-12 campaign, 7 mutants, all OBJECTED: `findings-not-taken-out`,
  `dropped-entry-unlogged`, `code-bug-to-the-scenario-side`, `side-step-is-the-pipeline-file`,
  `evidence-key-by-hand`, `unread-path-written`, `verdict-from-a-fixed-name`.

**Coverage matrix**

| Function | Unit | Integration | E2E |
|---|---|---|---|
| `send_findings` / `inject_feedback` | ✅ | ✅ `test_draft_chain_integration.py`, `test_feedback_replay_across_resume.py` | ✅ |
| `pop_findings` | ✅ | ✅ `test_scenario_integration_dispatch.py` (arbiter sends, generator pops) | ✅ `test_scenario_verification_e2e.py` |
| `side_step` and the arbiter's routing | ✅ | ✅ `test_scenario_integration_dispatch.py`, `test_dual_run_feedback.py` | ✅ |
| declared keys (guard) | ✅ | — | — |

Composition: `send_findings` → `pop_findings` runs as a pair in the dispatch integration test. Agreement:
one pop function is left, so there is nothing to agree with.

**Architecture**: `feedback.py` imports only `typing`, `logging` and `run_context` (TYPE_CHECKING);
the engine and the handlers already depend on `run_state`; `arbiter` → `dual_pipeline` adds no cycle.
`tach check` passes. The duplication baseline is re-frozen for a 9-line import block that
`draft.py` and `scenario.py` share (imports cannot be extracted).

**Red/blue (7.5)**, 2 cycles
- R1 (MEDIUM, fixed) A third pop function, `DraftSpecHandler._pop_feedback`, which the plan missed.
  Removed under F-1; the design's NFR-1 exception names its tests.
- R2 (MEDIUM, fixed) The stricter pop rule hid a malformed entry from the scenario step's warning
  (`test_malformed_findings_treated_as_no_feedback` failed). `pop_findings` now logs the drop, so
  every reader warns, not only the scenario step.
- R3 (LOW) `generation._pop_findings` passed non-dict findings on, and the coder step then failed.
  Now they degrade to no findings with a warning. Every writer puts a dict there
  (`StepResult.output: dict[str, Any]`), so only a malformed entry is affected.
- R4 (LOW) Tests still spell the keys as strings (`test_arbiter.py`). That pins the wire value on
  purpose: a renamed key fails them.
- R5 (LOW) A `MagicMock` context gives a `MagicMock` entry, which logs the warning. Test noise only.
- Cycle 2: challenged R3 (does any code outside `core/flow` read `context.feedback`?): none in
  `src/`. Challenged the guard's reach (only `core/flow`): it is the only package that touches
  `feedback`. No new finding above LOW.
