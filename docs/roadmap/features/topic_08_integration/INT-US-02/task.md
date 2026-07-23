# Task List — INT-US-02 SF-02: Composition-Root Provider Wiring (SF-01 record: git history + walkthrough)

- **Impl Plan**: docs/roadmap/features/topic_08_integration/INT-US-02/INT-US-02_sf01_implementation_plan.md
- **FRs**: FR-1 (validate in-pipeline), FR-2 (review in-pipeline), FR-3 (bounded REAL loop), FR-6 (report), FR-7 (explicit bound)
- **Commit boundary**: single **CB-1**.
- **Execution discipline (binding, from design handoff)**: minimal depth on AD-6a plumbing; investment freeze
  on the E-INTL-02 engine (no SPEC_SECTIONS tuning / Drafter refactors); seam-first tests.

## Tasks

- [x] **T1 — Feedback-aware `DraftSpecHandler`** (FR-3, AD-6a)
  - src: `core/flow/handlers/draft.py` — pop `context.feedback[step.name]` BEFORE the exists-skip
    (mirror `generation.py:_extract_prompt_feedback`); findings+provider+llm → re-draft via
    `_execute_drafting(findings=…)` (findings as one `add_context(json.dumps(findings), "reviewer_findings")`
    block — smallest seam, no prompt polish); findings without provider/llm → park WITH findings in the park
    output; no feedback → byte-identical.
  - test: `tests/unit/core/flow/handlers/test_draft_handler.py` (extend) — seam-first: [Happy] feedback+
    provider+llm+existing spec → `_execute_drafting` invoked with findings, feedback consumed exactly once;
    [Boundary] no feedback + exists → skip unchanged; [Degradation] feedback, no provider → parks, findings in
    park output; [Hostile] malformed feedback (no `findings`/wrong type) → treated as absent, no crash.

- [x] **T2 — 3-step inline pipeline + explicit yaml bound** (FR-1, FR-2, FR-3, FR-7)
  - src: `workflows/review/interfaces/cli.py` — replace `create_single_step` with
    `PipelineDefinition(name="draft_spec", steps=[draft_spec, validate_spec(auto/all_passed/abort),
    review_spec(auto/accepted/loop_back→draft_spec, max_retries=2)])`; `workflows/pipelines/new_feature.yaml`
    — add `max_retries: 2` to the review_spec gate.
  - test: `tests/integration/interfaces/cli/test_cli_review.py` (extend) — captured PipelineDefinition has 3
    steps + exact gates (mock PipelineRunner); `new_feature.yaml` parses with explicit bound (unit).
  - note: loop_target `draft_spec` is BACKWARD from step 2 → passes `validate_flow()`.

- [x] **T3 — Inline outcome report** (FR-6)
  - src: same cli — iterate step_records: spec path, validation rule counts, review verdict + findings count;
    "review rejected (retries exhausted)" phrasing on loop-exhausted failure (attempt counters are not
    persisted for loop_back — derive from the gate bound we own); REMOVE the stale "Run 'sw check'…" line;
    exit 0 only if final record PASSED.
  - test: cli integration — accept path shows all three outcomes + stale message ABSENT + exit 0;
    rejected-exhausted → non-zero + findings surfaced; validation-abort → rule failures reported.

- [x] **T4 — Integration: the real loop** (FR-3 end-to-end at integration level)
  - test: new `tests/integration/workflows/review/test_draft_chain_integration.py` — real PipelineRunner +
    real gates, scripted ContextProvider + mocked LLM: [Happy] accept in one pass; [Happy/loop] reject→accept:
    loop_back re-enters draft, re-draft RAN (drafter called 2nd time), spec regenerated, then accepted;
    [Degradation] reject×3 → exhausted → run failed; [Hostile] provider raises mid-redraft → step FAILED
    surfaced. (Full e2e + TTY/headless control = SF-03.)

- [x] **T5 — Full suite + pre-commit gate (CB-1)**
  - Full unit/integration/e2e; fix any regression project-wide. Pre-commit skill. HITL commit stop.

## Adversarial Test Matrix (per task — 4 buckets)
| Task | Happy | Boundary/Edge | Graceful Degradation | Hostile/Wrong Input |
|------|-------|---------------|----------------------|---------------------|
| T1 | feedback→re-draft, consumed once | no feedback→skip byte-identical | no provider→park WITH findings | malformed feedback→treated absent |
| T2 | 3 steps + exact gates | loop_target backward (validate_flow OK) | yaml parses w/ bound | — (declarative) |
| T3 | full report, stale line gone | validation-abort report | exhausted→non-zero+findings | missing outputs→report degrades, no crash |
| T4 | one-pass accept | reject→accept loop (re-draft proven) | reject×3 exhausted | provider raises mid-redraft |

## Progress
- Phase 2 (task breakdown): approved (Red/Blue R1/R2/R5/R6 folded in).
- T1–T4 done (TDD). Findings during dev: new_feature review gate had EXPLICIT max_retries: 3 (not
  default-omitted as researched) → tightened to 2 per approved FR-7; fixed inherited test issues
  (telemetry-flush suppress didn't catch typer.Exit; lineage e2e now stubs downstream handlers —
  its intent is lineage only, the chain is proven in test_draft_chain_integration.py).
- Full suite (Step A): unit 4756 · integration 496 · e2e 150 (5402 passed, 0 failures).
- Pre-commit gate (Step B): _running_.
  - Phase 1 (architecture): [x] ✅ no violations (tach clean; no new cross-layer edge).
  - Phase 2 (test gap): [x] combined analysis; user approved G2 + G4 + pushed the C-B corner.
  - Phase 3 (implement tests): [x] G2 (4 direct _pop_feedback), G4 (validate_flow tripwire), C-B
    (re-drafted spec failing re-validation aborts mid-loop). ruff clean.
  - Phase 4 (full suite): [x] unit 4760 · integration 498 · e2e 150 (5408 passed, 0 failures).
  - Phase 5 (code quality): [x] ruff, mypy (303), C901, file-size, tach, roadmap-sync — all clean.
  - Phase 6 (docs): [x] user guide 2_drafting (one-command loop), impl-plan as-built, design tracker Dev ✅.
  - Phase 7 (walkthrough): [x] INT-US-02_sf01_walkthrough.md.
  - Phase 7.5 (Red/Blue on code): [x] no criticals (feedback-key consistency ✓; human-gated park/resume
    cycle accepted; findings-injection within TECH-007 posture).
  - Phase 8 (commit boundary): ✅ committed (direct to master, 2026-07-22). SF-01 tracker Pre-Commit ✅ + Committed ✅.
