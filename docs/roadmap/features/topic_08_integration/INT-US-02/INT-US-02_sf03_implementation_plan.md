# INT-US-02 SF-03 — Verifiable Proof

**Status**: APPROVED — approved by Steve Bula on 2026-07-23 (Q1–Q3 = a; corner pass added E6/E7
cross-session journeys, E1 surface corrected to `sw draft`). Single CB-1. Committed `e6645a57`
(2026-07-23). · **FRs owned**: FR-8 · **Depends on**: SF-01, SF-02 · Design:
[INT-US-02_design.md](INT-US-02_design.md) §Sub-features → SF-03

## Goal

The FR-8 e2e: a scripted ContextProvider + mocked LLM drive the REAL CLI surfaces through the full
co-author → validate → review loop — accept, reject→re-draft→accept, retries exhausted, and the
**headless park control** (NFR-5/NFR-6). Test-only; closes the contract → **US-2 goes 🟢** (US-21
becomes integration-only).

## Where it plugs in

1. **Review stays REAL.** `reviewer.py` parses `VERDICT: ACCEPTED` / `VERDICT: DENIED` from the raw LLM
   response (`:79/:95/:227`). A scripted adapter returning properly-prefixed texts drives the genuine
   `ReviewSpecHandler` + gate — no handler stubs (the SF-01 integration stubbed the handler).
2. **Drafting stays REAL.** The genuine `Drafter` assembles the 6-section spec from the adapter's
   section responses + the scripted provider's answers; SF-01's re-draft path runs live.
3. **The battery stays REAL, deterministically.** LLM-backed rules (`S03` stranger, `S07` test-first —
   `requires_llm`) would make the e2e non-deterministic. `D-VAL-02` project-local overrides
   (`{project}/.specweaver/pipelines/{name}.yaml`, searched FIRST — `pipeline_loader.py:40/:77`) let the
   e2e project ship a **mechanical-only** copy of the packaged spec preset: real executor, real registry,
   real gate, zero LLM in validation. The loader requests the archetype-suffixed name first, then
   `validation_spec_default`.
4. **The scripted provider registers through the SF-02 seam** (`set_context_provider_factory`), so the
   proof exercises the delivered wiring. Reset via fixture (R1 pattern).
5. **Surfaces:** `sw run new_feature` = the full US-2 sentence (SF-02 wiring + SF-01 chain in the
   shipped pipeline); `sw draft` = the inline chain + rejection loop.
6. **Headless control:** no registered factory / non-TTY → parks with **exit 0** (the SF-02 fix) — the
   e2e twin of the G1 integration test.

External deps: none new. Test-only by plan; any defect found is fixed under this SF (fix-inherited
rule).

## Changes

New file `tests/e2e/capabilities/workflows/test_drafter_loop_e2e.py`, beside `test_pipeline_e2e.py`.
Shared fixtures: scripted provider (deterministic answers), scripted LLM adapter (ordered responses:
drafter sections… then review verdicts), mechanical-only validation preset written into the temp
project, seam registration + reset fixture.

| # | Scenario | Bucket |
|---|----------|--------|
| E1 | **The US-2 sentence, full-real** via `sw draft` (its 3-step chain IS the US-2 loop): scripted provider + accept-verdict adapter → spec co-authored (real Drafter), REAL battery passes (mechanical preset), REAL reviewer accepts — zero manual steps; exit 0; spec exists with lineage tag; stale "sw check" hint ABSENT. Not `new_feature`: it continues into US-3 generation steps, out of contract; that surface is proven by E3/E6/E7. | Happy |
| E2 | **The living loop** via `sw draft`: adapter scripts `VERDICT: DENIED` (with findings) then `VERDICT: ACCEPTED` → loop_back fires, re-draft runs (spec regenerated), second review accepts; exit 0. | Happy/loop |
| E3 | **Headless park control**: `sw run new_feature` headless → parks at draft, **exit 0**, no spec created, resume hint shown. | Boundary/FR-5 |
| E4 | **Exhausted rejection** via `sw draft`: DENIED×3+ → bounded loop exhausts → non-zero exit, findings surfaced. | Degradation |
| E5 | **Hostile**: provider raises mid-interview → drafting fails loud, run not COMPLETED, non-zero. | Hostile |
| E6 | **Park→manual→resume through the NEW chain**: `sw run new_feature` headless parks → user writes the spec manually (as the park message says) → `sw resume` → draft SKIPS (exists, no feedback) → REAL validate + REAL review on the manual spec → accepted; steps after review stubbed PASSED (US-3 scope). | Boundary/cross-session |
| E7 | **Rejection-park across sessions**: headless run reaches review → `VERDICT: DENIED` → loop_back re-enters draft headless → SF-01 parks WITH findings (asserted in park output) → user edits the spec → `sw resume` → skip → validate → review `ACCEPTED` → proceeds. Proves park-state (loop_back rewound the step), resume mechanics, feedback-consumed-once across sessions. | Degradation/cross-session |

**Documented (not tested):** resume-in-TTY after a rejection-park skips the re-draft (findings consumed
at park time) and self-heals on the next rejection.

## Decisions (audit)

| # | Question | Options | Chosen | Severity |
|---|----------|---------|--------|----------|
| Q1 | LLM-backed S-rules in the proof. | (a) project-local **mechanical-only** validation preset (real battery machinery, deterministic); (b) craft adapter responses to satisfy S03/S07 parsers (brittle); (c) stub ValidateSpecHandler (weakest — not a real battery). | **(a)**. | MEDIUM |
| Q2 | Proof surfaces. | (a) BOTH `sw run new_feature` (E1/E3) and `sw draft` (E2/E4/E5); (b) one surface only. | **(a)** — the contract names both halves. (E1 later moved to `sw draft`.) | LOW |
| Q3 | Scripted-provider injection. | (a) via the SF-02 seam — the proof exercises the delivered wiring; (b) patch `HITLProvider`. | **(a)**. | LOW |

Architecture check: fixtures use only public/exposed surfaces (the seam is a declared tach interface).
No violation unless a defect fix needs one.

## As built (2026-07-23)

All 7 scenarios green. Not test-only after all: the proof and the pre-commit sweeps found 5 existing
defects, fixed in-scope (details in the [SF-03 walkthrough](INT-US-02_sf03_walkthrough.md)):

| Where | What |
|---|---|
| `validation.py` `ValidateSpecHandler` + `ValidateCodeHandler` | pass `project_dir` to `load_pipeline_yaml`, so D-VAL-02 local overrides apply in pipelines |
| SF-01 report (`_report_draft_chain`) | rule-status comparison case-insensitive (`RuleStatus.value` is lowercase `"fail"`) |
| both review handlers | output `"findings": [f.model_dump() ...]`, not only `findings_count` |
| report + `sw review` display | `rich.markup.escape()` on every untrusted interpolation |

Fixtures as built: `ScriptedProvider` (deterministic answers, `fail_after` option, real
`ContextProvider` subclass); `ScriptedAdapter` (verdict queue on "VERDICT" prompts, section bodies
otherwise — S06 needs the fenced code block); `_mechanical_preset()` (mechanical-only battery:
S01/S02/S06/S09/S10/S08); `_POST_REVIEW_STUBS` (US-3 steps, out of contract); E6/E7 reach the state DB
via `state_db_path` + `SW_PROJECT`.
