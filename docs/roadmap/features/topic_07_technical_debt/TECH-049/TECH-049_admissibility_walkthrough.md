# Walkthrough: `TECH-049` — a record that answers for less than it claims

- **Ticket**: none, by the `FR-11` precedent in this directory. The record is this file, the test
  docstrings, and six mutants in the nightly corpus
- **Kind**: bugfix · **DAL-C** · 2026-08-27 · **CB-4 of 7**

## The failure

Two ways a session record can be perfectly readable and answer the wrong question. The gate checked
neither.

**It covered part of the corpus.** `mutation.py --corpus <one file>` writes a record shaped
**exactly** like the nightly's — same block, same mutant list, same path. Measured 2026-08-27: a
by-hand run at 05:13 covering 51 mutants overwrote the 03:00 nightly's 187, and `--gate` answered
`CLEAR` from it without a word.

**Its tree is gone.** `_build_sandbox` builds the sandbox as HEAD **plus** `git diff HEAD`
**plus** every untracked file, deliberately, so a run measures the tree you have. The cost is that
a dirty verdict names no commit — nobody can re-derive it, and the gate had no way to ask whether
the diff it rests on is still there.

## The rules

Both are the run stating its own limits, because nothing downstream can recover them.

| | Record says | Gate does |
|---|---|---|
| Reach | `scope: {"kind": "full"}` | admits it |
| | `scope: {"kind": "scoped", "corpora": [...]}` | blocks, naming what it got |
| | no `scope` at all | **blocks** — silence is not a claim of completeness |
| Tree | `dirty: false` | never consults the working tree |
| | `dirty: true`, fingerprint matches | admits it |
| | `dirty: true`, fingerprint moved | blocks |
| | `dirty: true`, fingerprint unreadable | **blocks** — a hash it could not take is not a match |

**Coverage is which corpora the run was pointed at, never how many mutants came back**
`[agreed 2026-08-27]`. A rule counting mutants against the corpus *now* would block all day every
day somebody adds one — the corpus grew by 7 on 2026-08-27 while that night's record held 187 — and
`TECH-056` `NFR-1` says in as many words that a gate blocking on ordinary work is switched off
within a week. `test_a_full_sweep_stays_admissible_after_the_corpus_grows` is that control.

**`dirty` is not the fault.** Blocking on it would kill the gate every morning after an evening's
work, on a verdict that measured exactly the code being worked on. What makes a verdict worthless
is being unable to reproduce it, so that is what is tested.

## The fingerprint hashes both halves

`working_tree_sha(diff, untracked)`. A diff-only hash misses an untracked file, and forgetting
untracked files is not a subtle failure — a helper that existed only in the working tree once made
every importing file fail to collect and reported the whole campaign BROKEN.

Sorted, because `git ls-files --others` ordering is not a contract and a hash depending on it would
report the tree as changed at random. That is the kind of flake that gets a check deleted rather
than fixed.

## `scope` has no default, and that is the point

`build_session_record` requires it. A default would be the completeness claim made by whoever
forgot to think about it — which is precisely how a 51-mutant run came to answer for a 187-mutant
one. Sixteen existing tests failed the moment the rule landed, each because its record could not
say what it covered, and each now says so.

**Three hand-built record shapes went with them.** `test_mutation_gate.py::_report`,
`test_mutation_gate_composition.py::_session_report` and the chain test in `test_mutation_seam.py`
each spelled `{"schema": 1, "session": {...}, "mutants": [...]}` by hand. `_as_dict` already
accepts a plain mutant dict, so they buy nothing and cost the drift that let `68a089d4` rename a
block under the gate with every test still green. They call the producer now.

## Proof it works, on the live artefact

```
$ python scripts/mutation.py --gate
BLOCKED: this record does not answer for the corpus — it covers no scope recorded.
```

That is this morning's 05:13 record, the one that has been answering `CLEAR` all session.

## Probes

| Neutralised | Objections |
|---|---|
| the scope check is removed | 2 |
| a missing scope reads as full | **1** |
| the tree check is removed | 2 |
| an unreadable tree counts as a match | **1** |
| a clean record is judged on the working tree | 14 |
| the fingerprint ignores untracked files | 2 |

All six are in the corpus — five under `FR-11`, one under a new `FR-9` campaign — anchored on
`gate_verdict` and `working_tree_sha`, every hash pinned through `--refresh`.

Eight older anchors drifted as `gate_verdict` grew across CB-1, CB-3 and CB-4, and were re-pinned
**after** the run re-verified them. That included `FR-6 confirmation-always-agrees`, stale since
before this session and clean now.

## Two files this pushed over their ceilings

Both were mine, and both had a real seam rather than an arithmetic one.

- **`mutation.py`** 591 → 634. The cause was duplication: I gathered untracked files twice, once
  for the producer and once for the gate. `_run_reach.py` now owns *what a run may answer for and
  over which tree* — `scope_of`, `tree_sha`, `current_tree_sha` — with one implementation and two
  callers. 599 lines.
- **`test_mutation_gate.py`** 904 → 764. `TestGateVerdictAdmissibility` moved to
  `test_mutation_gate_admissibility.py`: every class left behind asks what the gate concludes
  **from** a record, and every class moved asks whether the record may be read at all.

## Results

| Check | Result |
|---|---|
| full suite | **9,023 passed, 11 skipped** in 89s (was 9,009) |
| `quality.py cb` | 14 passed, 1 skipped, 0 failed |
| `quality.py doc` | 14 passed, 0 failed |
| `tests.py cb TECH-049 --kind bugfix` | unit + integration, ok |
| `TECH-049` corpus | 16 judged, **16 protected**, 0 unprotected, 0 unmeasured, **0 stale** |

## Not fixed here, and named

- **The e2e lifecycle helper now runs `--corpus-dir`, not `--corpus`.** Its subject is the ledger
  lifecycle, which needs a record the gate will accept; a scoped record is refused for reasons that
  have nothing to do with what those tests assert. The change is one line and it is a real
  narrowing of what that file proves — it no longer exercises the scoped path at all, and nothing
  else does end to end either.
- **The nightly's record is still one file at one path**, so a by-hand run can still overwrite it
  before the gate reads it. The gate now *refuses* what it finds there rather than trusting it,
  which is the safe half. **CB-5** gives every run its own file so the nightly's cannot be lost.
- **`--ledger` still defaults to the committed ledger.** CB-3's walkthrough records the cost; this
  boundary's own runs passed `--ledger .tmp/cb4_ledger.json` and left the real one alone.
