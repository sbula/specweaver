# Walkthrough — INT-US-02 SF-01: Draft → Validate → Review Inline Chain

- **Commit boundary**: single **CB-1** (direct to `main`).
- **Impl plan**: `INT-US-02_sf01_implementation_plan.md` (APPROVED 2026-07-22, Q1–Q4 = a).
- **Execution discipline honored**: minimal AD-6a depth (one JSON context block, no prompt polish),
  investment freeze on the E-INTL-02 engine, seam-first tests (survive the D-INTL-07 engine swap).

## What changed and why

`sw draft` co-authored a spec, then told the user to *"Run 'sw check' manually"* — and `new_feature.yaml`'s
review rejection loop had **always been dead** (`DraftSpecHandler` skips when the spec exists, so
`loop_back → draft_spec` re-entered a no-op). SF-01 joins the chain and brings the loop to life:

1. **Feedback-aware `DraftSpecHandler` (AD-6a)** — pops this step's loop_back feedback *before* the
   exists-skip (mirroring `generation.py`'s idiom, consumed exactly once): findings + provider + llm →
   re-draft with the reviewer findings injected as one `reviewer_findings` context block; findings without
   a provider → **park WITH the findings** (headless contract); no feedback → byte-identical behavior.
2. **`sw draft` 3-step inline pipeline** — `draft_spec → validate_spec (all_passed/abort) → review_spec
   (accepted / loop_back → draft_spec / max_retries=2)`; helpers `_build_draft_pipeline` +
   `_report_draft_chain` (C901).
3. **Inline outcome report** — spec path, rules passed, verdict + findings, non-zero exits; the stale
   *"Run 'sw check'…"* line is deleted.
4. **`new_feature.yaml`** — review gate bound tightened 3 → 2 (FR-7 as approved).

## The headline proof

`test_draft_chain_integration.py` runs the REAL PipelineRunner + GateEvaluator + feedback plumbing:
**reject → loop_back → a genuine re-draft (v2 written) → accept**; rejection-forever is bounded at exactly
3 drafts; a drafter crash mid-re-draft fails loud; and (C-B corner, added at the pre-commit HITL) a
re-drafted spec that fails re-validation aborts mid-loop — regenerated content cannot skip the battery.

## Tests

| Level | File | Added |
|---|---|---|
| Unit | `test_draft_handler.py` | +8 (4 feedback-branch seam tests, 4 direct `_pop_feedback` — G2) |
| Unit | `test_pipeline_yaml.py` | +2 (explicit bound; still parses) |
| Integration | `test_cli_review.py` | +6 (pipeline shape + gates, report happy/rejected/abort/hostile, G4 `validate_flow` tripwire) |
| Integration | `test_draft_chain_integration.py` (new) | 5 real-runner scenarios (accept, reject→re-draft→accept, exhausted-bounded, crash-fail-loud, C-B re-validation abort) |

**Full suite (Phase 4, re-run):** unit **4760** · integration **498** · e2e **150** — **5408 passed, 0
failures**. **Quality (Phase 5):** ruff ✅ · mypy ✅ (303) · C901 ✅ · file-size ✅ · tach ✅ · roadmap-sync ✅
(step 5.6's first pre-commit outing).

## HITL gate decisions
- Impl-plan Phase 4: Q1–Q4 all (a); single CB-1.
- Dev Phase 2: task list approved; Red/Blue R1 (backward loop_target legality), R2 (loop_back doesn't stamp
  `attempt` → honest "retries exhausted" phrasing), R5 (whole-interview re-run on loop accepted as
  engine-coupled limitation, D-INTL-07's job), R6 (park output carries findings) folded in.
- Pre-commit Phase 2/3: user approved G2 + G4 and pushed for corners → **C-B found and covered**.
- No gate bypassed.

## Corrections & inherited fixes (reported faithfully)
- Research Note 5 was wrong about the *mechanism*: the review gate had an EXPLICIT `max_retries: 3`
  (my grep window cut the line), not an omitted key. Value story unchanged; FR-7 = tighten 3→2.
- `test_cli_telemetry_flush` draft test: its `suppress(SystemExit)` never caught `typer.Exit`
  (click's Exit is a RuntimeError subclass) — fixed to suppress both; flush intent preserved.
- Lineage e2e now stubs validate/review handlers: its intent is lineage only (tag + event); the trivial
  mock spec content legitimately fails real S-rules; the chain is proven in the dedicated integration file.

## Deferred by design
- FR-8 e2e proof + headless park control → SF-03 (needs SF-02's TTY-gating first).
- Provider wiring at `sw run`/`resume` → SF-02 (engine-neutral factory shape per the discipline note).
