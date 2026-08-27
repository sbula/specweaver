# Walkthrough: `TECH-049` — the gate could not read the record it is given

- **Ticket**: none, by the `FR-11` precedent in this directory — *"I do not want a new tech ticket
  for that one but we must not forget it either! so just fix it!"*. The record is this file, the
  test docstrings, an extended anti-pattern row, and five mutants now in the nightly corpus
- **Kind**: bugfix · **DAL-C** · 2026-08-27 · **CB-1 of 7**

## The failure

`mutation.py --gate` has two rules that refuse a session record. Neither could fire.

```
gate reads   record["summary"]["baseline"]        (_mutation_gate.py:138)
producer writes  record["session"]["baseline"]    (_session_record.py:308)
```

Measured against the real producer, before any change:

| Record | Verdict |
|---|---|
| red baseline, built by `build_session_record` | **CLEAR** |
| corrupt JSON | **CLEAR** |
| zero-byte file | **CLEAR** |
| valid JSON with no `session` block | **CLEAR** |

Four ways for a nightly to tell you nothing, and all four read as a clean bill of health.

## Why it survived

`68a089d4` — *"retire the word report, and one vocabulary everywhere"* — renamed the block in the
producer **and** the renderer (`_session_record.py:150`), and missed the one reader in
`_mutation_gate.py`. One file out of three.

The tests could not see it because **the gate's tests built their own record**:

```python
json.dumps({"summary": {"baseline": baseline, "verdict": "PASSED"}, "campaigns": []})
```

No producer has written that shape since the rename, and `findings_in` reads `"mutants"`, not
`"campaigns"`. So `TestARedBaselineBlocks` proved the rule against a document that does not exist,
passed every assertion it had, and the shipped gate could not block.

**This is `anti_patterns.md`'s *two modules naming one thing differently across a seam*, and the
remedy was already written there** when it happened — a shared constant plus an agreement test.
`TECH-068` paid for that row twice. The row now records this third instance.

## What it did not cost

Nothing. The 2026-08-24 red baseline blocked the gate through the **per-mutant**
`UNMEASURED [scope-already-red]` verdict, which `_mutation_verdict.py` assigns at judging time and
which never passed through this reader. The net held by a different rope, and that is luck, not
design: a red baseline with zero findings would have gone straight through.

## The fix

| # | Change |
|---|---|
| 1 | `_session_record.SESSION_BLOCK` / `MUTANTS_BLOCK` — the record's two top-level names, declared once. The producer and both readers import them; nothing spells them |
| 2 | `_mutation_gate` imports `_session_record` by the established `_sibling` pattern. One-way: the producer imports nothing from the gate, so no cycle |
| 3 | The baseline rule reads `baseline.get("ran")`, not the block's presence. `_baseline_block(None)` returns `{"ran": False}`, so the old `is not None` test read *nobody measured* as *the tree was red* — the safe absence turned into the loud failure. Found by the `--no-baseline` boundary test, not by inspection |
| 4 | A record with no `SESSION_BLOCK` blocks. Corrupt, empty and truncated all land here: `_read_json` answers `{}` for anything unreadable, and every rule below reads `{}` as *nothing to report* |
| 5 | Every hand-built record shape in the gate's tests is gone. `TestARedBaselineBlocks` and `TestGateVerdictStaleness` both buy their records from `build_session_record` |

## The agreement test

`test_mutation_seam.py::TestTheGateReadsWhatTheProducerWrites` — integration tier, because the
claim is about the pair and neither half can ask it alone.

Its fourth case hands the gate a record carrying the **retired** `summary` block and requires
that the gate refuse it *without* reaching the baseline rule. Asserting only "a red baseline
blocks" would pass again the next time one side is renamed.

**Its first assertion was decoration, and the Phase 7.5 review caught it.** It read
`gate.SESSION_BLOCK is session_record.SESSION_BLOCK`. CPython interns identifier-shaped literals,
so that is `True` even when the gate hard-codes its own `"session"` — it passes in exactly the
state it claims to detect. Measured: two modules each declaring `X = "session"` compare identical.

The falsifiable form is *one name, one place*: no file in `scripts/` outside `_session_record.py`
may spell the block name as a literal. A mutant that keeps the value and only re-spells it —
`SESSION_BLOCK = _record.SESSION_BLOCK` → `SESSION_BLOCK = "session"` — is caught by that
assertion and by nothing else in the repo.

## Probes

Every claim neutralised, against `tests/unit/scripts/test_mutation_gate.py` and
`tests/integration/scripts/test_mutation_seam.py`.

| Neutralised | Objections |
|---|---|
| `record.get(SESSION_BLOCK)` → `record.get("summary")` | 3 |
| `if baseline.get("ran") and not baseline.get("green")` → `if False` | 2 |
| drop the `ran` flag — `if not baseline.get("green")` | 9 |
| `if SESSION_BLOCK not in record` → `if False` | 4 |
| `baseline.get('failed', '?')` → `baseline.get('failed', 0)` | **1** |
| `SESSION_BLOCK = _record.SESSION_BLOCK` → `= "summary"` | 8 |
| `SESSION_BLOCK = _record.SESSION_BLOCK` → `= "session"` (value kept, spelling duplicated) | **1** |

**Two of these are not in the corpus.** Both anchor on a module-level assignment, and
`--refresh` refuses to hash anything without an enclosing `def` or `class` rather than pin a lie.
`STATE.md`'s documented remedy is to re-anchor on the function that *reads* the constant — which
lands exactly on `the-gate-reads-a-retired-key`, already in the campaign. So the mutant was
removed rather than kept `UNHASHED`, and the claim it made is carried by that one plus the
agreement test.

The value-preserving re-spelling has no such re-anchor — the claim *is* the module-level line. It
was left out rather than added as a fifth permanent `UNHASHED` row beside the four `STATE.md`
already names: it would be judged every night and never able to report drift. The guard runs in
every suite run instead, and this measurement is the record that it works.

**`a-red-baseline-with-no-count-stops-blocking` has exactly one protector.** Recorded here because
a single point of protection is one skipped test away from none. It is a message-detail claim —
the `?` in *"the baseline was not green (? failing)"* — so one is proportionate.

## Corpus

`TECH-049_mutants.json` gains `FR-3a` (4 mutants) and grows `FR-11` to 3. Every anchor pinned
through `--refresh`, none hand-written.

`FR-11`'s two existing anchors drifted when `gate_verdict` changed and were re-pinned after the
run re-verified them — not before.

## Results

| Check | Result |
|---|---|
| full suite | **8,986 passed, 11 skipped** in 89s (was 8,977 — nine new tests) |
| `quality.py cb` | 14 passed, 1 skipped, 0 failed |
| `quality.py doc` | 13 passed, 0 failed |
| `tests.py cb TECH-049 --kind bugfix` | unit + integration, 42 passed |
| `TECH-049` corpus | 10 judged, **10 protected**, 0 unprotected, 0 unmeasured |
| `tach` · coupling · `test_architecture.py` | clean · 355 modules in limits · 28 passed |

## Not fixed here, and named

- **`FR-9`'s path clause.** The row now says `session`; it still says *one
  `.tmp/mutation_session.json`*, which stays true until **CB-5** replaces it with a per-run store.
  One clause each, so the two edits do not collide.
- **`TECH-049 FR-6 confirmation-always-agrees` is `STALE`** and was before this boundary. It
  anchors on `mutation.py::confirm_kill`, untouched here. One of the fourteen pre-existing stale
  anchors.
- **`TECH-056 FR-2` does not exist** and a test cited it. Re-homed to `FR-3a` here because the
  class was being rewritten anyway; the *checker* that cannot see a dangling citation —
  `check_fr_coverage.py` prints `3 of 1 requirement(s)` and exits `0` — is **CB-2**.
