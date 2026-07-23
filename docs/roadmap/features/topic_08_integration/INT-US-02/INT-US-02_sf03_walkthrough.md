# Walkthrough — INT-US-02 SF-03: Verifiable Proof

- **Commit boundary**: single **CB-1** (direct to `main`). Impl plan APPROVED 2026-07-23
  (Q1–Q3 = a; corner pass added E6/E7 cross-session journeys; E1 surface corrected to `sw draft`).
- Closes INT-US-02 → **US-2 epic 🟢** (US-21 becomes integration-only).

## What changed and why

The FR-8 proof: `tests/e2e/capabilities/workflows/test_int_us_02_drafter_e2e.py` drives the REAL CLI
surfaces through the full co-author → validate → review loop with a scripted `ContextProvider`
(registered through the SF-02 seam — the proof exercises the delivered wiring itself) and a scripted
LLM adapter. Everything else is genuine: real Drafter, real battery machinery (D-VAL-02 project-local
**mechanical-only** preset — deterministic, zero LLM rules), real reviewer verdict parsing, real gate
loop_back, real park/resume state.

| # | Scenario | Proves |
|---|----------|--------|
| E1 | `sw draft` accept path | The US-2 sentence end-to-end, zero manual steps, stale "sw check" hint gone |
| E2 | DENIED → re-draft → ACCEPTED | The living loop (SF-01 feedback path) on the real chain |
| E3 | headless `sw run new_feature` | Park control: exit 0, nothing drafted, resume hint (NFR-5/6) |
| E4 | DENIED × retries | Bounded loop exhausts → non-zero exit + finding text surfaced |
| E5 | provider crash mid-interview | Loud failure, run not COMPLETED, non-zero |
| E6 | park → manual spec → `sw resume` | Historic manual journey through the NEW chain (draft skips, real validate+review run) |
| E7 | rejection-park → edit → `sw resume` | loop_back rewound state + findings in park output + feedback-consumed-once across sessions |

## The proof earned its keep — 5 inherited defects found & fixed

1. **D-VAL-02 dead on the flow-handler SPEC path**: `ValidateSpecHandler` never passed
   `project_dir` to `load_pipeline_yaml` — project-local pipeline overrides silently ignored in
   pipelines (worked only via `sw check`). Fixed (3 call sites).
2. **D-VAL-02 dead on the flow-handler CODE path** *(found by the pre-commit hidden-path sweep)*:
   `ValidateCodeHandler` had the identical bug (`validation.py:315/:317`). Fixed TDD — the 3
   `test_handlers_di_payload` pins were flipped red first.
3. **SF-01 report never listed failing rules**: it compared rule status against uppercase `"FAIL"`,
   but `RuleStatus.value` is lowercase `"fail"`. Now case-insensitive — and pinned by direct report
   tests using the REAL production shape (the report previously had no direct test at all).
4. **Finding texts were never exported** by either review handler (`findings_count` only) — the
   inline report (FR-6) and loop_back feedback (FR-3) need the texts. Now
   `"findings": [f.model_dump() ...]` (full dumps — `sw review` rehydrates `ReviewResult` from step
   output; a message-only list broke that, caught by 6 e2e failures).
5. **Rich-markup crash on hostile LLM text** *(found by the Phase 7.5 Red/Blue pass)*: the report AND
   the pre-existing `sw review` display printed LLM/content-derived text unescaped — an unmatched
   closing tag like `[/notatag]` in a finding, summary, or rule message raised
   `rich.errors.MarkupError` and crashed AFTER the run succeeded. Fixed with `rich.markup.escape()`
   on every untrusted interpolation, pinned by 2 hostile-markup tests (red first).

Hidden-path sweep (Phase 2): API `GET /rules` and `sw config show-profile` load bare defaults by
design (global catalogs, no project context exists on those surfaces);
`generation.py::_extract_prompt_feedback` reads only `hitl_verdict`/`remarks`/`results` keys, so the
new `findings` key is inert there (available for future US-3-side rendering); the API review endpoint
calls the engine directly (handler shape irrelevant); finding dumps are JSON-safe in the state DB.

## Documented (not tested) semantics
**Resume-in-TTY after a rejection-park skips the re-draft**: the findings were consumed (popped) at
park time, so `sw resume` in a TTY sees an existing spec + no feedback → draft skips → validate +
review run on the unchanged spec. If the reviewer rejects again, fresh findings flow and the loop
**self-heals on the next rejection**. Accepted as-is for the base contract (the park message tells the
user to edit the spec, which is the E7 journey).

## Tests
7 e2e scenarios (file above) · G-a: 2 units pinning both review handlers' findings-dict output
contract · G-b: 6 direct `_report_draft_chain` units (real lowercase `"fail"`, dict findings, empty/
None records, hostile non-dict outputs) · G-c: 3 `project_dir=` passthrough pins on the code path ·
Red/Blue: 2 hostile-markup units (report + `sw review` display).

**Full suite (after all fixes):** unit 4778 · integration 502 · e2e 157 — **5437 passed, 0 failures.**
**Quality:** ruff ✅ · mypy ✅ (303 files) · tach ✅ · file-size 0 errors · roadmap-sync ✅.

## HITL gate decisions
- Plan Phase 4/5: Q1 = (a) mechanical-only local preset; Q2 = (a) both surfaces; Q3 = (a) via the
  SF-02 seam. User corner pass added E6/E7 and corrected E1's surface to `sw draft`.
- Pre-commit Phase 2/3: user demanded "corner cases? hidden paths?" → sweep found defect #2 above.
  G-a + G-b approved and implemented. No gate bypassed.
