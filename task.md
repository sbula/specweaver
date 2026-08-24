# Task: the nightly baseline says how many tests failed, never which

**Skill**: `specweaver-dev` · **Story**: ticket-less bugfix on dev tooling · **Kind**: bugfix

Found 2026-08-24 looking at the nightly. Third night running the baseline was red; the first two
were dirty-tree artefacts, this one was a clean commit (`eeaa84ee`) and therefore real. It cannot be
diagnosed, because the record keeps the count and throws the names away.

## Research (measured — do not re-derive)

| Fact | Evidence |
|---|---|
| The names ARE captured | `mutation.py:252` — `failures=_mutate.killers(out)` |
| `Baseline` carries them | `mutation.py:81-86` — `green`, `failures: list[str]`, `code` |
| The record discards them | `_session_record.py:268` — `"failed": len(getattr(baseline, "failures", []) or [])` |
| A test pins the discard | `test_session_record.py:139` supplies `failures=["tests/a.py::test_x"]` and asserts the block is exactly `{ran, green, failed: 1}` |
| `failed` has exactly two readers | `_session_record.py:153` (prose) and `_mutation_gate.py:142` (gate message) |
| A red baseline voids the whole run | `_session_record.py:155` — *"every verdict below is meaningless while the baseline is red"*; 145 verdicts lost on 2026-08-24 |
| The suite is green now | 8381 passed exit 0, and the blamed scope alone 36 passed — so the failure is flaky or environment-bound at 03:00 |

## Decisions

- `failures` is **added**, `failed` **stays** `[agreed 2026-08-24]`. Removing the count would touch
  the gate, the summary renderer and their tests — a refactor wearing a bugfix's clothes. Both are
  written by one function from one object in one instant, so they cannot drift apart.
- The **JSON keeps every name**; the **prose caps at 10** with a `... and N more` line, following
  `check_decision_citations.py`'s existing shape. Not a new number.
- **Schema stays at 1.** Adding a key is additive — every existing reader keeps working, and the
  only readers are in this repo.

## Commit boundary 1 — a red baseline names what was red

- [ ] 1 — `test_session_record.py` asserts the block carries `failures` and that the names survive
      verbatim — **RED first**, the test currently pins their removal
- [ ] 2 — `_baseline_block` writes `failures` alongside `failed` -> GREEN
- [ ] 3 — `test_mutation_summary.py` asserts the prose PRINTS the names when the baseline is red,
      and caps at 10 with a `... and N more` line — **RED first**
- [ ] 4 — the prose renderer prints them -> GREEN
- [ ] 5 — probe both with `_mutate.py`: neutralise each and confirm the suite objects
- [ ] **CB-1 — a red baseline is diagnosable**

## Notes on tiers and proof

- Unit tier throughout. `_baseline_block` and the renderer are pure functions over a dataclass;
  there is no seam and no journey here.
- **Composition check (2.5c):** these two are used in sequence — the writer produces the block the
  renderer consumes. A test of each alone would pass while the pair disagreed about the key's name,
  which is `TECH-068`'s `kind`/`type` defect exactly. Task 3 drives the renderer from a block built
  by the real writer, not from a hand-made dict.
- **Out of scope, named rather than hidden:** this makes the failure *diagnosable*, it does not find
  it. The flaky test stays unknown until it recurs — with names attached.
