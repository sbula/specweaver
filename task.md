# INT-US-04 SF-01 — CB-1: stop dropping `Finding`

**Plan**: `docs/roadmap/features/topic_08_integration/INT-US-04/INT-US-04_sf01_implementation_plan.md` (APPROVED)
**FR**: FR-1 — extract validation findings into `StepResult.output` **without loss**
**Tier**: unit (one module's behaviour, no seam)

## Context

`handlers/validation.py` builds the same payload at **:108** (`ValidateSpecHandler`) and **:245**
(`ValidateCodeHandler`) — byte-identical comprehensions keeping `rule_id`/`status`/`message` and
dropping `Finding` entirely. `Finding` carries `message`, `line`, `severity`, `suggestion`
(`assurance/validation/models.py:39-45`); line numbers, severities and suggestions are computed by
the rules and thrown away at this boundary.

Two call sites, one shape → the widening goes in a **shared helper** (DRY), not twice.

## Tasks

- [x] **T1** — `_rule_payload(results)` helper carrying each rule's full `Finding` list; both
      handlers call it.
      - src: `src/specweaver/core/flow/handlers/validation.py`
      - test: `tests/unit/core/flow/handlers/test_validate_spec_findings.py` `[NEW]`
- [x] **T2** — Measure the `step_records` blob-size delta on a real run; record it in the plan.
      - doc: `INT-US-04_sf01_implementation_plan.md`
      - **Blocks the boundary if unrecorded** (plan CB-1 done-when 2, RB-6).

## Adversarial test matrix (mandatory, 4 buckets)

| Bucket | Test |
|---|---|
| **Happy path** | A rule with two findings → payload carries `message`, `line`, `severity`, `suggestion` for each, in order |
| **Boundary/edge** | Rule with **zero** findings → `findings: []` present, not absent. A finding with `line=None` and `suggestion=None` (both optional) → keys present, values `None`. A rule that PASSED still gets a `findings` key |
| **Graceful degradation** | The widened payload survives `json.dumps(..., default=str)` — the exact semantics `StateStore` persists with (plan R-7). `Severity` is a `StrEnum` and must not serialize as `"Severity.ERROR"` |
| **Hostile/wrong input** | Finding `message` carrying quotes, newlines and a 10k-char body — it derives from spec content, which is user input — survives the round trip unmangled |

## Red/Blue on this task list

| # | Finding | Resolution |
|---|---|---|
| RT-1 | The `json.dumps(default=str)` test is near-vacuous if the helper already emits `str` — it would be testing stdlib | Sharpened: assert the serialized text contains `"error"` and **not** `"Severity.ERROR"`. That tests *our* choice to emit `.value`, which is the thing that can go wrong |
| RT-2 | **Wiring only one call site still passes every helper test.** The plan names both :108 and :245 | Added a test that drives **`ValidateCodeHandler`** as well, not just the helper and the spec handler |
| RT-3 | The done-when mutant (*drop the `findings` key*) does not catch a **partial** loss, and FR-1 says *without loss* | Second mutant added: drop `suggestion` from the per-finding dict. If nothing dies, the happy-path test is not asserting the fields it claims |
| RT-4 | T2 said "measure on a real run" with no method — an unreproducible number | Method pinned below |
| RT-5 | Does widening break existing assertions? | **Checked, no.** Every existing assertion on this payload is additive-safe: `len(output["results"]) > 0`, lookup by `rule_id`, and a `rule_id` list comprehension. No exact-equality assertion exists on either handler's output |
| RT-6 | Naming collision: `inject_feedback` already stores the whole step output under a key called `"findings"`, so a rule's own list nests as `feedback[step]["findings"]["results"][0]["findings"]` | Keep `findings` — it is the domain term (`Finding`, DDD ubiquitous language, and the term FR-1 uses). The **outer** key is `inject_feedback`'s misnomer and is not this boundary's to rename. Noted so the nesting is not mistaken for a bug |

### T2 measurement method (pinned, RT-4)

Same spec, same pipeline, before and after the change: run the validate flow and compare
`len(json.dumps([r.model_dump() for r in run.step_records], default=str))` — the exact expression
`StateStore.save_run` uses (`store.py:175`). Record absolute bytes before, after, and the
percentage, plus the rule/finding counts that produced them, so the number is reproducible rather
than anecdotal.

## Pre-commit gate

- [x] Phase 1 — architecture (A-1..A-4; A-2 recorded, left by user decision)
- [x] Phase 2 — test gap (HITL: U-1, U-2 approved; A-2 deferred)
- [x] Phase 3 — U-1 and U-2 implemented, both probed KILLED
- [x] Phase 4 — full suite
- [x] Phase 5 — code quality
- [x] Phase 6 — documentation
- [x] Phase 7 — walkthrough
- [x] Phase 7.5 — Red/Blue on the code changes

## Commit boundary

CB-1 of 4. **Done when:**
1. The mutant *"drop the `findings` key from the payload builder"* is **KILLED**.
2. T2's measurement is recorded in the plan.
3. `python scripts/tests.py cb INT-US-04` green, pre-commit skill passed, HITL commit gate.
