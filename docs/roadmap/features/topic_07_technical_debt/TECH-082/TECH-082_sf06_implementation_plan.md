# Implementation Plan: Domain Logic Lives in the Flow Engine [SF-06: Feedback keys and names]
- **Feature ID**: TECH-082
- **Sub-Feature**: SF-06 — Feedback keys and names
- **Design Document**: docs/roadmap/features/topic_07_technical_debt/TECH-082/TECH-082_design.md
- **Design Section**: §Sub-Feature Breakdown → SF-06
- **Implementation Plan**: docs/roadmap/features/topic_07_technical_debt/TECH-082/TECH-082_sf06_implementation_plan.md
- **Status**: APPROVED

## Scope

`context.feedback` gets declared keys and one pop function; the arbiter takes the side step names
from the dual pipeline's side table; dead code and a duplicate name go; `roles_of` gets a public
home. FR: **FR-12**. NFRs carried: NFR-1, NFR-2, NFR-4. Kind: `refactor`.

Today (re-measured 2026-11-04):

| Key kind | Value | Written | Read |
|---|---|---|---|
| a step's name (loop-back findings) | `{"from_step", "findings"}` | `gates.py:155` `inject_feedback` (also by the resume replay, `hydration.py:267`), `arbiter.py:104,203` | `draft.py:29` `_pop_step_feedback(step, context)`, `generation.py:50` `_pop_findings(context, step)`, `dual_pipeline.py:284` |
| `scenario_test_failures` | the QA runner's exports | `validation.py:434` | `arbiter.py:83,140,148,260`; popped `:103,187,201` |
| `mention_scanner:resolved` | `list[ResolvedMention]` | `review.py:363` | `review.py:336` |
| `scenario_test_path` | a path string | `scenario.py:221` | nothing |

- The arbiter writes the side keys as literals `"generate_code"` (`arbiter.py:104`) and
  `"generate_scenarios"` (`:203`); the same names sit in `dual_pipeline.py:59-62` `_SIDES`.
- `GenerateCodeHandler.FILENAME_PREFIX` (`generation.py:105`) and `GenerateTestsHandler`'s
  (`:316`) have no reader.
- `handlers/mcp_assembler.py` and `handlers/context_assembler.py` both open "Context Assembler".
- `interfaces/run_setup/builder.py:79,156` imports `roles_of` from the private `handlers/_llm.py`.

## Decided by the user (Phase 4)

### F-1 (HIGH) Tests of the code FR-12 removes move with it — A `[agreed 2026-11-04]`

FR-12 removes two things whose own tests check them by name:
- the two pop functions become one: `test_draft_feature_handler.py:400-430`
  (`TestPopStepFeedbackHelper`) calls `_pop_step_feedback(_step(), ctx)` 5 times;
- the `scenario_test_path` write goes: `test_scenario_handlers.py:351-369` asserts it is written.

These tests move to what replaces the code: the 5 calls become `pop_findings(ctx, "draft_feature")`
with the same 5 cases and the same expected values; the write test becomes "no `scenario_test_path`
is written". NFR-1's exception in the design names them. Keeping `_pop_step_feedback` as a wrapper
was rejected: it is a second pop function and a shim (AD-6).

## Findings settled without a user choice

### F-2 (HIGH) Keep `context.feedback` a dict; declare its keys in one module

149 test lines in 32 files read or write `context.feedback` as a dict. A typed model in its place
would change all of them, against NFR-1. So the dict stays, and a new module
`core/flow/run_state/feedback.py` (beside `run_context.py`, where `feedback` lives) declares:
- each fixed key with its value type: `SCENARIO_EVIDENCE` (`"scenario_test_failures"`, the QA
  exports dict), `RESOLVED_MENTIONS` (`"mention_scanner:resolved"`, a list);
- the loop-back entry type `StepFindings` (`from_step: str`, `findings: dict[str, Any]`), keyed by
  the target step's name;
- one writer `send_findings(context, to_step, from_step, findings)` and one pop function
  `pop_findings(context, step_name) -> dict | None`.

Every reader and writer under `core/flow` uses these names. A guard test refuses a string-literal
feedback key anywhere else.

### F-3 (MEDIUM) The two pop functions differ on a bad entry

`_pop_step_feedback` returns None when `findings` is not a dict; `_pop_findings` returns whatever
is there. The one function takes the stricter rule (pop it, then None). Every real writer
(`inject_feedback`, the arbiter) puts a dict there (`StepResult.output` is a dict), so only a
malformed entry is affected; it now degrades instead of failing later in the prompt build.

### F-4 (MEDIUM) The arbiter's side names

`dual_pipeline.py` gets a public `side_step(side) -> str` over `_SIDES` (both handlers live in
`core/flow/handlers`, no new edge). The arbiter calls `side_step("coder")` and
`side_step("scenario")`. A test checks each side step exists in its side pipeline's YAML, so a
renamed YAML step fails there and not in a run.

`"from_step": "arbitrate_verdict"` (`arbiter.py:105,204`) is the arbiter's own YAML name, not a side
name; FR-12 does not name it. It becomes the step's own name (`step.name`, threaded to `_route`), so
the YAML is the one source. No reader branches on `from_step`.

### F-5 (MEDIUM) Distinct assembler names

`context_assembler.py` builds skeleton context (`evaluate_and_fetch_skeleton_context`). It becomes
`skeleton_assembler.py`, titled "Skeleton assembler"; `mcp_assembler.py`'s title becomes "MCP
resource assembler". Imports change in `generation.py:283`, `review.py:170` and 24 test lines
(imports and `mock.patch` targets only, NFR-1). No shim (AD-6).

### F-6 (MEDIUM) `roles_of`'s public home

`roles_of` moves to a new public `core/flow/handlers/roles.py`. It cannot go to the engine: it calls
`dual_side_pipelines()` in `handlers/dual_pipeline.py`, and the engine knows no handler (AD-7).
`builder.py` and 3 test files (`test_dual_pipeline_step.py:41`, `test_llm_for.py:90`,
`test_two_models.py:37`) import it from there. `_llm.py` keeps `llm_for` and `llm_for_step`
(private to the handlers).

### F-7 (LOW) Two commit boundaries

CB-1: feedback keys, side names and the `scenario_test_path` write (its literal key is what the CB-1
guard refuses). CB-2: `FILENAME_PREFIX`, names, `roles_of` (closes SF-06).

### Phase 3 (architecture), no violation

| Mechanism | `core/flow/run_state/feedback.py` | Verdict |
|---|---|---|
| I/O, state | reads and writes the given dict only | ok, same as `run_context.py` |
| Execution, LLM | none | ok |
| Dependencies | `run_context` (TYPE_CHECKING) | inside its module |
| Domain | what one step hands the next in a run | matches `run_state`'s purpose |

- No cycle: `engine` and `handlers` already import `run_state`; `run_state` imports neither.
- `handlers/roles.py` imports `engine.models` and `handlers.dual_pipeline`, both already used by
  `_llm.py`. `interfaces/run_setup` already depends on `core.flow.handlers` (tach); there is no
  `[[interfaces]]` block for `core.flow.handlers`, so no expose list changes.

## Decisions (no user choice needed)

### D-1 Readers and writers after CB-1

| Site | After |
|---|---|
| `gates.py:146` `inject_feedback` | calls `send_findings` (the resume replay keeps calling `inject_feedback`) |
| `arbiter.py:104,203` | `send_findings(context, side_step(...), step.name, {...})` |
| `arbiter.py` evidence reads and pops | `SCENARIO_EVIDENCE` |
| `validation.py:434` | `context.feedback[SCENARIO_EVIDENCE] = ...` |
| `review.py:336,363` | `RESOLVED_MENTIONS` |
| `draft.py:29`, `generation.py:50` | removed; callers use `pop_findings(context, step.name)` |
| `DraftSpecHandler._pop_feedback` (`draft.py:131`, a third pop, found in dev) | removed with its delegate test; `test_draft_handler.py:195-222` call `pop_findings` (F-1) |
| `scenario.py:221` | removed (no reader; FR-12) |
| `dual_pipeline.py:91,284` | unchanged (they read the side keys through `_SIDES`, which is the table) |

> [!NOTE]
> `dual_pipeline.py:284` moves a whole entry into the side's own feedback dict; it does not read
> findings. The side's step reads them with `pop_findings`. So it is not a second pop function, and
> the guard passes it (its key is a name, not a literal).

> [!CAUTION]
> `pop_findings` keeps the `hasattr(context, "feedback")` check and returns None for an empty dict.
> Many handler tests pass a `MagicMock` or a namespace as the context (NFR-1).

### D-2 Mutants to re-point (NFR-4)

B-FLOW-01 mutants in `arbiter.py` (`_code_bug`, `_scenario_error`, `_route`) and
`dual_pipeline.py` (`_build_runner`, `_sides_to_run`); whatever `stale_mutants.py` names after each
boundary. Each is re-run before its refresh.

### D-3 Which documents change

- `docs/architecture/02_bounded_contexts/domain_flow_engine.md`: `context.feedback`'s keys live in
  `run_state/feedback.py`.
- `docs/dev_guides/pipeline_engine_guide.md`: a step's loop-back findings are read with
  `pop_findings`; the assembler names.
- The design: NFR-1's exception (F-1), written at Phase 4.

### D-4 Out of scope

- Persisting `context.feedback` across a resume (design Non-Goals).
- The `inject_feedback` name (`test_validate_spec_findings.py:16` calls it a misnomer); it stays as
  the engine's call.

## Path List rows this SF owns

| Row | Interface first exists | Test |
|---|---|---|
| P-7 dual run → arbiter verdict → the side at fault gets its findings | CB-1 | existing `test_scenario_integration_dispatch.py`, `test_dual_run_feedback.py`, `test_side_at_fault_reruns.py`, `test_scenario_verification_e2e.py` pass with import edits only |
| P-8 a run builder asks which roles a pipeline needs (`roles_of`) | CB-2 | `test_two_models.py`, `interfaces/run_setup` tests pass, importing from `handlers/roles.py` |

## Commit Boundaries

### CB-1 (interior): declared feedback keys; the arbiter uses the side table; the unread write goes — FR-12

**Red first**:

1. `tests/unit/core/flow/run_state/test_feedback.py` (`Proves: TECH-082 FR-12`), red (no module):
   - happy: `send_findings` then `pop_findings` returns the findings once; a second pop is None.
   - boundary: an empty feedback dict gives None; another step's entry is left alone.
   - degradation: an entry with no `findings`, or a non-dict one, is popped and gives None.
   - hostile: an entry that is not a dict (a string) is popped and gives None.
2. `tests/unit/core/flow/test_feedback_keys_declared_once.py` (`Proves: TECH-082 FR-12`): an AST scan
   of `src/specweaver/core/flow` finds no string literal used as a `.feedback[...]` key or as the
   first argument of `.feedback.get/pop/setdefault`, outside `run_state/feedback.py`; and no
   `"generate_code"`/`"generate_scenarios"` literal in `arbiter.py`. Red: `arbiter.py`,
   `validation.py`, `review.py`, `scenario.py`.
   - boundary: a key held in a name (`context.feedback[step.name]`) passes.
   - degradation: an unparsable file is named.
   - hostile: an f-string key is found.
3. `tests/unit/core/flow/handlers/test_dual_pipeline.py` (+1): each `side_step` names a step that
   exists in its side pipeline's YAML. Red: no `side_step`.

4. `test_scenario_handlers.py:351`: becomes "ConvertScenarioHandler writes no `scenario_test_path`"
   (F-1). Red: it writes one.

**Green**: F-2, F-3, F-4, D-1; remove `scenario.py:221`; move `test_draft_feature_handler.py`'s 5
calls (F-1); re-point mutants (D-2).

**Done when**: `tach check`, `stale_mutants.py` pass; these mutants are killed:
- in `pop_findings`, return without popping → red 1 (happy, second pop).
- in the arbiter's code-bug branch, send to `side_step("scenario")` →
  `test_scenario_integration_dispatch.py` goes red.
- in `validation.py`, write the evidence under a literal `"scenario_test_failures"` → red 2.
- put the `scenario_test_path` write back → red 4.

**Gate**: `python scripts/tests.py cb TECH-082 --kind refactor`, `specweaver-pre-commit`, commit.

### CB-2 (closes SF-06, HITL): `FILENAME_PREFIX`, names, public `roles_of` — FR-12

**Red first**:

1. `tests/unit/core/flow/test_flow_names.py` (`Proves: TECH-082 FR-12`), red:
   - `GenerateCodeHandler` and `GenerateTestsHandler` have no `FILENAME_PREFIX`.
   - importing `specweaver.core.flow.handlers.context_assembler` raises `ModuleNotFoundError`; the
     two assemblers' module docstrings open with different titles.
   - no module outside `core/flow/handlers` imports `specweaver.core.flow.handlers._llm` (AST scan of
     `src/`). Red: `builder.py:79,156`.
**Green**: remove both `FILENAME_PREFIX`; F-5; F-6; docs (D-3).

**Done when**: P-8's tests pass; these mutants are killed:
- in `builder.py`, import `roles_of` from `_llm` again → red 1.

**Gate**: `python scripts/tests.py cb TECH-082 --kind refactor`, then `specweaver-pre-commit`,
stage, **STOP** for the user.

## Research Notes

- `RunContext.feedback: dict[str, Any]` (`run_state/run_context.py:174`).
- `GateEvaluator.inject_feedback(context, from_step, to_step, result)` (`gates.py:146`) writes
  `{"from_step": from_step, "findings": result.output}`; called from `step_execution.py:350` and
  `hydration.py:267`.
- `PipelineRunner.spawn(pipe, feedback=..., side=...)` (`runner.py:111`) gives a sub-run its own dict.
- `dual_side_pipelines()` (`dual_pipeline.py:146`) builds both side pipelines from `_SIDES`.
- `ResolvedMention` is in `infrastructure/llm/mention_scanner`; `run_state` may import
  `infrastructure.llm` (tach), so the key's type can name it under TYPE_CHECKING.
- No `[[interfaces]]` block exists for `specweaver.core.flow.handlers` or `.run_state`.

## Red/Blue (Phase 5), 2 cycles

- R1 (HIGH, fixed) The CB-1 guard refuses the literal key at `scenario.py:221`, but the plan removed
  that write only in CB-2, so CB-1 could not go green. The write and its test move to CB-1.
- R2 (MEDIUM, fixed) F-6 counted 4 test files that import `roles_of`; there are 3. Named them.
- R3 (MEDIUM, fixed) `dual_pipeline.py:284` also pops an entry. It moves the entry to the side, and
  the side reads it with `pop_findings`. Written as a note beside D-1.
- R4 (MEDIUM, fixed) Tests pass a `MagicMock` or a namespace as the context. `pop_findings` keeps the
  `hasattr` check. Written as a caution beside D-1.
- R5 (LOW) `from_step` becomes `step.name`. No reader branches on it; no test asserts the arbiter's
  `from_step` (grep `from_step` in the arbiter tests). The bundled YAML names the step
  `arbitrate_verdict`, so a real run writes the same value.
- R6 (LOW) The stricter pop rule (F-3) changes nothing for a real run: every writer puts a dict.
- Cycle 2: challenged R1 (does any other CB-1 red depend on CB-2 code?): the guard reads only
  `core/flow`; `FILENAME_PREFIX`, the assemblers and `roles_of` hold no feedback key. Challenged F-5
  (NFR-3 lists no assembler path): CB-2 test 1 checks the old path fails to import, so no shim can
  stay. No new finding above LOW.

## Backlog
