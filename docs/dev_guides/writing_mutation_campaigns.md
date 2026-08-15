# Writing a Mutation Campaign

A campaign asks one question: **if this requirement stopped working, would any test notice?**

You write the mutants by hand. That is deliberate — generating them from an AST is `A-VAL-03`, and
a hand-written mutant carries the intent a generated one cannot.

A nightly timer runs the whole corpus at 03:00; in the morning a gate tells you whether anything
needs reading. Nothing is blocked until a finding goes unread.

## Where it lives

```
docs/roadmap/features/<topic>/<ID>/<ID>_mutants.json
```

One file per feature, beside its design. The **filename is the authority**: `feature` inside must
match it, which is what lets the duplicate-id check read one file instead of the whole corpus.

## The shape

```json
{
  "schema": 1,
  "feature": "C-EXEC-06",
  "campaigns": [
    {
      "requirement": "FR-8",
      "title": "Multi-step generated-file e2e stays worktree-bounded",
      "scope": ["tests/e2e/sandbox/test_session_worktree_isolation_e2e.py"],
      "mutants": [
        {
          "id": "isolation-off",
          "file": "src/specweaver/core/flow/engine/isolation.py",
          "symbol": "apply_session_policy",
          "old": "return policy.enabled",
          "new": "return False",
          "breaks": "no worktree is created, so step 2 runs at the real root"
        }
      ]
    }
  ]
}
```

## Choosing a mutant

**One campaign, one (N)FR.** A mutant should break *that* requirement and preferably nothing else.

- `breaks` states the bug you are planting, in plain words. A survival is unreadable without it.
- `old` must appear **exactly once inside `symbol`** — not in the file. `return None` occurs 191
  times across 77 files, so file-uniqueness would force unreadable anchors.
- `old` and `new` must differ. An identical pair mutates nothing and reports a survival meaning the
  opposite of what it says.

**`symbol` is a dotted path.** `apply_session_policy` for a function, `SessionPolicy.apply` for a
method. Bare names are ambiguous in 25 files of `src/` — one holds `__init__` six times.

## Scope

`scope` lists the test files the mutant runs against, and it is **authoritative**. A mutant passes
only when a killer is *in scope*: a bystander test dying proves something noticed, not that the
requirement is covered.

Where the tests carry `Proves:` tags, the run cross-checks scope against them and reports a
`scope_drift` note if they disagree — a finding for a human, never a verdict.

## Drift

`symbol_sha` fingerprints the **normalised AST** of the enclosing symbol.

| State | Meaning |
|---|---|
| `UNHASHED` | no hash pinned yet. Legal — this is how every mutant starts |
| `OK` | the code still hashes to what was pinned |
| `STALE` | the code moved, or the symbol is gone. Re-read the claim |

Reformatting does not change it; renaming a local does; editing a docstring does not.

## Maintenance

```bash
python scripts/_corpus.py --corpus <path> --root . --refresh "<FEATURE> <FR> <id>"
python scripts/_corpus.py --corpus <path> --retire FR-8 --reason "requirement descoped"
```

**One mutant per refresh, and there is no bulk flag.** `--refresh-all` would clear every `STALE` in
one keystroke with nobody re-reading a claim, and drift detection would become decoration. The
one-line diff a refresh leaves is the review.

**Retire marks, never deletes.** A descoped requirement keeps its tombstone: deleting the campaign
destroys the only record it was ever measured.

Refreshing a mutant whose symbol has vanished **fails**. Pinning a hash for code that is gone
launders real drift into a green corpus.

## The morning routine

```bash
python scripts/mutation.py --gate
```

`CLEAR` and you carry on. `BLOCKED` names every finding nobody has looked at.

For each one, read its `breaks` field — it says what bug was planted — then decide:

| Disposition | Means | Counted by the census |
|---|---|---|
| `real-gap` | the requirement genuinely is not protected; you fixed it or wrote the test | No |
| `equivalent` | the mutant changes no observable behaviour, so surviving proves nothing | **Yes** |
| `will-fix` | real, and you are continuing anyway | **Yes** |
| `stale-refreshed` | the code moved; you re-read the claim and re-pinned it | No |

```bash
python scripts/mutation.py --confirm "C-EXEC-06 FR-8 isolation-off" \
       --as will-fix --why "narrowing the scope first"
```

**The gate never asks you to prove a fix.** Demanding proof would mean an on-demand corpus run,
which this design rejects — the next scheduled run re-measures anyway, so an unfixed finding simply
comes back. What stops that being a free pass is the recurrence count: a `will-fix` re-confirmed for
a fortnight is visible in the ledger, and `equivalent` and `will-fix` are ratcheted, so the number
of live bypasses may fall and never rise.

A `STALE` finding means the code a claim rested on moved. Re-read the claim first — that is the
whole point of the signal — then:

```bash
python scripts/_corpus.py --corpus <path> --root . --refresh "<derived id>"
```

### Running it by hand

```bash
python scripts/mutation.py --corpus-dir docs/roadmap/features   # the whole corpus
python scripts/mutation.py --corpus <path> --no-baseline        # one file, quickly
python scripts/mutation.py --install-timer                      # nightly at 03:00
```

Exit codes report the **run**, not the decision: `0` nothing failed, `1` something did, `2` it could
not run. Whether work continues is `--gate`'s answer, deliberately separate.

## Related

- `scripts/_mutate.py` — run one mutant now, in a detached worktree
- `scripts/_mutate_campaign.py` — the older ad-hoc batch form, which this corpus supersedes once
  the runner consumes it
- `.claude/skills/specweaver-ticket/references/closure-contract.md` — why attribution is not strength
