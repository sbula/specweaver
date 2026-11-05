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

## CB-2: dead setting, distinct names, public `roles_of` (FR-12, NFR-1, NFR-2, NFR-4)

**What changed**
- `generation.py`: `FILENAME_PREFIX` is gone from `_GenerationHandler` and `GenerateTestsHandler`
  (nothing read it).
- `handlers/context_assembler.py` → `handlers/skeleton_assembler.py`, titled "Skeleton assembler";
  its log lines say `SkeletonAssembler:`. `mcp_assembler.py` is titled "MCP resource assembler".
  No shim at the old path (AD-6). Imports moved in `generation.py`, `review.py` and 7 test files
  (imports and `mock.patch` targets only); `test_context_assembler.py` → `test_skeleton_assembler.py`.
- `roles_of` moves from the private `handlers/_llm.py` to the new public `handlers/roles.py`.
  `interfaces/run_setup/builder.py` (2 sites) and 3 test files import it from there.
- Docs: `pipeline_engine_guide.md` (`roles.py` is the public home), `code_structure_and_ast_editing.md`
  and `mcp_architecture_design.md` (assembler names), `topic_02_sensors.md`. Plans, walkthroughs and
  analyses that name the old module are history and stay as written.

**Tests**
- `test_flow_names.py` (8), red first: no `FILENAME_PREFIX` on either handler (their `OUTPUT_SUBDIR`
  stays); the old assembler path raises `ModuleNotFoundError`; the two titles differ; `roles_of`
  imports from `handlers.roles`; nothing in `src/` outside the handlers imports `_llm` (red on
  `builder.py:79,156`); both import forms are found; an unparsable file is named.

**Mutants**
- 14 stale (B-FLOW-01 1, B-FLOW-07 1, C-FLOW-13 4, D-INTL-03 1, TECH-077 6, TECH-081 1) re-run before
  the refresh: all OBJECTED. B-FLOW-01 FR-17 `side-roles-unchecked` re-pointed to `roles.py`; TECH-077
  FR-6 to `skeleton_assembler.py`. 0 stale.
- TECH-082 FR-12 gains `private-llm-imported-again`, `filename-prefix-back`,
  `assemblers-share-a-title`. All OBJECTED.

**Coverage matrix**

| Function | Unit | Integration | E2E |
|---|---|---|---|
| `roles_of` (new home) | ✅ `test_llm_for.py`, `test_dual_pipeline_step.py` | ✅ `test_two_models.py`, `test_build_run.py` | ✅ |
| `evaluate_and_fetch_skeleton_context` | ✅ `test_skeleton_assembler.py`, `test_skeleton_wiring.py` | ✅ `test_one_archetype.py` | — |
| names (guard) | ✅ | — | — |

Composition: the builder calls `roles_of` before the run; `test_build_run.py` drives that pair.
Agreement: one `roles_of` is left.

**Architecture**: `roles.py` imports `engine.models` and `handlers.dual_pipeline`, both already used
by the handlers; `dual_pipeline` imports neither `roles` nor `_llm`, so no cycle. `interfaces/run_setup`
already depends on `core.flow.handlers`. `tach check` passes.

**Red/blue (7.5)**, 2 cycles
- R1 (LOW) The skeleton assembler's log prefix changed to `SkeletonAssembler:`. No test, doc or
  script reads it (grep).
- R2 (LOW) `roles.py` imports `dual_pipeline` at load; `_llm.py` imported it inside the function.
  The builder imports `roles` inside its functions, so a CLI start pays nothing new; no cycle.
- R3 (LOW) NFR-3's list names no assembler path. `test_flow_names.py` checks the old path fails to
  import, so a shim cannot come back unseen.
- Cycle 2: challenged R2 (does any code still reach `roles_of` through `_llm`?): none in `src/` or
  `tests/` (grep). No new finding above LOW.
