# INT-US-02 SF-01 — Walkthrough

**Commit boundary:** single **CB-1** (direct to `main`) · **Date:** 2026-07-22 · Plan:
[sf01](INT-US-02_sf01_implementation_plan.md) (APPROVED 2026-07-22, Q1–Q4 = a)

Execution discipline honored: minimal AD-6a depth (one JSON context block, no prompt polish),
investment freeze on the E-INTL-02 engine, seam-first tests (survive the D-INTL-07 engine swap).

## Delivered

`sw draft` now runs the whole chain and the review rejection loop is live. Before, it co-authored and
then told the user to run `sw check`; and `new_feature.yaml`'s `loop_back → draft_spec` re-entered a
handler that skipped on an existing spec.

1. **Feedback-aware `DraftSpecHandler` (AD-6a)** — pops this step's loop_back feedback *before* the
   exists-skip (mirroring `generation.py`'s idiom, consumed exactly once). Findings + provider + llm →
   re-draft with the findings as one `reviewer_findings` context block. Findings without a provider →
   **park WITH the findings** (headless contract). No feedback → byte-identical.
2. **3-step `sw draft` pipeline** — `draft_spec → validate_spec (all_passed/abort) → review_spec
   (accepted / loop_back → draft_spec / max_retries=2)`; helpers `_build_draft_pipeline` +
   `_report_draft_chain` (C901).
3. **Inline report** — spec path, rules passed, verdict + findings, non-zero exits. The stale
   *"Run 'sw check'…"* line is gone.
4. **`new_feature.yaml`** — review gate bound 3 → 2 (FR-7).
5. Two existing tests adjusted to the chain: `test_cli_telemetry_flush` now suppresses `typer.Exit` too
   (click's Exit is a RuntimeError subclass, so `suppress(SystemExit)` never caught it; flush intent
   kept). The lineage e2e stubs validate/review — its intent is lineage only (tag + event), and its
   trivial mock spec legitimately fails real S-rules.

## Proof

`test_draft_chain_integration.py` runs the REAL PipelineRunner + GateEvaluator + feedback plumbing:
**reject → loop_back → genuine re-draft (v2 written) → accept**. Rejection-forever is bounded at exactly
3 drafts. A drafter crash mid-re-draft fails loud. A re-drafted spec failing re-validation aborts
mid-loop (C-B corner) — regenerated content cannot skip the battery.

| Level | File | Added |
|---|---|---|
| Unit | `test_draft_handler.py` | +8 (4 feedback-branch seam tests, 4 direct `_pop_feedback` — G2) |
| Unit | `test_pipeline_yaml.py` | +2 (explicit bound; still parses) |
| Integration | `test_cli_review.py` | +6 (pipeline shape + gates, report happy/rejected/abort/hostile, G4 `validate_flow` tripwire) |
| Integration | `test_draft_chain_integration.py` (new) | 5 real-runner scenarios (accept, reject→re-draft→accept, exhausted-bounded, crash-fail-loud, C-B re-validation abort) |

| Check | Result |
|---|---|
| Full suite | unit **4760** · integration **498** · e2e **150** — **5408 passed, 0 failures** |
| Quality | ruff ✅ · mypy ✅ (303) · C901 ✅ · file-size ✅ · tach ✅ · roadmap-sync ✅ (step 5.6's first pre-commit outing) |

Approvals: plan Q1–Q4 all (a), single CB-1. Dev task list approved; Red/Blue folded in R1 (backward
loop_target legality), R2 (loop_back doesn't stamp `attempt` → honest "retries exhausted" phrasing),
R5 (whole-interview re-run on loop accepted as an engine-coupled limitation, D-INTL-07's job), R6 (park
output carries findings). Pre-commit: G2 + G4 approved; the corner push found C-B. No gate bypassed.

## Findings still open

- Whole-interview re-run on each loop (R5) — left to `D-INTL-07`.
