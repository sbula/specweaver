# Writing a Mutation Campaign

A campaign asks one question: **if this requirement stopped working, would any test notice?**

You write the mutants by hand. That is deliberate — generating them from an AST is `A-VAL-03`, and
a hand-written mutant carries the intent a generated one cannot.

> Status: `TECH-049`, partially delivered. The corpus format, drift hashing and maintenance CLI
> exist. **Nothing runs a campaign yet** — the runner, verdicts, report and nightly gate are
> still to come. See the ticket's design for what remains.

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

## Related

- `scripts/_mutate.py` — run one mutant now, in a detached worktree
- `scripts/_mutate_campaign.py` — the older ad-hoc batch form, which this corpus supersedes once
  the runner consumes it
- `.claude/skills/specweaver-ticket/references/closure-contract.md` — why attribution is not strength
