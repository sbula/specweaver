# Task List — INT-US-02 SF-03: Verifiable Proof (SF-01/SF-02 records: git history + walkthroughs)

- **Impl Plan**: docs/roadmap/features/topic_08_integration/INT-US-02/INT-US-02_sf03_implementation_plan.md
- **FRs**: FR-8 (multi-scenario e2e proof of the full co-author → validate → review loop) + NFR-5/NFR-6
  (headless park control)
- **Commit boundary**: single **CB-1** — closes INT-US-02 → US-2 epic 🟢 (US-21 becomes integration-only).

## Tasks (SF-03)

- [x] **T1 — shared fixtures**: ScriptedProvider (deterministic answers, `fail_after` option, real
  `ContextProvider` subclass), ScriptedAdapter (verdict queue on "VERDICT" prompts, section bodies
  otherwise — S06 needs the fenced code block), `_mechanical_preset()` (D-VAL-02 project-local
  mechanical-only battery: S01/S02/S06/S09/S10/S08), seam registration + reset fixture,
  `_POST_REVIEW_STUBS` (US-3 steps out-of-contract boundary).
- [x] **T2 — E1/E2 happy + loop**: `sw draft` full-real accept; DENIED→re-draft→ACCEPTED loop.
- [x] **T3 — E3/E4/E5 controls**: headless park exit 0; retries exhausted (non-zero + finding text);
  provider crash mid-interview (loud failure).
- [x] **T4 — E6/E7 cross-session journeys**: park→manual-spec→resume; rejection-park (findings in park
  output)→edit→resume→accept (state DB via `state_db_path` + `SW_PROJECT`).
- [x] **T5 — inherited defects flushed by the proof (fix-inherited rule)**:
  1. `validation.py` ValidateSpecHandler loader missing `project_dir` → D-VAL-02 local overrides dead
     on the flow-handler spec path → fixed.
  2. SF-01 report compared rule status against uppercase `"FAIL"`; production emits lowercase → report
     never listed failing rules → case-insensitive.
  3. Both review handlers exported only `findings_count`, never the finding texts → now
     `"findings": [f.model_dump() ...]` (model_dump — `sw review` rehydrates ReviewResult from output).

## Pre-Commit Gate (CB-1)

- [x] Phase 1 — architecture: test-only + in-scope defect fixes; tach ✅ (no new imports/boundaries).
- [x] Phase 2 — test gap analysis: presented G-a/G-b; user demanded hidden-path sweep → **found defect
  #4: ValidateCodeHandler's loader ALSO missing `project_dir`** (validation.py:315/:317 — D-VAL-02 dead
  for CODE validation via pipelines). Fixed TDD (3 di_payload pins flipped red first). Swept 7 paths:
  API `/rules` + `sw config show-profile` are global catalogs (no project context — intended);
  `generation.py::_extract_prompt_feedback` ignores the new `findings` key (no breakage, now available
  for future US-3 work); API review calls the engine directly; state-DB serialization safe.
- [x] Phase 3 — implement approved tests: **G-a** (2 units pinning both review handlers' findings-dict
  output contract), **G-b** (6 direct `_report_draft_chain` units — the report had NO direct test, which
  is how the case bug survived; pins REAL lowercase `"fail"` + dict-findings shapes + hostile inputs),
  **G-c** (3 code-handler `project_dir=` pins, written as the red step of defect #4).
- [x] Phase 4 — full suite: **unit 4776 · integration 502 · e2e 157 — 5435 passed, 0 failures.**
- [x] Phase 5 — quality: ruff ✅ · mypy ✅ (303 files) · tach ✅ · file-size 0 errors · roadmap-sync ✅.
- [x] Phase 6 — documentation (this record + as-built notes + walkthrough).
- [x] Phase 7 — walkthrough: INT-US-02_sf03_walkthrough.md.
- [x] Phase 7.5 — Red/Blue adversarial review: **found defect #5** — the report (and the pre-existing
  `_display_review_result` in `sw review`, per fix-inherited) printed LLM/content-derived text
  unescaped into rich markup; an unmatched closing tag (e.g. `[/notatag]`) raised
  `rich.errors.MarkupError` and crashed AFTER a successful run. Fixed TDD (2 hostile-markup tests red
  first) with `rich.markup.escape()` on all finding/rule/summary interpolations. Also reviewed: the
  `project_dir` fallback now fails LOUD on a malformed local override (correct — D-VAL-02 precedence),
  state-DB dumps bounded/JSON-safe, e2e fixtures isolated. Full suite re-run after the fix:
  **unit 4778 · integration 502 · e2e 157 — 5437 passed, 0 failures**; ruff/mypy/tach re-verified.
- [x] Phase 8 — CB-1 committed `e6645a57` (direct to main, 2026-07-23). **INT-US-02 COMPLETE.**

## Post-commit (after CB-1)
- Design tracker: SF-03 Committed ✅ → INT-US-02 done.
- `US-02_integration.md` status ✅; US-2 → 🟢 in master roadmap (Verifiable Proof:
  `tests/e2e/capabilities/workflows/test_int_us_02_drafter_e2e.py`); US-21 dep box sync; queue update.
