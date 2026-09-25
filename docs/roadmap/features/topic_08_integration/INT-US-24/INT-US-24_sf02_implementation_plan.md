# INT-US-24 SF-02 — Close the Feedback Loop

**Status**: APPROVED — Phase 4 (Q1–Q4) approved 2026-07-24; Phase 5 (R/B: step-name pin T3c,
call-site guard, NFR-4 log) approved 2026-07-24. Dev complete 2026-07-24. · **FRs owned**: FR-4, FR-6 · **Depends on**: SF-01 · Design:
[INT-US-24_design.md](INT-US-24_design.md) §Sub-features → SF-02

## Goal

- **FR-4** — `GenerateScenarioHandler` consumes `context.feedback["generate_scenarios"]` pop-once
  via the `_extract_prompt_feedback` contract and injects the arbiter's `scenario_error` findings
  into the regeneration prompt; without feedback, byte-identical.
- **FR-6** — on a `code_bug` loop-back, the coding pipeline's regeneration input contains no
  scenario vocabulary — pinned at the REAL arbiter→generation seam, not just the guard's unit tests.

The arbiter dead-code cleanup planned here already landed in SF-01 (`3fece855`). Out of scope: SF-03
CLI journey/proof; a scenario-side mechanical vocabulary guard (B-FLOW-01 FR-9's scenario-side
constraint stays prompt-instructed — `B-INTL-07` territory).

## Where it plugs in

| Fact | Where |
|---|---|
| `_extract_prompt_feedback(context, step)` pops `context.feedback[step.name]`, returns `(dictator_overrides, validation_findings)`. The arbiter's `scenario_error` write — `{"findings": {"results": [{"status": "FAIL", "rule_id": <spec_clause>, "message": <scenario_feedback>}]}}` — is compatible; extraction yields `"[<rule_id>] <message>"` lines. `dictator_overrides` (hitl reject remarks) is never written for scenarios. | `generation.py:75-93`; `arbiter.py` |
| Pattern to mirror: `GenerateCodeHandler` passes `validation_findings=validation_findings` as a named kwarg into `generator.generate_code`. | `generation.py:135,169-170` |
| `ScenarioGenerator.generate_scenarios(spec_content, contract_content, req_ids, *, constitution=None, project_metadata=None)` has no feedback parameter. Its prompt is built once in `_build_prompt` (static, keyword-only) and reused across the JSON-retry loop, so a feedback block persists across retries for free. | `scenario_generator.py:47-55` |
| `GenerateScenarioHandler.execute` already imports `_resolve_generation_routing` from `generation.py`; importing `_extract_prompt_feedback` adds no boundary. The step in `scenario_validation.yaml` is named `generate_scenarios` (the arbiter's key). The dual sub-runner shares the parent `RunContext`, so the pop crosses the runner boundary as on the coding side. | `scenario.py:24-91` |
| `SCENARIO_VOCABULARY` frozenset + `_guard_coding_feedback` rewrite leaky coding feedback; guarded text flows into `feedback["generate_code"].findings.results[].message`. SF-01 pins vocabulary-free routing; the next hop — what a REAL `GenerateCodeHandler` hands the Generator — is not yet pinned. | `arbiter.py:46-82` |
| Existing tests: `test_scenario_handlers.py::TestGenerateScenarioHandler` (5, no feedback coverage); `tests/unit/workflows/scenarios/test_scenario_generator.py` (no feedback coverage); `test_scenario_integration_dispatch.py` (SF-01 chain — home for the seam pins). | tests |

Boundaries: `scenario_generator.py` change is additive in `workflows/scenarios`, a module
`core.flow` already consumes — no reverse dependency. `scenario.py` → `generation.py` is a
same-package import already precedented (`_resolve_generation_routing`). No new modules, no
enum/YAML/sandbox changes; `tach` unaffected.

## Changes

TDD, red first. Single commit boundary CB-1.

1. **T1 — generator feedback param** · `workflows/scenarios/scenario_generator.py` — optional
   keyword-only `feedback` (Q1).
2. **T2 — handler consumption** · `core/flow/handlers/scenario.py` — extract via
   `_extract_prompt_feedback` and pass `feedback=`; INFO log naming the regeneration-with-feedback
   (NFR-4). Empty/malformed `findings` → treated as no feedback, via a CALL-SITE guard around the
   extraction; the shared `_extract_prompt_feedback` stays untouched (NFR-1 protects its three
   coding-side consumers).
3. **T3 — seam-chain pins** · `test_scenario_integration_dispatch.py` (Q3).

Commit: `feat(flow): feedback-aware scenario regeneration + opacity seam pins (INT-US-24 SF-02)`.
Direct to main.

## Tests

| Task | Bucket | Case |
|---|---|---|
| T1 — `test_scenario_generator.py` | Happy | (a) prompt contains the feedback block + text when provided |
| | Happy | (b) omitted/None → prompt byte-identical |
| | Boundary | (c) block persists in the retry prompt after an invalid first response |
| | Hostile | (d) hostile feedback text (markdown fences/braces) lands verbatim without breaking assembly |
| T2 — `test_scenario_handlers.py` | Happy | (a) arbiter-shaped `feedback["generate_scenarios"]` → called with `"[FR-x] message"`, key popped, INFO log |
| | Happy | (b) no feedback → `feedback=None`, `context.feedback` untouched |
| | Boundary | (c) unrelated feedback keys survive the pop |
| | Degradation | (d) empty/malformed `findings` → no-feedback, no crash |
| T3 — dispatch integration | Happy | (a) FR-6: LEAKY code_bug verdict → Generator's `validation_findings` scenario-vocabulary-free |
| | Happy | (b) FR-4: arbiter → handler → ScenarioGenerator feedback kwarg carries the delta, key popped |
| | Boundary | (c) YAML step-name pin: the arbiter writes the FIXED keys `generate_code`/`generate_scenarios`; `new_feature.yaml` and `scenario_validation.yaml` must name their steps so (sibling of SF-01's reserved-key pin — a rename would strand verdict feedback) |

FR-6's leaky vocabulary is itself the hostile input on the arbiter side.

## Decisions (audit)

| Q | Decision | Resolution |
|---|----------|-----------|
| Q1 | Feedback entry point | New optional keyword-only param on `ScenarioGenerator.generate_scenarios` (e.g. `feedback: str | None = None`), threaded into `_build_prompt` as a clearly-labeled prior-verdict block placed before the output-schema instructions. Additive + default None = byte-identical without feedback |
| Q2 | Dictator half | Ignored for scenarios (never written by the arbiter); only `validation_findings` is threaded. Documented, not plumbed speculatively (YAGNI) |
| Q3 | FR-6/FR-4 pin shape | Extend `test_scenario_integration_dispatch.py` with seam-chain tests: (a) arbiter executes with a LEAKY code_bug LLM verdict → real guard → REAL `GenerateCodeHandler` (Generator mocked) → captured `validation_findings` kwarg contains the guarded text and none of `SCENARIO_VOCABULARY`; (b) arbiter `scenario_error` → REAL `GenerateScenarioHandler` (ScenarioGenerator mocked) → captured feedback kwarg carries the behavioral delta, and the feedback key was popped |
| Q4 | Consumed-even-on-failure | Pop-once stands even if regeneration then crashes — the next loop iteration re-publishes fresh findings (mirrors the shipped coding-side behavior); documented |

Accepted risks (R/B): prompt injection via the LLM-authored `scenario_feedback` into the
regeneration prompt — pre-existing class flagged at SF-01, `E-VAL-03` scope (queue Candidate 4),
not widened. The scenario-side "no source code in feedback" constraint (B-FLOW-01 FR-9) stays
prompt-instructed with no mechanical guard — `B-INTL-07` territory. Step-name/verdict-key coupling
on the coding side (`generate_code`) predates this SF; now pinned by T3c, not redesigned.

## As built (2026-07-24)

FR-6 landed as proof only — the guard was already correct; the seam pin asserts every
SCENARIO_VOCABULARY term absent from the real Generator input. Gap pins G-a/G-b added; full suite
5479 passed / 0 failures. Walkthrough: [sf02](INT-US-24_sf02_walkthrough.md).
