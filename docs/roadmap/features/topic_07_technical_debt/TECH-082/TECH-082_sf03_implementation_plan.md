# Implementation Plan: Domain Logic Lives in the Flow Engine [SF-03: Arbitration home and thin handlers]
- **Feature ID**: TECH-082
- **Sub-Feature**: SF-03 — Arbitration home and thin handlers
- **Design Document**: docs/roadmap/features/topic_07_technical_debt/TECH-082/TECH-082_design.md
- **Design Section**: §Sub-Feature Breakdown → SF-03
- **Implementation Plan**: docs/roadmap/features/topic_07_technical_debt/TECH-082/TECH-082_sf03_implementation_plan.md
- **Status**: APPROVED (the user, 2026-11-04)

## Scope

The arbiter's model work leaves `core/flow/handlers/arbiter.py` for the new module
`specweaver.workflows.arbitration` (AD-2). After it, no flow handler calls a model itself. FRs:
**FR-5, FR-6**. NFRs carried: NFR-1 (same behaviour), NFR-2 (boundaries hold), NFR-4 (mutants
re-pointed). NFR-3 does not apply: `arbiter.py` stays, it only gets thinner. Kind: `refactor`.

| Moves | From | To |
|---|---|---|
| `ArbitrateVerdict`, `ArbitrateResult` | `arbiter.py:32-47` | `workflows/arbitration/verdict.py` |
| `ARBITRATE_INSTRUCTIONS` | `arbiter.py:111-129` | same |
| the evidence text (failures → text, the errors-only line) | `arbiter.py:359-370` | same, `evidence_text(...)` |
| the model call and the parse (prompt in, `generate`, JSON extract, `ArbitrateResult`) | `arbiter.py:394-412` | same, `arbitrate(...)` |
| the coder and scenario guards (D-6) | `arbiter.py:50-108,132-155,223-230` | same |

The handler keeps: the park and evidence checks, the `total == 0` and all-green branches,
`llm_for`, the stack trace filter (it needs `sandbox`), the prompt build (`_build_base_prompt` is
in `core/flow`), and the verdict routing into `context.feedback`.

## Decisions (Phase 4, the user 2026-11-03)

- **D-6 The coder and scenario guards move too** `[agreed 2026-11-03]` (F-1 A):
  `SCENARIO_VOCABULARY`, `_guard_coding_feedback`, `scenario_safe`, `code_trace` and `_with_trace`
  (about 90 lines of pure text rules: which words the coder may see) go to
  `workflows/arbitration/verdict.py`. The handler passes in the filter it built.
  `_guard_coding_feedback` becomes public `guard_coding_feedback`, and `_with_trace` becomes
  `with_trace` (no private name crosses a module). `code_trace` types its filter as
  `StackTraceFilterInterface` (a TYPE_CHECKING import; tach counts it), so tach gets
  `workflows.arbitration → workspace.ast.parsers` (downward; `infrastructure.llm` has the same edge;
  `interfaces.StackTraceFilterInterface` is already in that module's `[[interfaces]]`). FR-5 in the
  design now says so.

## Findings settled without a user choice

### F-2 (MEDIUM) A reply that is not JSON

Today the handler returns ERROR "Failed to parse LLM verdict: <raw>". The new `arbitrate` raises
`UnreadableVerdict(raw)` (a `ValueError`); the handler turns it into the same message. A verdict the
model names wrongly still raises pydantic's `ValidationError`, caught by the handler's catch-all, as
today. No user choice: same behaviour (NFR-1).

### F-3 (MEDIUM) The string reply

`arbiter.py:399` accepts a reply that is a plain string ("the unit-mock convention"). 13 handler
tests script the model that way. `arbitrate` keeps the check, so those tests change only imports
(NFR-1). No user choice.

### F-4 (MEDIUM) The handler must pass complexity 10 without `noqa`

After the move, `execute` still has the evidence branches and the 3-way routing (today 14). Split:
`_no_failures(...)` (the all-green branch) and `_route(result, ...)` (the 3 verdicts). FR-6's guard
below checks it. `ValidateTestsHandler.execute` and `LintFixHandler` already pass (measured:
`ruff check --select C901 --ignore-noqa` flags only `arbiter.py:300`). No user choice.

### F-5 (LOW) One commit boundary

FR-6's guard is red today only because of `arbiter.py:396`. If it is written after the move, it can
never fail. So the guard, the move and the split are one boundary, the one that closes SF-03.

### F-6 (LOW) `ArbitrateVerdict.ERROR` has no user

Nothing sets it. It moves as it is (NFR-1). No change here.

### Phase 3 (architecture), no violation

| Mechanism | `workflows/arbitration` (orchestrator) | Verdict |
|---|---|---|
| I/O, state | none (text in, text out) | ok |
| Execution | none (the trace filter is built in the handler, from `sandbox`) | ok |
| LLM | `adapter.generate`, `Message`, `Role` from `infrastructure/llm` | consumed |
| Dependencies | `infrastructure.llm`, `commons.json` (utility), `workspace.ast.parsers` (type only, D-6) | downward, no cycle |
| Domain | the dual run's verdict and what each side may read | matches its `purpose` |

- Zoom-out: `workflows/review` also judges with a model, but the user chose a module of its own
  (AD-2, design cycle 2).
- No cycle: `workflows.arbitration` imports nothing from `core/flow`; `core.flow.handlers` gets the
  edge to it.
- Boundary rule (FR-15): the root manifest has `consumes: []` and no `forbids`; `infrastructure/llm`
  is a sibling under the root, so no `widens` is needed.

## Decisions (no user choice needed)

### D-1 The split

- `workflows/arbitration/verdict.py`:
  - `ArbitrateVerdict`, `ArbitrateResult`, `ARBITRATE_INSTRUCTIONS`, moved as they are.
  - `evidence_text(failures, errors, total) -> str`: the lines `nodeid: message\nstacktrace`, or the
    errors-only line when none carries text.
  - `async arbitrate(adapter, config, prompt: str) -> ArbitrateResult`: one user message, the
    string-reply check (F-3), the `{...}` extract, `json.loads`, `ArbitrateResult(**data)` with
    `raw_response` set. A reply with no JSON raises `UnreadableVerdict(raw)` (F-2). Adapter errors
    propagate.
  - The guards (D-6), moved as they are, two renamed public.
- The handler's model step, in order: `evidence_text` → the filter (handler) →
  `_build_base_prompt(context, ARBITRATE_INSTRUCTIONS, profile=...)` + the filtered text →
  `llm_for(context, TaskType.REVIEW)` → `arbitrate` → guards → `_route`.

### D-2 tach and manifest edges

| Module | Change |
|---|---|
| `specweaver.workflows.arbitration` (new) | `depends_on = ["specweaver.infrastructure.llm", "specweaver.workspace.ast.parsers"]`; `[[interfaces]]` = the manifest's `exposes` |
| `specweaver.core.flow.handlers` | + `workflows.arbitration` |

- `workflows/arbitration/context.yaml`: archetype `orchestrator`; consumes `specweaver/infrastructure/llm`
  and `specweaver/workspace/ast/parsers`; forbids `specweaver/sandbox/*` and
  `specweaver/core/flow/*`; `exposes` = every name `src/` and the handlers import, from a grep at the
  boundary, not from memory.
- `core/flow/handlers/context.yaml` consumes `specweaver/workflows/arbitration`.
- `tests/unit/test_boundary_rule_holds.py` and `test_manifests_match_tach.py` re-check them.

### D-3 Tests and mutants

- Import edits only (NFR-1): `tests/unit/core/flow/handlers/test_arbiter.py` (`TestArbitrateVerdict`,
  `TestArbitrateResult` and the guard tests move to
  `tests/unit/workflows/arbitration/test_verdict.py`); also
  `test_arbiter_tells_coder_and_human.py`, `test_scenario_report_filtered.py`,
  `test_scenario_integration_dispatch.py`, `test_scenario_verification_e2e.py`.
- `mock.patch` strings on `specweaver.core.flow.handlers.arbiter` (`test_build_base_prompt_profiles.py:181,279,366`)
  stay valid: the handler does not move. `test_logging_rollout.py` adds the new module.
- B-FLOW-01 mutants in `arbiter.py` (9): `scenario-report-unfiltered` and `set-not-kept` anchor in
  `execute` and are re-anchored in `_route` and `_no_failures`; `no-trace`,
  `check-frames-kept`, `banned-words-pass` move file to `verdict.py`. Every mutant whose symbol
  changed is refreshed: `python scripts/_corpus.py --corpus <file> --refresh "<derived id>"`.

### D-4 Which documents change

- `docs/architecture/03_system_topology/module_dependency_graph.md`: the arbitration module; the
  design's guides row turns ✅ for it.
- `docs/dev_guides/layer_isolation_and_di.md`: "a handler is a shell: it gathers inputs from the run,
  calls a workflow with plain values, and writes the result back"; the design's guides row turns ✅.
  SF-03 is the last move, so the rule is true from here.
- Closed stories' documents keep the old paths (`finished-stories-immutable`).

### D-5 Out of scope

- `work_unit.py`'s agentic loop calls `generate_with_tools` in the engine (FR-6 excludes it).
- The feedback keys `generate_code` and `generate_scenarios` the arbiter writes: SF-06 (FR-12).
- The arbiter's role (`TaskType.REVIEW`) moving into the step table: SF-05 (FR-9).

## Path List rows this SF owns

| Row | Interface first exists | Test |
|---|---|---|
| P-7 `sw run scenario_integration` → dual run → `arbitrate`+`verdict` → arbitration workflow → model | CB-1 | existing `tests/integration/core/flow/handlers/test_arbiter_integration.py`, `test_scenario_integration_dispatch.py`, `test_scenario_report_filtered.py`, `test_one_reviewed_spec.py`, `test_kept_suite.py` and `tests/e2e/capabilities/workflows/test_scenario_verification_e2e.py` pass with import edits only |

## Commit Boundaries

### CB-1 (closes SF-03, HITL): the arbiter's model work moves; no handler calls a model — FR-5, FR-6

**Red first**:

1. `tests/unit/core/flow/handlers/test_no_handler_calls_a_model.py` (`Proves: TECH-082 FR-6`): an
   AST scan of every module under `core/flow/handlers` finds no call `<x>.generate(...)` or
   `<x>.generate_with_tools(...)`, and no `noqa: C901`. Red: `arbiter.py:396` and `:300`.
   - happy: a clean handler passes.
   - boundary: a call inside a nested function is found; `hasattr(adapter, "generate_with_tools")`
     (a string, `review.py:48`, `scenario.py:27`) is not a call and passes.
   - degradation: an unparsable file is named, not skipped.
   - hostile: `getattr(adapter, "generate")(...)` is found too; a bare `# noqa` on a `def` line
     counts as hiding C901; `self._generate(...)` (`generation.py:128`) is another name and passes.
2. `tests/unit/workflows/arbitration/test_verdict.py` (`Proves: TECH-082 FR-5`), red (no module):
   - happy: a fake adapter's JSON gives the right verdict and keeps the raw reply; the prompt reaches
     the adapter as one user message.
   - boundary: JSON wrapped in prose is found; `evidence_text` with no failure text gives the
     errors-only line.
   - degradation: an adapter error propagates; a plain string reply is read (F-3).
   - hostile: a reply with no JSON raises `UnreadableVerdict` naming the raw text; an unknown verdict
     raises `ValidationError`.
3. `tests/unit/workflows/arbitration/test_arbitration_has_its_own_home.py`
   (`Proves: TECH-082 FR-5, TECH-082 NFR-2`): the moved names exist in the new module, and an AST
   scan of `arbiter.py` finds no class, function or assignment that defines one of them (an import
   is allowed: the handler uses them, so `hasattr` would pass and prove nothing); an AST scan finds no import of `specweaver.sandbox` or `specweaver.core.flow` in
   the new module. Red: no module.

**Green**: write `verdict.py` (D-1); the handler calls it; split `execute` (F-4) and drop the
`noqa`; manifests and tach (D-2); move the tests and edit imports (D-3); re-point and refresh the
mutants; docs (D-4).

**Done when**: all of P-7's tests pass with import edits only; `tach check`,
`test_boundary_rule_holds.py` and `stale_mutants.py` pass; these mutants are killed:
- in `arbitrate`, parse the reply whole, without the `{...}` extract → a test with JSON in prose goes
  red (unit; if no integration test objects, add one: the real handler with a model that wraps its
  JSON in a sentence still routes `code_bug`).
- in the handler, route `scenario_error` to the coder's key → `test_scenario_integration_dispatch.py`
  goes red.
- in a handler, add `adapter.generate(...)` back → the FR-6 guard goes red.

**Gate**: `python scripts/tests.py cb TECH-082 --kind refactor`, then `specweaver-pre-commit`,
stage, **STOP** for the user.

## Research Notes

- `ArbitrateVerdictHandler.execute(step, context) -> StepResult` (`arbiter.py:300`), C901 14.
- `llm_for(context, TaskType.REVIEW)` (`handlers/_llm.py`); `_build_base_prompt(context,
  instructions, *, profile=None, skeleton_files=None)` imported from `handlers.base`.
- `create_stack_trace_filter(project_path)` (`sandbox.language.core.stack_trace_filter_factory`);
  13 tests patch it by that full path, so its call stays in the handler unchanged.
- `StackTraceFilterInterface` is an ABC in `workspace/ast/parsers/interfaces.py:377` with
  `filter(text)` and `is_scenario_frame(line)`.
- tach today: `workflows.review` depends only on `infrastructure.llm`; `infrastructure.llm` depends
  on `workspace.ast.parsers`; `core.flow.handlers` depends on `workflows.review`,
  `workflows.implementation`, `workflows.scenarios`, `workflows.planning`.
- SF-01's `explain_drift(adapter, config, findings, file_path)` and SF-02's `repair_lint(...)` are
  the shape: adapter, config and plain values in, plain value out.
- `ruff check --select C901 --ignore-noqa src/specweaver/core/flow/handlers/` flags only
  `arbiter.py:300` (14 > 10), measured 2026-11-03.

## Red/Blue (Phase 5), 2 cycles

- R1 (MEDIUM) The home guard first checked "not in `arbiter.py`" by name; the handler imports the
  names, so that check could never fail. Fixed: an AST scan for definitions.
- R2 (MEDIUM) The FR-6 guard looked only for `noqa: C901`; a bare `# noqa` on a `def` line hides it
  too. Fixed: a hostile case.
- R3 (LOW) The moved guard logs "ArbitrateVerdictHandler: Vocabulary leak caught" under the new
  module's logger. No test reads that logger name (grep); the text stays (NFR-1).
- R4 (LOW) 13 tests patch `create_stack_trace_filter` by its full path. Its call stays in the handler,
  so the patch still lands.
- Cycle 2: challenged R1's fix (a re-export `X = verdict.X` is an assignment, so it is caught) and
  D-6's new edge (`StackTraceFilterInterface` is already in the parsers' `[[interfaces]]`). No new
  finding above LOW.

## Backlog
