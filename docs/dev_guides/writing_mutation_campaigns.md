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

**Never scope a mutant to a test that runs the corpus.** `tests/e2e/scripts/test_mutation_nightly.py`
executes a real session; a campaign scoped to that file would run it inside a sandbox, where it
spawns another session over the same corpus, without bound. Verify such a claim with `_mutate.py` by
hand and record the verdict in the test's docstring — the corpus cannot hold this one.

**Mutate a guard so it fails CLOSED, never open.** When the target is something every test runs
through — a suite-wide `autouse` fixture, a conftest hook, a shared assertion helper — a mutant that
makes it *raise more* poisons the run instead of measuring it. `TECH-055` planted the obvious edit
in a baseline-comparison helper, inverting `!=` to `==` so that every *unchanged* file was reported
as rewritten. The autouse guard then failed sixteen tests in teardown, and `is_broken()` cannot
distinguish that from a collection failure, so the run was judged **BROKEN** and proved nothing —
which is the correct refusal, not a bug in the runner.

The fix is to choose the direction: make the guard **miss** what it should catch (`if … and False`),
never **invent** what is not there. The same rule applies to any mutant whose blast radius includes
the machinery running the tests that judge it.

## Scope

`scope` lists the test files the mutant runs against, and it is **authoritative**. A mutant passes
only when a killer is *in scope*: a bystander test dying proves something noticed, not that the
requirement is covered.

Where the tests carry `Proves:` tags, the run cross-checks scope against them and reports a
`scope_drift` note if they disagree — a finding for a human, never a verdict.

## What a mutant costs, and why scope is the lever

Measured 2026-08-16 over the whole corpus, 24 mutants, one scoped pytest plus a confirmation re-run
each:

| Scope tier | Seconds per mutant |
|---|---|
| unit | **1.2 – 1.6** |
| unit + integration | **1.2 – 1.3** |
| includes an e2e file | **9.9 – 16.1** |

**An e2e scope is an 8x purchase.** On that run, 42% of the mutants consumed **86%** of the clock —
ten e2e-scoped mutants took 111s while the other fourteen took 18s between them. The cause is not
the corpus: an e2e test spawns real subprocesses, and the mutant pays for all of them, twice, once
to measure and once to confirm.

So **scope at the lowest tier that can still falsify the claim.** That is not a cost-saving
instruction dressed as a principle — it is the same rule `scope` already states, with a price on it.
Where a claim genuinely lives in a journey (`TECH-054` FR-1's resume discovery could not be seen
below e2e), pay it deliberately and say so in `breaks`.

**The arithmetic that makes this matter.** Measured 2026-08-16: **402 FRs and 177 behavioural NFRs
are mutatable — 579 of 658 declared, 88%.** The other 79 cannot carry a mutant at all: `[proof: meta]`
is a rule about tests or docs and `[proof: arch]` is proven by a gate, so neither has a production
line to neutralise. With 61 of 135 capabilities delivered, full roadmap is roughly **918 mutatable
requirements**, and at today's 2.7 mutants each:

| Scope mix | Mutants | Serial wall clock |
|---|---|---|
| disciplined (unit/integration) | ~2,480 | **~54 min** |
| today's mix | ~2,480 | **~3.7 h** |
| e2e-dominated | ~2,480 | **~7.6 h** |

The nightly starts at 03:00, so the middle row lands at 06:42 with the whole margin spent, and a
session that overruns is not reported as stale for 48 hours. The corpus covers **10 of 579** today —
1.7% of the destination — so the difference between the first row and the third is still entirely
undecided, and it gets decided one campaign at a time, by whoever picks a scope.

Parallel execution is the other half of the answer and is deliberately not built yet: see
`TECH-057`, which records why (sandbox build and teardown measured **0.2s**, so a pool is cheap when
it is wanted).

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
