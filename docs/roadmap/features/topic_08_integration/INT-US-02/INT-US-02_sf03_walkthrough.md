# INT-US-02 SF-03 — Walkthrough

**Commit boundary:** single **CB-1** (direct to `main`), committed `e6645a57` · **Date:** 2026-07-23 ·
Plan: [sf03](INT-US-02_sf03_implementation_plan.md) (APPROVED 2026-07-23; Q1–Q3 = a; corner pass added
E6/E7; E1 surface corrected to `sw draft`)

Closes INT-US-02 → **US-2 epic 🟢** (US-21 becomes integration-only). Post-commit: `US-02_integration.md`
status ✅; US-2 → 🟢 in the master roadmap (Verifiable Proof:
`tests/e2e/capabilities/workflows/test_drafter_loop_e2e.py`); US-21 dep box sync; queue update.

## Delivered

The FR-8 proof, `tests/e2e/capabilities/workflows/test_drafter_loop_e2e.py`, drives the REAL CLI
surfaces through co-author → validate → review with a scripted `ContextProvider` (registered through the
SF-02 seam, so the delivered wiring is exercised) and a scripted LLM adapter. Everything else is
genuine: real Drafter, real battery machinery (D-VAL-02 project-local **mechanical-only** preset —
deterministic, zero LLM rules), real reviewer verdict parsing, real gate loop_back, real park/resume
state.

| # | Scenario | Proves |
|---|----------|--------|
| E1 | `sw draft` accept path | The US-2 sentence end-to-end, zero manual steps, stale "sw check" hint gone |
| E2 | DENIED → re-draft → ACCEPTED | The living loop (SF-01 feedback path) on the real chain |
| E3 | headless `sw run new_feature` | Park control: exit 0, nothing drafted, resume hint (NFR-5/6) |
| E4 | DENIED × retries | Bounded loop exhausts → non-zero exit + finding text surfaced |
| E5 | provider crash mid-interview | Loud failure, run not COMPLETED, non-zero |
| E6 | park → manual spec → `sw resume` | Historic manual journey through the NEW chain (draft skips, real validate+review run) |
| E7 | rejection-park → edit → `sw resume` | loop_back rewound state + findings in park output + feedback-consumed-once across sessions |

Five existing defects, fixed in-scope:

1. **D-VAL-02 on the flow-handler SPEC path** — `ValidateSpecHandler` never passed `project_dir` to
   `load_pipeline_yaml`, so project-local overrides were ignored in pipelines (worked only via
   `sw check`). Fixed at 3 call sites.
2. **D-VAL-02 on the flow-handler CODE path** (pre-commit hidden-path sweep) — `ValidateCodeHandler`,
   same bug (`validation.py:315/:317`). Fixed TDD; the 3 `test_handlers_di_payload` pins went red first.
3. **SF-01 report listed no failing rules** — it compared against uppercase `"FAIL"`; `RuleStatus.value`
   is lowercase `"fail"`. Now case-insensitive, pinned by direct report tests on the REAL production
   shape.
4. **Finding texts not exported** by either review handler (`findings_count` only); the inline report
   (FR-6) and loop_back feedback (FR-3) need them. Now `"findings": [f.model_dump() ...]` — full dumps,
   because `sw review` rehydrates `ReviewResult` from step output (a message-only list broke 6 e2e tests).
5. **Rich-markup crash on hostile LLM text** (Phase 7.5 Red/Blue) — the report AND the existing
   `sw review` display (`_display_review_result`) printed LLM/content-derived text unescaped; an
   unmatched closing tag like `[/notatag]` in a finding, summary or rule message raised
   `rich.errors.MarkupError` AFTER a successful run. Fixed with `rich.markup.escape()` on every
   untrusted interpolation.

## Proof

| Tests | Cases |
|---|---|
| e2e scenarios (file above) | 7 |
| G-a: both review handlers' findings-dict output contract | 2 units |
| G-b: direct `_report_draft_chain` units (real lowercase `"fail"`, dict findings, empty/None records, hostile non-dict outputs) | 6 |
| G-c: `project_dir=` passthrough pins on the code path | 3 |
| Red/Blue: hostile markup (report + `sw review` display) | 2 units |

| Check | Result |
|---|---|
| Full suite (after all fixes) | unit 4778 · integration 502 · e2e 157 — **5437 passed, 0 failures** |
| Quality | ruff ✅ · mypy ✅ (303 files) · tach ✅ · file-size 0 errors · roadmap-sync ✅ |

Hidden-path sweep (7 paths), no change needed: API `GET /rules` and `sw config show-profile` load bare
defaults by design (global catalogs, no project context); `generation.py::_extract_prompt_feedback`
reads only `hitl_verdict`/`remarks`/`results`, so the new `findings` key is inert there (available for
future US-3-side rendering); the API review endpoint calls the engine directly; finding dumps are
JSON-safe and bounded in the state DB. Red/Blue also confirmed: a malformed local override now fails
LOUD through the `project_dir` path (correct — D-VAL-02 precedence); e2e fixtures are isolated.

Approvals: plan Q1 = (a) mechanical-only local preset, Q2 = (a) both surfaces, Q3 = (a) via the SF-02
seam; user corner pass added E6/E7 and moved E1 to `sw draft`. Pre-commit: the user's "corner cases?
hidden paths?" sweep found defect #2; G-a + G-b approved. No gate bypassed.

## Findings still open

- **Resume-in-TTY after a rejection-park skips the re-draft** — findings were popped at park time, so
  `sw resume` in a TTY sees an existing spec + no feedback → draft skips → validate + review run on the
  unchanged spec. A second rejection brings fresh findings and the loop **self-heals**. Accepted for the
  base contract (the park message tells the user to edit the spec — the E7 journey).
