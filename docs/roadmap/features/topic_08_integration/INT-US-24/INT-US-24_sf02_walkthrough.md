# INT-US-24 SF-02 — Walkthrough

**Commit boundary:** single **CB-1** (direct to `main`) · **Plan:**
[sf02](INT-US-24_sf02_implementation_plan.md), APPROVED 2026-07-24 (Q1–Q4 as proposed; R/B
corrections: T3c step-name pin, T2d call-site guard, NFR-4 log)

## Delivered

Both arbiter verdict branches now have a consuming party. Replaces a `scenario_error` verdict whose
feedback nobody read — the scenario agent regenerated blind.

| Change | Where | What |
|---|---|---|
| FR-4 producer side | `workflows/scenarios/scenario_generator.py` | `generate_scenarios` gains keyword-only `feedback: str \| None = None`, rendered by `_build_prompt` as a labeled **Prior Verdict Feedback** block before the output-schema instructions. Built once, reused across the JSON-retry loop, so it persists on retries. `None`/`""` ⇒ byte-identical prompt (pinned by equality). |
| FR-4 consumer side | `core/flow/handlers/scenario.py` | `GenerateScenarioHandler` consumes `context.feedback["generate_scenarios"]` via `_extract_prompt_feedback` (pop-once, keyed by step name — the shape the arbiter writes), behind a **call-site guard**: malformed feedback → normal first-pass generation + WARNING, not a crash (the shared helper stays byte-identical for its three coding-side consumers). Regeneration-with-feedback emits an INFO line (NFR-4). |
| FR-6 | — | No source change; a proof obligation — NFR-8 opacity pinned on the real integrated seam. |

## Proof

| Test | Cases |
|---|---|
| `ScenarioGenerator` units | 5 — block placement, byte-identical, retry persistence, hostile text, empty string |
| Handler units | 5 — pop-once + INFO, byte-identical, unrelated-keys survival, malformed-findings guard, dictator-shaped feedback tolerated (the G-b pin: trips if scenario steps ever gain HITL gates, so remarks can't vanish silently) |
| Seam chains (SF-01 dispatch file) | **FR-6** — a LEAKY `code_bug` verdict runs the real arbiter guard, then the real `GenerateCodeHandler`; the `validation_findings` handed to the Generator is free of **every** `SCENARIO_VOCABULARY` term (stronger than the design wording). **FR-4** — real arbiter `scenario_error` → real `GenerateScenarioHandler`; ScenarioGenerator receives `"[FR-1] <delta>"`, key popped. **T3c** — `new_feature.yaml` names `generate_code`, `scenario_validation.yaml` names `generate_scenarios` |
| E2E | none — the CLI journey is SF-03's FR-7 (same scoping the user approved for SF-01) |

| Check | Result |
|---|---|
| Unit / integration / e2e | 4815 · 507 · 157 — **5479 passed, 0 failures** |
| ruff · mypy (303 files) · C901 · file-size · tach · roadmap-sync | ✅ · 0 errors |

## Findings still open

- Prompt injection via the LLM-authored `scenario_feedback` into the regeneration prompt:
  pre-existing class (`E-VAL-03` scope), not widened. Accepted.
- Consume-on-malformed asymmetry (handler consumes a broken shape; arbiter retains on error): safe —
  the arbiter re-publishes fresh `generate_scenarios` feedback on every `scenario_error` round
  (plan Q4).
- Broad `except` in the call-site guard: logs with `exc_info`, scoped to the extraction call. LOW,
  accepted.

R/B converged after 2 cycles, no fix-required findings. Minted in the same session (`37cf5fb9`):
`C-EXEC-07` + `INT-US-09-SF06` (DAL-escalated isolation for pipeline runs — the user's "would a PO
be happy?" question), and one INT sub-story per add-on group (`INT-US-01-SF05`, `INT-US-03-SF03`,
`INT-US-04-SF10`).
