# INT-US-21 SF-03 CB-5 — Walkthrough: Docs Currency & Registry Closure

**Commit boundary:** 5 of 5 — **closes the US-21 epic** · **Date:** 2026-07-28 · Plan:
[sf03](INT-US-21_sf03_implementation_plan.md) §Changes → CB-5

## Delivered

Documentation and registries only — **zero source files**.

| Change | Where |
|---|---|
| §13 `feature_decomposition` journey block | `docs/dev_guides/pipeline_engine_guide.md` |
| `C-FLOW-12` design stub | `docs/roadmap/features/topic_03_flow_engine/C-FLOW-12/` |
| `C-FLOW-12` registered | `capability_matrix.md` **and** `topic_03_flow_engine.md` |
| Base contract filled, `INT-US-21-SF02` minted | `US-21_integration.md` |
| US-21 → 🟢, add-on listed, routing queue refreshed | `master_story_roadmap.md` |
| `Status: COMPLETE`, tracker all ✅ | `INT-US-21_design.md` |

- **Guide-2 needed nothing.** `4_interactive_hitl_gates.md` already documents approve-on-resume, all
  four park flavours, the exit-code-0 caveat and "each park costs one resume" (SF-01 CB-4). Checked.
- **Guide-1 distinguishes AUTO from HITL coverage failure.** `pipeline_engine_guide.md` §5 CAUTION
  says a coverage failure pushes the engine into "a rigid 3-Strike Loop `FAILED` status" — that is
  the **auto-gate** behaviour. The bundled decompose gate is **HITL**, which parks unconditionally,
  so a low-coverage plan parks for a human. Measured in CB-3. §13 names the distinction.
- US-21 → 🟢 while `INT-US-21-SF02` is Pending: epic-green means Core Required (MVS) complete —
  US-24 is 🟢 with a 🔴 add-on Pending Design.

## Proof

Every numeric claim machine-verified: 22 e2e scenarios, 33 integration, 4 seam pins, all 12 cited
commit hashes exist.

Claim verification (the docs analogue of test-gap) found four defects, all fixed:

| # | Defect |
|---|---|
| D1 | "28" integration tests stated; there are 33 |
| D2 | Renumbering the routing queue left `2, 2, 3, 4` — one replacement matched nothing |
| D3 | An entry became **self-referential**: item 2 read "may preempt 1–2" |
| D4 | The add-on used an invented `⬜`/`🔜` marker; add-on groups use `🔴`/`🟡`/`🟢` with `` `[ ]` `` items |

Red/Blue (Phase 7.5):

| # | Attack | Verdict |
|---|---|---|
| 1 | Is US-21 → 🟢 justified while `INT-US-21-SF02` is Pending? | **Defended by precedent** (US-24) |
| 2 | House-style conformance of the new add-on entry | **HIT** → D4 |
| 3 | Stale queue-position cross-references | Clean after D2/D3 |
| 4 | Does the `TECH-018` note breach finished-stories-immutability? | Clean — it sits *below* the entries; the delivered `INT-US-21-SUB` block is byte-untouched |
| 5 | Guide-1's "five disjoint buckets" claim | Verified against source: `collided, created, failed, rejected, skipped` |

The `guard_finished_stories` hook blocked a full-file write that would have put a note *inside* the
delivered add-on entry.

| SF | Boundaries | Commits |
|----|---|---|
| SF-01 | 4 | `f1de38f1` `c4c1a109` `6811a943` `5ebcc414` |
| SF-02 | 3 | `4a42b87a` `ce00be20` `5aa20ffa` |
| SF-03 | 5 | `8fff2470` `d0c020f4` `ccdda8f8` `39aa3860` + this |

## Findings still open

- Autonomous DAG execution is `C-FLOW-12` / `INT-US-21-SF02`, behind `C-EXEC-07` and `TECH-014`.
  Re-validating the delivered `INT-US-21-SUB` add-on is `TECH-018`, audit-only.
- **Walkthroughs stop silently.** SF-01 wrote 4 for 4 boundaries, SF-02 3 for 3, SF-03 **0 for its
  first four**; `task.md` never got an SF-03 section (its last marker read "SF-02 CB-1 ← CURRENT").
  Phases that emit chat output (1–2) survived; phases that emit files (6, 7, 7.5) stopped, and CB-5
  nearly shipped ungated until the user stopped it. Remedy: a check that a commit claiming `CB-N`
  carries its walkthrough.
