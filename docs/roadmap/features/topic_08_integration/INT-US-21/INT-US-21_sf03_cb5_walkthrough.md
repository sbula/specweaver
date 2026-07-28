# Walkthrough: INT-US-21 SF-03 CB-5 — Docs Currency & Registry Closure

- **Feature**: INT-US-21 — Autonomous Feature Decomposition (base integration contract)
- **Sub-feature**: SF-03 — CLI Journey, Verifiable Proof & Registry Closure
- **Commit boundary**: 5 of 5 — **closes the US-21 epic**
- **Date**: 2026-07-28

## What changed

Documentation and registries only. **Zero source files.**

| Change | Where |
|---|---|
| §13 `feature_decomposition` journey block | `docs/dev_guides/pipeline_engine_guide.md` |
| `C-FLOW-12` design stub | `docs/roadmap/features/topic_03_flow_engine/C-FLOW-12/` |
| `C-FLOW-12` registered | `capability_matrix.md` **and** `topic_03_flow_engine.md` |
| Base contract filled, `INT-US-21-SF02` minted | `US-21_integration.md` |
| US-21 → 🟢, add-on listed, routing queue refreshed | `master_story_roadmap.md` |
| `Status: COMPLETE`, tracker all ✅ | `INT-US-21_design.md` |

**Guide-2 needed nothing.** `4_interactive_hitl_gates.md` already documents approve-on-resume, all
four park flavours, the exit-code-0 caveat and "each park costs one resume" — written during SF-01
CB-4, earlier than the design anticipated. Checked rather than assumed; nothing written.

## What the gate found

This boundary was initially committed-bound **without a gate** — the user stopped it. Running the
gate properly then found four defects, all in documentation about to become permanent record:

| # | Defect |
|---|---|
| D1 | **"28" integration tests stated; there are 33.** The one number asserted from memory rather than measured was the one that was wrong |
| D2 | Renumbering the routing queue left `2, 2, 3, 4` — one replacement silently matched nothing |
| D3 | Renumbering also made an entry **self-referential**: item 2 read "may preempt 1–2", i.e. itself |
| D4 | The add-on used an invented `⬜`/`🔜` marker; every add-on group in the roadmap is `🔴`/`🟡`/`🟢` with `` `[ ]` `` items |

All four fixed. Every remaining numeric claim is machine-verified: 22 e2e scenarios, 33 integration,
4 seam pins, and all 12 cited commit hashes confirmed to exist.

## Red/Blue (Phase 7.5)

| # | Attack | Verdict |
|---|---|---|
| 1 | Is US-21 → 🟢 justified while `INT-US-21-SF02` is Pending? | **Defended by precedent** — US-24 is 🟢 with a 🔴 add-on Pending Design. Epic-green means Core Required (MVS) complete |
| 2 | House-style conformance of the new add-on entry | **HIT** → D4 |
| 3 | Stale queue-position cross-references | Clean after D2/D3 |
| 4 | Does the `TECH-018` note breach finished-stories-immutability? | Clean — it sits *below* the entries; the delivered `INT-US-21-SUB` block is byte-untouched |
| 5 | Guide-1's "five disjoint buckets" claim | Verified against source: `collided, created, failed, rejected, skipped` |

> The immutability point was not caught by review — the **`guard_finished_stories` hook blocked a
> full-file write** that would have inserted a note *inside* the delivered add-on entry. The guard
> worked exactly as designed.

## One correction folded into Guide-1

The guide's existing §5 CAUTION states that a coverage failure pushes the engine into "a rigid
3-Strike Loop `FAILED` status". That is the **auto-gate** behaviour. The bundled journey's decompose
gate is **HITL**, and a HITL gate parks unconditionally whatever the step returned — so a
low-coverage plan parks for a human instead of looping to FAILED. Measured in CB-3, not inferred.
§13 names the distinction rather than contradicting §5.

## Process note

SF-01 produced 4 walkthroughs for 4 boundaries; SF-02 produced 3 for 3; **SF-03 produced 0 for its
first four**, and `task.md` was never given an SF-03 section at all — its last marker still read
"SF-02 CB-1 ← CURRENT". The phases that emit chat output (1–2) survived; the phases that emit files
(6, 7, 7.5) stopped silently, because a file that was never written is indistinguishable from one
that was never required.

Recorded here because it is the reason this boundary nearly shipped ungated, and because the
remedy — a check that a commit claiming `CB-N` must carry its walkthrough — is mechanical, not a
matter of remembering.

## US-21 is closed

| SF | Boundaries | Commits |
|----|---|---|
| SF-01 | 4 | `f1de38f1` `c4c1a109` `6811a943` `5ebcc414` |
| SF-02 | 3 | `4a42b87a` `ce00be20` `5aa20ffa` |
| SF-03 | 5 | `8fff2470` `d0c020f4` `ccdda8f8` `39aa3860` + this |

Autonomous DAG execution is `C-FLOW-12` / `INT-US-21-SF02`, sequenced behind `C-EXEC-07` and
`TECH-014`. Re-validating the delivered `INT-US-21-SUB` add-on is `TECH-018`, audit-only.
