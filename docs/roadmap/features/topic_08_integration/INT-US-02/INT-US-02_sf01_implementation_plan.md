# INT-US-02 SF-01 — Draft → Validate → Review Inline Chain

**Status**: APPROVED — approved by Steve Bula on 2026-07-22. Audit Q1–Q4 all resolved to option
**(a)**; single commit boundary **CB-1**. Implemented 2026-07-22. · **FRs owned**: FR-1, FR-2, FR-3,
FR-6, FR-7 · **Depends on**: none · Design: [INT-US-02_design.md](INT-US-02_design.md) §Sub-features →
SF-01

## Goal

Extend `sw draft`'s inline pipeline with `validate_spec` + `review_spec` (gate `accepted`,
`loop_back → draft_spec`, `max_retries: 2`). Make `DraftSpecHandler` **feedback-aware** on the
loop_back path so the rejection loop is real (AD-6 = a). Report the outcome inline and remove the stale
"Run 'sw check'…" message. Make the `new_feature.yaml` review-gate bound explicit (FR-7).

## Where it plugs in

| Fact | Where |
|---|---|
| Feedback plumbing is fully built. `GateEvaluator._handle_loop_back` honors `gate.max_retries` (attempts ≤ bound); the runner calls `inject_feedback`, storing `context.feedback[loop_target] = {"from_step", "findings": result.output}`. | `gates.py:194-…`, `runner.py:448`, `gates.py:144-156` |
| For `loop_target="draft_spec"` the findings dict is `ReviewSpecHandler`'s output (`{verdict, findings…}`). | `review.py:167-168` |
| Consumption pattern to mirror: `generation.py:_extract_prompt_feedback` — `context.feedback.pop(step.name, None)` → use `findings` → cleared, so it never sticks. | `generation.py:75-84` |
| Skip-check to modify: `draft.py` `execute()`'s FIRST branch is `if context.spec_path.exists(): → PASSED (skip)`. `_execute_drafting` builds `Drafter` + `_build_base_prompt(INTERACTIVE)`. `Drafter.draft(name, specs_dir)` writes the same path → natural overwrite; no Drafter change. | `core/flow/handlers/draft.py` |
| `sw draft` today: `PipelineDefinition.create_single_step(name="draft_spec", DRAFT/SPEC)`; last-record-only success check; prints the stale *"Run 'sw check' to validate the drafted spec."*. Settings loaded with `llm_role="draft"`. | `workflows/review/interfaces/cli.py:98-129` |
| `GateDefinition.max_retries` **defaults to 3**. | `models.py:160` |
| Report data: validation output = rule pass/fail counts (S-battery results); review output = `{verdict, findings…}`; retries = `run.step_records[..].attempt`. All in `run_state`. | — |

The steps to add mirror `new_feature.yaml`: `validate_spec` (VALIDATE/SPEC, gate auto `all_passed`,
`on_fail: abort`) and `review_spec` (REVIEW/SPEC, gate auto `accepted`, `on_fail: loop_back →
draft_spec`, `max_retries: 2`). The review step reuses the draft adapter (`new_feature` precedent —
single adapter per run).

External deps: none new. No new module.

## Changes

1. **Feedback-aware `DraftSpecHandler`** (FR-3, AD-6a) · `core/flow/handlers/draft.py` — in
   `execute()`, in order:
   1. Pop loop-back feedback first (mirror `_extract_prompt_feedback`):
      `fb = context.feedback.pop(step.name, None)`.
   2. `fb` has findings AND provider+llm present → **re-draft**: `_execute_drafting` with the findings
      rendered into the base prompt as a labeled context block ("reviewer_findings"); returns the fresh
      spec.
   3. `fb` present, provider/llm missing → **park**, with the findings in the park message (headless).
   4. No feedback → existing behavior byte-identical (exists→skip; provider→draft; else park).

   `_execute_drafting` gains an optional findings param; no `Drafter` signature change.
2. **3-step `sw draft` pipeline** (FR-1, FR-2, FR-3) · `workflows/review/interfaces/cli.py` — replace
   `create_single_step` with a `PipelineDefinition` of `draft_spec` → `validate_spec` → `review_spec`
   and the gates above. Only already-imported symbols (`PipelineDefinition`, `PipelineStep`,
   `StepAction`, `StepTarget`, gate models).
3. **Inline outcome report** (FR-6) · same file — iterate `run_state.step_records`: spec path,
   validation rule counts, review verdict + findings count, retries used. **Delete the "Run 'sw check'…"
   line.** Exit 0 only when the final record PASSED; else non-zero with the findings surfaced
   (retries-exhausted included).
4. **Explicit review-gate bound** (FR-7) · `workflows/pipelines/new_feature.yaml` — `max_retries: 2` on
   the `review_spec` gate; FR-7 correction note in the design.

| File | Change | FR |
|------|--------|----|
| `src/specweaver/core/flow/handlers/draft.py` | feedback-aware re-draft/park (AD-6a) | FR-3 |
| `src/specweaver/workflows/review/interfaces/cli.py` | 3-step pipeline + inline report | FR-1, FR-2, FR-6 |
| `src/specweaver/workflows/pipelines/new_feature.yaml` | explicit `max_retries: 2` | FR-7 |
| `docs/.../INT-US-02_design.md` | FR-7 factual correction note | — |

## Tests

| Tier | Bucket | Case |
|---|---|---|
| Unit — `DraftSpecHandler` feedback branch | Happy | feedback+provider+llm+existing spec → re-drafts (drafter invoked; findings in the built prompt; feedback popped) |
| | Boundary | no feedback + existing spec → skip, byte-identical |
| | Degradation | feedback, no provider/llm → parks with findings in the message |
| | Hostile | malformed feedback (no `findings` key / wrong type) → treated as no-feedback (skip), never crashes; consumed exactly once (second execute sees none) |
| Unit/Integration — `sw draft` pipeline + report | Happy | captured `PipelineDefinition` has the 3 steps and gates (`accepted`, `loop_back→draft_spec`, `max_retries: 2`); accept path reports path + rules + verdict, stale message ABSENT, exit 0 |
| | Degradation | review rejected until exhausted → exit non-zero, findings surfaced |
| | Boundary | validation failure → abort + rule failures reported |
| Integration — real loop (scripted provider + mocked LLM) | Happy | draft→validate→review accepted in one pass |
| | Happy/loop | verdict sequence reject→accept → loop_back → re-draft with findings → accepted; attempt counters correct |
| | Degradation | reject×3 → exhausted, non-zero |
| | Hostile | provider raises mid-redraft → step FAILED surfaced, no silent pass |
| Regression | — | `new_feature.yaml` parses with the explicit bound; existing draft/review unit suites green |

Full e2e with TTY/headless control = SF-03.

## Decisions (audit)

| # | Question | Options | Chosen | Severity |
|---|----------|---------|--------|----------|
| Q1 | Review step's LLM: `sw draft` loads a single adapter with `llm_role="draft"`; the review step would reuse it. | (a) single adapter (new_feature precedent); (b) wire ModelRouter for per-step roles. | **(a)** — precedent; router wiring is an orthogonal enhancement (follow-up). | LOW |
| Q2 | Headless rejection semantics (once SF-02 lands): re-draft needs a provider; without one → park with findings. | (a) park with findings; (b) abort. | **(a)** — parking IS the headless contract (FR-5); resume in a TTY continues the loop. | MEDIUM |
| Q3 | FR-7: default bound is 3, not unbounded. Still set explicit `max_retries: 2`? | (a) yes — parity with INT-US-03 + self-documenting; (b) leave default 3. | **(a)** — one line; makes intent visible. | LOW |
| Q4 | Should `validate_spec` failures also loop back to draft (instead of abort, the new_feature mirror)? | (a) abort, mirror new_feature; (b) loop_back too. | **(a)** — S-rule failures usually need the human's answer content, not a blind re-generation; the semantic-review loop is the focus. Revisit after field use. | MEDIUM |

Architecture check: all changes in already-owned modules with existing imports — `draft.py` (mirrors
generation.py's feedback idiom), the review CLI (flow symbols already imported), one YAML value. **No
new cross-layer edge, no boundary change, no architectural switch** (AD-6a signed off at design).
`tach`/`ruff`/`mypy --strict` stay green. Feedback consumption reuses the `_extract_prompt_feedback`
shape; no parallel mechanism. No CRITICAL violation.

## As built (2026-07-22)

Built under the execution discipline (minimal AD-6a depth, engine freeze, seam-first tests).

| Where | What |
|---|---|
| `core/flow/handlers/draft.py` | `_pop_feedback` (popped exactly once; malformed → treated absent) + feedback branches in `execute`: re-draft via `_execute_drafting(findings=…)` with one JSON `reviewer_findings` context block; headless → park WITH findings. No-feedback paths byte-identical |
| `workflows/review/interfaces/cli.py` | `_build_draft_pipeline` (3 steps, exact gates) + `_report_draft_chain` (inline report, non-zero exits) — helpers extracted for C901 |
| `workflows/pipelines/new_feature.yaml` | review gate bound 3 → 2 |

- The review gate already had an EXPLICIT `max_retries: 3` (not an omitted key); FR-7 tightens 3 → 2
  as approved.
- A re-drafted spec that fails re-validation aborts mid-loop (the C-B corner, added at pre-commit).

Proof and results: [SF-01 walkthrough](INT-US-02_sf01_walkthrough.md).
