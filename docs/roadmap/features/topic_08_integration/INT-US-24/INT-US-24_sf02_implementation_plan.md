# Implementation Plan: INT-US-24 [SF-02: Close the Feedback Loop]

- **Feature ID**: INT-US-24
- **Sub-Feature**: SF-02 — Close the Feedback Loop
- **Design Document**: docs/roadmap/features/topic_08_integration/INT-US-24/INT-US-24_design.md
- **Design Section**: §Sub-Feature Breakdown → SF-02
- **Implementation Plan**: docs/roadmap/features/topic_08_integration/INT-US-24/INT-US-24_sf02_implementation_plan.md
- **Status**: APPROVED <!-- Phase 4 (Q1–Q4) approved 2026-07-24; Phase 5 (R/B: step-name pin T3c, call-site guard, NFR-4 log) approved 2026-07-24 -->

## Scope (from design)

- **FR-4** — feedback-aware scenario regeneration: `GenerateScenarioHandler` consumes
  `context.feedback["generate_scenarios"]` pop-once via the `_extract_prompt_feedback` contract
  and injects the arbiter's `scenario_error` findings into the regeneration prompt; without
  feedback, byte-identical.
- **FR-6** — opacity through the integrated loop: on a `code_bug` loop-back, the coding
  pipeline's regeneration input contains no scenario vocabulary — pinned at the REAL
  arbiter→generation seam, not just the guard's unit tests.

As-built delta from SF-01: the arbiter dead-code cleanup slated here already landed in
`3fece855`. Out of scope: SF-03 CLI journey/proof; scenario-side mechanical vocabulary guard
(FR-9's scenario-side constraint is prompt-instructed, unchanged — `B-INTL-07` territory).

## Research Notes (Phase 0)

1. **Extraction contract**: `_extract_prompt_feedback(context, step)` (`generation.py:75-93`)
   pops `context.feedback[step.name]`, returns `(dictator_overrides, validation_findings)`;
   the arbiter's `scenario_error` write (`{"findings": {"results": [{"status": "FAIL",
   "rule_id": <spec_clause>, "message": <scenario_feedback>}]}}`, `arbiter.py`) is compatible
   out of the box — extraction yields `"[<rule_id>] <message>"` lines. The `dictator_overrides`
   half (hitl reject remarks) is never written for scenarios — unused here.
2. **Injection pattern to mirror**: `GenerateCodeHandler` passes
   `validation_findings=validation_findings` as a named kwarg into `generator.generate_code`
   (`generation.py:135,169-170`). `ScenarioGenerator.generate_scenarios(spec_content,
   contract_content, req_ids, *, constitution=None, project_metadata=None)`
   (`scenario_generator.py:47-55`) has NO feedback parameter today; its prompt is built once in
   `_build_prompt` (static, keyword-only) and reused across its JSON-retry loop, so a feedback
   block added at build time persists across retries for free.
3. **Handler site**: `GenerateScenarioHandler.execute` (`scenario.py:24-91`) already imports
   `_resolve_generation_routing` from `generation.py` — importing `_extract_prompt_feedback`
   from the same module adds no boundary. Step name in `scenario_validation.yaml` is
   `generate_scenarios` (matches the arbiter's key). The dual sub-runner shares the parent
   `RunContext`, so the pop crosses the runner boundary exactly like the coding side.
4. **Opacity guard**: `SCENARIO_VOCABULARY` frozenset + `_guard_coding_feedback`
   (`arbiter.py:46-82`) rewrite leaky coding feedback; guarded text flows into
   `feedback["generate_code"].findings.results[].message`. The SF-01 dispatch test already pins
   vocabulary-free routing; what is NOT yet pinned is the next hop — that the text a REAL
   `GenerateCodeHandler` extracts and hands to the Generator stays clean.
5. **Existing tests**: `test_scenario_handlers.py::TestGenerateScenarioHandler` (5 tests — no
   feedback coverage); `tests/unit/workflows/scenarios/test_scenario_generator.py` (prompt/
   parsing units — no feedback coverage); `test_scenario_integration_dispatch.py` (SF-01 chain —
   natural home for the seam pins).

## Resolved Decisions (Phase 4 merge — pending HITL)

| Q | Decision | Resolution |
|---|----------|-----------|
| Q1 | Feedback entry point | New optional keyword-only param on `ScenarioGenerator.generate_scenarios` (e.g. `feedback: str | None = None`), threaded into `_build_prompt` as a clearly-labeled prior-verdict block placed before the output-schema instructions. Additive + default None = byte-identical without feedback |
| Q2 | Dictator half | Ignored for scenarios (never written by the arbiter); only `validation_findings` is threaded. Documented, not plumbed speculatively (YAGNI) |
| Q3 | FR-6/FR-4 pin shape | Extend `test_scenario_integration_dispatch.py` with seam-chain tests: (a) arbiter executes with a LEAKY code_bug LLM verdict → real guard → REAL `GenerateCodeHandler` (Generator mocked) → captured `validation_findings` kwarg contains the guarded text and none of `SCENARIO_VOCABULARY`; (b) arbiter `scenario_error` → REAL `GenerateScenarioHandler` (ScenarioGenerator mocked) → captured feedback kwarg carries the behavioral delta, and the feedback key was popped |
| Q4 | Consumed-even-on-failure | Pop-once stands even if regeneration then crashes — the next loop iteration re-publishes fresh findings (mirrors the shipped coding-side behavior); documented |

## Task Breakdown (TDD; single commit boundary CB-1)

- **T1 — generator feedback param** (`workflows/scenarios/scenario_generator.py` +
  `tests/unit/workflows/scenarios/test_scenario_generator.py`): red: (a) prompt contains the
  feedback block + its text when provided; (b) omitted/None → prompt byte-identical to today;
  (c) feedback block persists in the retry prompt after an invalid first response;
  (d) hostile feedback text (markdown fences/braces) lands verbatim as text without breaking
  prompt assembly. Then implement the optional kwarg + prompt block.
- **T2 — handler consumption** (`core/flow/handlers/scenario.py` +
  `test_scenario_handlers.py`): red: (a) `feedback["generate_scenarios"]` in arbiter shape →
  `generate_scenarios` called with the extracted `"[FR-x] message"` text AND the key popped
  (consume-once), with an INFO log naming the regeneration-with-feedback (NFR-4); (b) no
  feedback → called with `feedback=None`, `context.feedback` untouched (byte-identical);
  (c) unrelated feedback keys survive the pop; (d) feedback present but with empty/malformed
  `findings` → treated as no-feedback, no crash — implemented as a CALL-SITE guard around the
  extraction (the shared `_extract_prompt_feedback` stays untouched; NFR-1 protects the three
  coding-side consumers). Then wire the extraction in.
- **T3 — seam-chain opacity + regeneration pins** (`test_scenario_integration_dispatch.py`):
  red per Q3: (a) FR-6 leaky-verdict chain → Generator's `validation_findings` scenario-vocabulary-free;
  (b) FR-4 chain arbiter→handler → ScenarioGenerator feedback kwarg carries the delta, key popped;
  (c) YAML step-name contract pin (R/B cycle 1): the arbiter writes the FIXED keys
  `generate_code`/`generate_scenarios` — pin that `new_feature.yaml` and
  `scenario_validation.yaml` name their steps exactly so (sibling of SF-01's reserved-key
  collision pin; a silent rename would strand the verdict feedback).

**Adversarial matrix:** happy = T1a/T2a/T3a/T3b; boundary = T1c retry persistence, T2c
unrelated-keys survival, T3c step-name contract; graceful degradation = T2d malformed findings;
hostile = T1d hostile feedback text (+ FR-6 leaky vocabulary is itself the hostile input on the
arbiter side).

**Accepted risks (R/B dispositions):** prompt-injection via the LLM-authored
`scenario_feedback` into the regeneration prompt is the same pre-existing class flagged at
SF-01 Phase 7.5 — `E-VAL-03` scope (queue Candidate 4), not widened here. The scenario-side
"no source code in feedback" constraint (B-FLOW-01 FR-9) remains prompt-instructed with no
mechanical guard — `B-INTL-07` territory, out of the base contract. Step-name/verdict-key
coupling on the CODING side (`generate_code`) predates this SF and is now pinned by T3c rather
than redesigned.

**Commit boundary CB-1** (single): all tasks + full suite + pre-commit →
`feat(flow): feedback-aware scenario regeneration + opacity seam pins (INT-US-24 SF-02)`.
Direct to main.

## Architecture Verification (Phase 3)

- `scenario_generator.py` change is additive (optional keyword-only param, default None) in
  `workflows/scenarios` — a module `core.flow` already consumes; no reverse dependency.
- `scenario.py` imports `_extract_prompt_feedback` from `generation.py` — same-package import
  already precedented (`_resolve_generation_routing`).
- No new modules, no enum/YAML changes, no sandbox changes; `tach` unaffected.

## Session Handoff

**Current status**: DEV COMPLETE (2026-07-24) — T1–T3 + gap pins G-a/G-b green; full suite
5479 passed / 0 failures; quality gates clean; walkthrough written. As-built: FR-6 landed as
proof-only (no source change needed — the guard was already correct; the seam pin asserts every
SCENARIO_VOCABULARY term absent from the real Generator input).
**Next step**: Phase 8 commit boundary CB-1 (HITL) → then SF-03 impl plan (DAL intake already
RESOLVED to (a)/C-EXEC-07).
