# task.md — the mutation session gate

**Kind**: bugfix · **Owner**: `TECH-049` (session record + gate), `TECH-056` (disposition gate)
**No ticket**, per the `TECH-049_fr11_walkthrough.md` precedent. The record is a walkthrough.

## Decisions taken with the user, 2026-08-27

| Q | Answer |
|---|---|
| Q1 | Only a **full-corpus** run may close a finding as `withdrawn`. A scoped run closes nothing. A scoped run closing what it never looked at is the defect; a full run is the only thing that can tell deletion from absence `[agreed 2026-08-27]` |
| Q2 | A dirty record is admissible **only while the tree still hashes the same**. `session.diff_sha` over `git diff HEAD`; the gate re-hashes and blocks on a mismatch. The sandbox is HEAD **plus** the uncommitted diff by design (`_mutate.py:292`), so dirty is an input, not a fault — what makes a verdict worthless is being unable to reproduce it `[agreed 2026-08-27]` |
| Q3 | Coverage is judged by **which corpus files the run was pointed at**, never by exact mutant ids. A full sweep stays a full sweep when a corpus file grows. The gate blocks on a scoped record and names the scope it got `[agreed 2026-08-27]` |
| Q4 | One file per run, scope named in the filename `[agreed 2026-08-27]` |
| Q5 | A record is deleted only when a later `PASSED` record supersedes it. `FAILED` and `NOT_RUN` are kept until then `[agreed 2026-08-27]` |
| Q6 | Superseding requires **covering** scope. A narrow clean run cannot retire a wide failure `[agreed 2026-08-27]` |
| Q7 | No cap. Warn past **20** unsuperseded records, in the run **and** in `--gate`. Never auto-delete a record of a failure `[agreed 2026-08-27]` |
| Q8 | Delete the stale scratch in `.tmp/` once, by hand, listing it first `[agreed 2026-08-27]` |
| Q9 | One store. Every run writes `.tmp/sessions/`; the gate picks the newest record whose scope covers the corpus `[agreed 2026-08-27]` |
| Q10 | Correct `TECH-049` `FR-9`'s text where it has become false `[agreed 2026-08-27]` |
| Q11 | Keep `session`. Move the stranded reader `[agreed 2026-08-27]` |

## The five defects

1. **The red-baseline block cannot fire.** `_mutation_gate.py:138` reads `record["summary"]["baseline"]`;
   `_session_record.py:308` writes `session.baseline`. Commit `68a089d4` renamed the block and moved the
   renderer, missing the one reader. Measured against the real producer: a red baseline reads `CLEAR`.
2. **The gate's tests build a record no producer has ever written** — `{"summary": …, "campaigns": []}`,
   while `findings_in` reads `"mutants"`. Every assertion in `TestARedBaselineBlocks` is against a fiction.
3. **`TECH-056 FR-2` does not exist.** `TECH-056` declares one FR and says so in its own words.
   `test_mutation_gate.py:342` cites `FR-2`; the mutant is filed under `FR-1`.
4. **`check_fr_coverage.py` cannot see a dangling citation.** It prints `3 of 1 requirement(s)` and
   exits `0`. It asks whether every declared FR is cited, never whether every citation names a declared FR.
5. **A scoped run silently withdraws every finding outside its scope.** Reproduced against `fold_session`.

---

# CB-1 — the gate reads where the producer writes  (defects 1 + 2)

- [x] **T1** — Red: an integration test building a record with the **real** `build_session_record`,
      a red baseline, asserting `gate_verdict` blocks. Must fail today.
- [x] **T2** — Red: producer and gate **agree on the key** — the seam test the rename never had.
- [x] **T3** — Rewrite `TestARedBaselineBlocks` through `build_session_record`. No hand-built
      record shapes left anywhere in the gate's tests.
- [x] **T4** — Green: `_mutation_gate.py` reads `session.baseline`.
- [x] **T5** — Mutants: the gate reads the wrong key · the baseline check is removed.
- [x] **T6** — Pre-commit Phase 2 found a second family: corrupt, empty and truncated records all
      read `CLEAR`. Four tests and an unreadable-record rule, added in this boundary.
- [x] **T7** — Pre-commit Phase 1 found the anti-pattern's remedy was half-applied.
      `_session_record.SESSION_BLOCK` / `MUTANTS_BLOCK`; both readers import them.
- [x] **T8** — Pre-commit Phase 7.5 found the agreement test's identity assertion cannot fail
      (CPython interns the literal). Replaced with a one-name-one-place source guard, and proved
      it fails on a mutant that keeps the value and only re-spells it.

**Every check before the commit**: full suite · `quality.py cb` · `doc` · ruff · ruff format ·
mypy · complexity · class health · duplication · conventions · tach.

---

# CB-2 — a citation that names nothing  (defects 3 + 4)

- [x] **T1** — Red: `check_fr_coverage.py` fails a citation naming an FR the design does not declare.
- [x] **T2** — Red: the `3 of 1` ratio cannot be printed — a count above the declared total is the bug.
- [x] **T3** — Green: the check reads citations both ways.
- [x] **T4** — Re-home the red-baseline test. It proves `TECH-049` `FR-3a`, not a `TECH-056` `FR-2`
      that never existed. Move the mutant to the campaign that matches.
- [x] **T5** — Mutants: a dangling citation passes · the reverse check never runs.
- [x] **T6** — The sweep: `check_dangling_citations.py`, repo-wide, in the `doc` gate `[agreed 2026-08-27]`.
- [x] **T7** — All 9 findings fixed. `TECH-058` gained `FR-2`/`FR-3` — delivered by its own
      boundary, never written down `[agreed 2026-08-27]`.
- [x] **T8** — A SILENT mutant exposed a vacuous test of mine: the fixture story had no plan, so
      `missing_from_plan` blocked it whatever the dangling rule did. Fixture given a plan; the
      assertion now requires the other two failures to be absent.

**Every check before the commit.**

---

# CB-3 — a run may not close what it never looked at  (Q1, defect 5)

- [ ] **T1** — Red: a **scoped** run leaves an out-of-scope open finding open.
- [ ] **T2** — Red: a **full** run still closes a genuinely deleted mutant as `withdrawn`.
- [ ] **T3** — Red: a scoped run closes nothing as `withdrawn`, even inside its own scope.
- [ ] **T4** — Green: `fold_session` takes the run's scope; only a full sweep may withdraw.
- [ ] **T5** — Mutants: every run may withdraw · no run may withdraw.

**Every check before the commit.**

---

# CB-4 — a record says what it covered, and the gate reads it  (Q2, Q3)

- [ ] **T1** — Red: the record carries `session.scope` (full or the corpus files) and `session.diff_sha`.
- [ ] **T2** — Red: a dirty record is admissible while the tree hashes the same.
- [ ] **T3** — Red: the same record blocks once the tree changes, and the reason says so.
- [ ] **T4** — Red: a scoped record blocks, naming the scope it got.
- [ ] **T5** — Red: a full-sweep record does not block **after a corpus file grows**. The `TECH-056`
      `NFR-1` control — this is the test that stops the gate being switched off.
- [ ] **T6** — Green: producer writes `scope` and `diff_sha`; `gate_verdict` gains both rules,
      after staleness and baseline, before findings.
- [ ] **T7** — Mutants: the diff hash is ignored · the scope check is removed · a scoped record passes.

**Every check before the commit.**

---

# CB-5 — one store, one record per run  (Q4, Q9)

- [ ] **T1** — Red: two runs in the same second leave two records, neither overwriting the other.
- [ ] **T2** — Red: the gate picks the newest **covering** record and ignores a newer scoped one.
- [ ] **T3** — Red: no covering record at all blocks, saying the nightly has not run.
- [ ] **T4** — Green: `.tmp/sessions/`; `--out` and `--gate` follow; systemd unit updated.
- [ ] **T5** — Correct `TECH-049` `FR-9`: one file becomes one store, `summary` becomes `session`.
      One edit, beside the fact, saying why.
- [ ] **T6** — Mutants: the gate takes the newest record regardless of scope · the suffix is dropped.

**Every check before the commit.**

---

# CB-6 — retention by state, not by age  (Q5, Q6, Q7)

- [ ] **T1** — Red: a `FAILED` record survives a later `PASSED` record of **narrower** scope.
- [ ] **T2** — Red: a `FAILED` record is deleted by a later `PASSED` record of covering scope.
- [ ] **T3** — Red: a `NOT_RUN` record is kept, exactly as a `FAILED` one.
- [ ] **T4** — Red: past **20** unsuperseded records the run warns and deletes nothing, and
      `--gate` prints the same warning.
- [ ] **T5** — Green: pruning runs at the **start** of a session, so a crashed run still gets swept.
- [ ] **T6** — Mutants: a narrow pass supersedes a wide failure · the warning never fires ·
      pruning deletes a failure.

**Every check before the commit.**

---

# CB-7 — the scratch that nothing prunes  (Q8)

- [ ] **T1** — List every file in `.tmp/` for the user, then delete all but `HANDOVER.md` and the
      live records.
- [ ] **T2** — The walkthrough: `docs/roadmap/features/topic_07_technical_debt/TECH-049/`.

**Every check before the commit.**
