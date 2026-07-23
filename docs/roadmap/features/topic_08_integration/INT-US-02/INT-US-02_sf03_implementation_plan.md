# Implementation Plan: Interactive Drafter Integration — SF-03: Verifiable Proof

- **Feature ID**: INT-US-02
- **Sub-Feature**: SF-03 — Verifiable Proof
- **Design Document**: docs/roadmap/features/topic_08_integration/INT-US-02/INT-US-02_design.md
- **Design Section**: §Sub-Feature Breakdown → SF-03
- **Implementation Plan**: docs/roadmap/features/topic_08_integration/INT-US-02/INT-US-02_sf03_implementation_plan.md
- **Status**: APPROVED — approved by Steve Bula on 2026-07-23 (Q1–Q3 = a; corner pass added E6/E7 cross-session journeys, E1 surface corrected to `sw draft`). Single CB-1.

## Scope (from the Design Document)
The FR-8 e2e: a scripted ContextProvider + mocked LLM drive the REAL CLI surfaces through the full
co-author → validate → review loop — accept path, reject→re-draft→accept path, retries-exhausted path,
and the **headless park control** (NFR-5/NFR-6). Test-only; closes the contract → **US-2 goes 🟢**
(US-21 becomes integration-only). **FRs owned: FR-8.**

## Research Notes (Phase 0)

1. **Review stays REAL in the proof.** `reviewer.py` parses `VERDICT: ACCEPTED` / `VERDICT: DENIED` from
   the raw LLM response (`:79/:95/:227`) — a scripted mock adapter returning properly-prefixed texts
   drives the genuine `ReviewSpecHandler` + gate, no handler stubs (stronger than the SF-01 integration,
   which stubbed the handler).
2. **Drafting stays REAL.** The genuine `Drafter` assembles the 6-section spec from the mocked adapter's
   section responses + the scripted provider's answers; the SF-01 feedback-aware re-draft path runs live.
3. **The battery stays REAL — deterministically.** LLM-backed rules (`S03` stranger, `S07` test-first —
   `requires_llm`) would make the e2e non-deterministic. `D-VAL-02` project-local overrides
   (`{project}/.specweaver/pipelines/{name}.yaml`, searched FIRST — `pipeline_loader.py:40/:77`) let the
   e2e project ship a **mechanical-only** copy of the packaged spec preset: real executor, real registry,
   real gate — zero LLM in validation. (Loader requests the archetype-suffixed name first, then
   `validation_spec_default` — provide the names observed at dev time.)
4. **The scripted provider registers through the SF-02 seam** (`set_context_provider_factory`) — the
   proof exercises the delivered wiring itself rather than bypassing it. Reset via fixture (R1 pattern).
5. **Surfaces:** `sw run new_feature` = the full US-2 sentence end-to-end (SF-02 wiring + SF-01 chain in
   the shipped pipeline); `sw draft` = the inline chain + rejection loop. Both are contract surfaces.
6. **Headless control:** no registered factory / non-TTY → parks with **exit 0** (the SF-02 inherited fix)
   — the e2e-level twin of the G1 integration test.

### External deps: none new. Test-only — no src/ changes expected (any defect found = fix under this SF per the fix-inherited rule).

## Implementation Approach
> New file `tests/e2e/capabilities/workflows/test_int_us_02_drafter_e2e.py` (placement beside
> `test_pipeline_e2e.py`). Shared fixtures: scripted provider (deterministic answers), scripted LLM
> adapter (ordered responses: drafter sections… then review verdicts), mechanical-only validation preset
> written into the temp project, seam registration + reset fixture.

### Scenarios
| # | Scenario | Bucket |
|---|----------|--------|
| E1 | **The US-2 sentence, full-real** via `sw draft` (its 3-step chain IS the US-2 loop): scripted provider + accept-verdict adapter → spec co-authored (real Drafter), REAL battery passes (mechanical preset), REAL reviewer accepts — zero manual steps; exit 0; spec exists with lineage tag; stale "sw check" hint ABSENT. *(Corrected from `new_feature`: that pipeline continues into US-3 generation steps — out of this contract; its surface is proven by E3/E6/E7.)* | Happy |
| E2 | **The living loop** via `sw draft`: adapter scripts `VERDICT: DENIED` (with findings) then `VERDICT: ACCEPTED` → loop_back fires, re-draft runs (spec regenerated), second review accepts; exit 0. | Happy/loop |
| E3 | **Headless park control**: `sw run new_feature` headless → parks at draft, **exit 0**, no spec created, resume hint shown. | Boundary/FR-5 |
| E4 | **Exhausted rejection** via `sw draft`: DENIED×3+ → bounded loop exhausts → non-zero exit, findings surfaced. | Degradation |
| E5 | **Hostile**: provider raises mid-interview → drafting fails loud, run not COMPLETED, non-zero. | Hostile |
| E6 | **UNUSUAL WORKFLOW — the historic park→manual→resume journey through the NEW chain**: `sw run new_feature` headless parks → user writes the spec file manually (as the park message instructs) → `sw resume` → draft SKIPS (exists, no feedback) → REAL validate + REAL review run on the manually-written spec → accepted; steps beyond review stubbed PASSED (US-3 scope, out-of-contract boundary). | Boundary/cross-session |
| E7 | **UNUSUAL WORKFLOW — rejection-park across sessions**: headless run reaches review → `VERDICT: DENIED` → loop_back re-enters draft headless → SF-01 parks WITH findings (assert findings in park output) → user edits the spec per findings → `sw resume` → skip → validate → review `ACCEPTED` → proceeds. Proves park-state (loop_back had rewound the step) + resume mechanics + feedback-consumed-once across sessions. | Degradation/cross-session |

**Documented (not tested) semantics:** resume-in-TTY after a rejection-park skips the re-draft (findings
were consumed at park time) and self-heals on the next rejection — recorded in the walkthrough.

## Audit (Phase 2) — open questions for HITL
| # | Question | Options | Proposal | Severity |
|---|----------|---------|----------|----------|
| Q1 | LLM-backed S-rules in the proof. | (a) project-local **mechanical-only** validation preset (real battery machinery, deterministic) [rec]; (b) craft adapter responses to satisfy S03/S07 parsers (brittle); (c) stub ValidateSpecHandler (weakest — not a real battery). | **(a)**. | MEDIUM |
| Q2 | Proof surfaces. | (a) BOTH `sw run new_feature` (E1/E3) and `sw draft` (E2/E4/E5) [rec]; (b) one surface only. | **(a)** — the contract names both halves. | LOW |
| Q3 | Scripted-provider injection. | (a) via the SF-02 seam [rec — the proof exercises the delivered wiring]; (b) patch `HITLProvider`. | **(a)**. | LOW |

## Architecture Verification (Phase 3)
Test-only; no src changes planned. Fixtures use only public/exposed surfaces (the seam is a declared
tach interface). **Verdict:** no violation possible unless a defect is found (then fixed in-scope).

## Session Handoff
**Current status**: DEV COMPLETE — all 7 scenarios green; pre-commit Phases 1–7 done. As-built deltas
(see `INT-US-02_sf03_walkthrough.md`): the "no src changes expected" prediction was wrong in the best
way — the proof + the pre-commit hidden-path sweep flushed **4 inherited defects**, all fixed in-scope
(D-VAL-02 `project_dir` missing on BOTH flow-handler validation paths; SF-01 report uppercase-"FAIL"
comparison; review handlers exporting no finding texts). Gap tests G-a/G-b/G-c added. Full suite
5435 passed, 0 failures.
**Next step**: Phase 7.5 Red/Blue → CB-1 commit closes INT-US-02 → US-2 🟢 → US-21 integration-only.
