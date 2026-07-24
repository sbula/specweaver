# Walkthrough — INT-US-24 SF-02: Close the Feedback Loop

- **Commit boundary**: single **CB-1** (direct to `main`). Impl plan APPROVED 2026-07-24
  (Q1–Q4 as proposed; R/B corrections: T3c step-name pin, T2d call-site guard, NFR-4 log).
- Second bite of INT-US-24: both arbiter verdict branches now have a consuming party.

## What changed and why

After SF-01, a `scenario_error` verdict wrote feedback nobody read — the scenario agent
regenerated blind, making the arbiter's scenario-side judgment decorative. Two additive changes
close the loop:

1. **FR-4 producer-side (`workflows/scenarios/scenario_generator.py`)** —
   `generate_scenarios` gains keyword-only `feedback: str | None = None`, rendered by
   `_build_prompt` as a labeled **Prior Verdict Feedback** block placed before the output-schema
   instructions. The prompt is built once and reused across the JSON-retry loop, so the block
   persists on retries structurally. `None`/`""` ⇒ byte-identical prompt (pinned by equality).
2. **FR-4 consumer-side (`core/flow/handlers/scenario.py`)** — `GenerateScenarioHandler`
   consumes `context.feedback["generate_scenarios"]` via the shared `_extract_prompt_feedback`
   contract (pop-once, keyed by step name — the exact shape the arbiter already writes), behind a
   **call-site guard**: malformed feedback degrades to a normal first-pass generation with a
   WARNING instead of crashing the pipeline (the shared helper stays byte-identical for its three
   coding-side consumers). Regeneration-with-feedback emits an INFO line (NFR-4).

**FR-6** needed no source change — it is a *proof* obligation: NFR-8 opacity pinned on the real
integrated seam, not just the guard's unit tests.

## Tests

- Unit: 5 `ScenarioGenerator` feedback tests (block placement/byte-identical/retry-persistence/
  hostile-text/empty-string) · 5 handler consumption tests (pop-once + INFO, byte-identical,
  unrelated-keys survival, malformed-findings guard, dictator-shaped feedback tolerated — the
  G-b pin that trips if scenario steps ever gain HITL gates so remarks can't vanish silently).
- Integration (seam chains, extending the SF-01 dispatch file): **FR-6** — a LEAKY `code_bug`
  LLM verdict runs the real arbiter guard, then the real `GenerateCodeHandler`; the captured
  `validation_findings` handed to the Generator is asserted free of **every**
  `SCENARIO_VOCABULARY` term (strictly stronger than the design wording). **FR-4** — real
  arbiter `scenario_error` → real `GenerateScenarioHandler`; the ScenarioGenerator receives
  `"[FR-1] <delta>"` and the key is popped. **T3c** — YAML step-name contract pin:
  `new_feature.yaml` must name `generate_code` and `scenario_validation.yaml` must name
  `generate_scenarios` (the fixed keys the arbiter writes; a silent rename would strand verdict
  feedback with no error anywhere).
- E2E: deliberately none — the CLI journey is SF-03's FR-7 (same scoping the user approved for
  SF-01).

**Full suite (pre-commit Phase 4, re-run from scratch):** unit 4815 · integration 507 · e2e 157 —
**5479 passed, 0 failures.**
**Quality:** ruff ✅ · mypy ✅ (303 files) · C901 ✅ · file-size 0 errors · tach ✅ · roadmap-sync ✅.

## Red/Blue (Phase 7.5) — findings & dispositions

- Prompt-injection via the LLM-authored `scenario_feedback` into the regeneration prompt:
  pre-existing class (`E-VAL-03` scope, flagged identically at SF-01 7.5), not widened. Accepted.
- Consume-on-malformed asymmetry (handler consumes even when the shape is broken, vs the
  arbiter's retain-on-error): safe by construction — the arbiter re-publishes fresh
  `generate_scenarios` feedback on every `scenario_error` round; documented in plan Q4.
- Broad `except` in the call-site guard: logs with `exc_info` (observable), scoped to the
  extraction call only. LOW, accepted.
- No fix-required findings; converged after 2 cycles.

## Session context

Minted alongside this SF (same session, commit `37cf5fb9`): `C-EXEC-07` + `INT-US-09-SF06`
(DAL-escalated isolation for pipeline runs — the user's "would a PO be happy?" question), and the
audit giving every add-on group its own INT sub-story (`INT-US-01-SF05`, `INT-US-03-SF03`,
`INT-US-04-SF10`). The INT-US-24 SF-03 DAL intake decision is RESOLVED to (a) — posture
documented, escalation delegated to `C-EXEC-07`.
