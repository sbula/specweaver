# Implementation Plan: Interactive Drafter Integration — SF-01: Draft → Validate → Review Inline Chain

- **Feature ID**: INT-US-02
- **Sub-Feature**: SF-01 — Draft → Validate → Review Inline Chain
- **Design Document**: docs/roadmap/features/topic_08_integration/INT-US-02/INT-US-02_design.md
- **Design Section**: §Sub-Feature Breakdown → SF-01
- **Implementation Plan**: docs/roadmap/features/topic_08_integration/INT-US-02/INT-US-02_sf01_implementation_plan.md
- **Status**: APPROVED — approved by Steve Bula on 2026-07-22. Audit Q1–Q4 all resolved to option **(a)**; single commit boundary **CB-1**.

## Scope (from the Design Document)
Extend `sw draft`'s inline pipeline with `validate_spec` + `review_spec` (gate `accepted`,
`loop_back → draft_spec`, `max_retries: 2`); make `DraftSpecHandler` **feedback-aware** on the loop_back
path so the rejection loop is real (AD-6 = a, approved); inline outcome report; remove the stale
"Run 'sw check'…" message; make the `new_feature.yaml` review-gate bound explicit (FR-7, corrected — see
Research Note 5). **FRs owned: FR-1, FR-2, FR-3, FR-6, FR-7.**

## Research Notes (Phase 0)

1. **Feedback plumbing is fully built** — `GateEvaluator._handle_loop_back` (`gates.py:194-…`) honors
   `gate.max_retries` (attempts ≤ bound) and the runner calls `inject_feedback` (`runner.py:448`,
   `gates.py:144-156`), storing `context.feedback[loop_target] = {"from_step", "findings": result.output}`.
   For `loop_target="draft_spec"` the findings dict is `ReviewSpecHandler`'s output
   (`review.py:167-168`: `{verdict, findings…}`).
2. **The consumption pattern to mirror** — `generation.py:_extract_prompt_feedback` (`:75-84`):
   `context.feedback.pop(step.name, None)` → use `findings` → cleared so it never sticks. The
   `DraftSpecHandler` change copies this shape exactly.
3. **The skip-check to modify** — `draft.py` `execute()`: the FIRST branch is
   `if context.spec_path.exists(): → PASSED (skip)`. AD-6(a): pop step-feedback BEFORE this check; when
   findings are present (and provider+llm available) → re-draft via the existing `_execute_drafting`
   (which builds `Drafter` + `_build_base_prompt(INTERACTIVE)`); the reviewer findings are added to the
   base prompt as a context block. `Drafter.draft(name, specs_dir)` writes the same path → natural
   overwrite; no Drafter change needed. Feedback present but NO provider/llm → **park with findings**
   (headless rejection semantics, consistent with the existing park path).
4. **`sw draft` current shape** — `workflows/review/interfaces/cli.py:98-129`:
   `PipelineDefinition.create_single_step(name="draft_spec", DRAFT/SPEC)`; last-record-only success check;
   prints the stale *"Run 'sw check' to validate the drafted spec."*. Steps to add mirror
   `new_feature.yaml`: `validate_spec` (VALIDATE/SPEC, gate auto `all_passed`, `on_fail: abort`) and
   `review_spec` (REVIEW/SPEC, gate auto `accepted`, `on_fail: loop_back → draft_spec`, `max_retries: 2`).
   Settings already loaded with `llm_role="draft"`; the review step reuses the same adapter
   (`new_feature` precedent — single adapter per run).
5. **Design correction (FR-7):** `GateDefinition.max_retries` **defaults to 3** (`models.py:160`) — the
   shipped `new_feature` review loop was *bounded-but-DEAD* (the skip defect), not unbounded as the design
   stated. FR-7 therefore shrinks to: set an **explicit `max_retries: 2`** on that gate for parity with
   `INT-US-03`'s bound and self-documentation. The dead-loop defect (the real one) is fixed by Change 1.
6. **Report data available inline** — validation output: rule pass/fail counts (S-battery results);
   review output: `{verdict, findings…}`; retries: `run.step_records[..].attempt`. All in `run_state`.

### External deps: none new. No new module.

## Implementation Approach
> Pseudocode / ordered steps only.

### Change 1 — Feedback-aware `DraftSpecHandler` (FR-3, AD-6a) · `core/flow/handlers/draft.py`
In `execute()`, ordered:
1. Pop loop-back feedback first (mirror `_extract_prompt_feedback`): `fb = context.feedback.pop(step.name, None)`.
2. If `fb` has findings AND provider+llm present → **re-draft path**: `_execute_drafting` with the findings
   rendered into the base prompt (a labeled context block, e.g. "reviewer_findings"); returns the fresh spec.
3. If `fb` present but provider/llm missing → **park**, surfacing the findings in the park message (headless).
4. No feedback → existing behavior byte-identical (exists→skip; provider→draft; else park).
`_execute_drafting` gains an optional findings param (or reads them from a small argument) — smallest seam
chosen at dev time; no `Drafter` signature change.

### Change 2 — Extend the `sw draft` inline pipeline (FR-1, FR-2, FR-3) · `workflows/review/interfaces/cli.py`
Replace `create_single_step` with a 3-step `PipelineDefinition` (`draft_spec` → `validate_spec` →
`review_spec`) with the gates from Research Note 4. Only already-imported symbols (`PipelineDefinition`,
`PipelineStep`, `StepAction`, `StepTarget`, gate models).

### Change 3 — Inline outcome report (FR-6) · same file
Replace the last-record-only block: iterate `run_state.step_records` → report spec path, validation rule
counts, review verdict + findings count, retries used; **delete the "Run 'sw check'…" line**; exit 0 only
when the final record PASSED, else non-zero with the findings surfaced (retries-exhausted case included).

### Change 4 — Explicit review-gate bound (FR-7 corrected) · `workflows/pipelines/new_feature.yaml`
Add `max_retries: 2` to the `review_spec` gate. Also correct the design doc's "unbounded" claim (note,
dated — in-progress doc, not a finished story).

### Files to modify
| File | Change | FR |
|------|--------|----|
| `src/specweaver/core/flow/handlers/draft.py` | feedback-aware re-draft/park (AD-6a) | FR-3 |
| `src/specweaver/workflows/review/interfaces/cli.py` | 3-step pipeline + inline report | FR-1, FR-2, FR-6 |
| `src/specweaver/workflows/pipelines/new_feature.yaml` | explicit `max_retries: 2` | FR-7 |
| `docs/.../INT-US-02_design.md` | FR-7 factual correction note | — |
| `tests/...` | see Test Plan | all |

## Test Plan (4 Adversarial Buckets)

**Unit — `DraftSpecHandler` feedback branch (direct):** [Happy] feedback+provider+llm+existing spec →
re-drafts (drafter invoked; findings present in the built prompt; feedback popped); [Boundary] no feedback +
existing spec → skip, byte-identical; [Degradation] feedback but no provider/llm → parks with findings in
the message; [Hostile] malformed feedback (no `findings` key / wrong type) → treated as no-feedback (skip),
never crashes; feedback is consumed exactly once (second execute sees none).

**Unit/Integration — `sw draft` pipeline + report:** [Happy] captured `PipelineDefinition` has the 3 steps
with the specified gates (`accepted`, `loop_back→draft_spec`, `max_retries: 2`); accept-path report shows
path + rules + verdict, stale message ABSENT, exit 0; [Degradation] review rejected until exhausted → exit
non-zero, findings surfaced; [Boundary] validation failure → abort + rule failures reported.

**Integration — the real loop (scripted provider + mocked LLM):** [Happy] draft→validate→review accepted in
one pass; [Happy/loop] review rejects once (mock verdict sequence reject→accept) → loop_back → re-draft ran
with findings → accepted; attempt counters correct; [Degradation] reject×3 → exhausted, non-zero;
[Hostile] provider raises mid-redraft → step FAILED surfaced, no silent pass. (Full e2e incl. TTY/headless
control = SF-03.)

**Regression:** `new_feature.yaml` still parses + gate bound explicit; existing draft/review unit suites green.

## Audit (Phase 2) — resolved at Phase 4 HITL (2026-07-22): Q1–Q4 all option (a)
| # | Question | Options | Proposal | Severity |
|---|----------|---------|----------|----------|
| Q1 | Review step's LLM: `sw draft` loads a single adapter with `llm_role="draft"`; the review step would reuse it. | (a) single adapter (new_feature precedent) [rec]; (b) wire ModelRouter for per-step roles. | **(a)** — precedent; router wiring is an orthogonal enhancement (note as follow-up). | LOW |
| Q2 | Headless rejection semantics (matters once SF-02 lands): feedback-aware re-draft needs a provider; without one → park with findings. | (a) park with findings [rec]; (b) abort. | **(a)** — parking IS the headless contract (FR-5); resume in a TTY continues the loop. | MEDIUM |
| Q3 | FR-7 correction: default bound is 3, not unbounded. Still set explicit `max_retries: 2`? | (a) yes — parity with INT-US-03 + self-documenting [rec]; (b) leave default 3. | **(a)** — one line; makes intent visible. | LOW |
| Q4 | Should `validate_spec` failures also loop back to draft (instead of abort, the new_feature mirror)? | (a) abort, mirror new_feature [rec]; (b) loop_back too. | **(a)** — S-rule failures usually need the human's answer content, not a blind re-generation; the semantic-review loop is the contract's focus. Revisit after field use. | MEDIUM |

## Architecture Verification (Phase 3)
- All changes in already-owned modules with existing imports: `draft.py` (handler, mirrors generation.py's
  feedback idiom), review CLI (flow symbols already imported), one YAML value. **No new cross-layer edge, no
  boundary change, no architectural switch** (AD-6a sign-off already obtained at design approval).
  `tach`/`ruff`/`mypy --strict` stay green.
- **Zoom-out/duplication:** feedback consumption reuses the established `_extract_prompt_feedback` shape —
  consider extracting a tiny shared helper if identical (dev-time call); no parallel mechanisms introduced.
- **Verdict:** no CRITICAL violation.

## Implementation Notes (as-built, 2026-07-22)

Delivered as planned under the execution discipline (minimal AD-6a depth, engine freeze, seam-first tests):
- `core/flow/handlers/draft.py` — `_pop_feedback` (popped exactly once; malformed → treated absent) +
  feedback branches in `execute` (re-draft via `_execute_drafting(findings=…)`, one JSON
  `reviewer_findings` context block; headless → park WITH findings) — no-feedback paths byte-identical.
- `workflows/review/interfaces/cli.py` — `_build_draft_pipeline` (3 steps, exact gates) +
  `_report_draft_chain` (inline report; stale "Run 'sw check'…" removed; non-zero exits) — extracted as
  helpers for C901.
- `workflows/pipelines/new_feature.yaml` — review gate bound 3 → 2.

**Corrections & findings during dev:** (1) the review gate had an EXPLICIT `max_retries: 3` (Research
Note 5's "omitted key / default 3" was wrong — value right, mechanism wrong; my grep window cut the line);
FR-7 = tighten 3→2 as approved. (2) Fixed two inherited tests exposed by the chain:
`test_cli_telemetry_flush` (its `suppress(SystemExit)` never caught `typer.Exit`) and the lineage e2e
(now stubs validate/review — its intent is lineage only; the chain is proven in
`test_draft_chain_integration.py`). (3) Pre-commit HITL added the **C-B corner**: a re-drafted spec
failing re-validation aborts mid-loop (proven).

Tests: handler unit +8 (feedback branches + G2 direct), cli integration +6 (shape/report/G4),
`test_draft_chain_integration.py` (5 real-runner scenarios incl. C-B), yaml +2. Full suite:
unit 4760 · integration 498 · e2e 150 (5408 passed, 0 failures). ruff/mypy(303)/C901/tach/file-size/
roadmap-sync all clean.

**The headline proof:** the shipped-dead rejection loop is ALIVE — reject → loop_back → real re-draft
(v2) → accept, bounded at exactly 3 drafts, through the real runner + gates + feedback plumbing.

## Session Handoff
**Current status**: DEV COMPLETE (2026-07-22) — pre-commit phases 1–5 green; walkthrough + commit boundary next.
**Next step**: CB-1 commit, then SF-02 (provider wiring) → SF-03 (proof) closes the contract.
