# Proving a claim: mutation and backfill

## Contents
- 3.2b Mutate — prove the test can still fail
- Campaigns and the durable corpus (and the loop after moving code)
- 3.2c Backfill on contact — a capability you touch gains the FRs it never had

## 3.2b Mutate — prove the test can still fail

Green means the test passes. It does **not** mean the test would notice the behaviour going away,
and a test written after the code has never failed for the right reason.

For each FR this boundary claims to prove, neutralise the line that carries it and check the suite
objects:

```
python scripts/_mutate.py --file src/... --old '<exact anchor>' --new '<neutralised>'
```

It runs in a detached worktree, so your tree is untouched and you can keep working; a targeted run
is seconds, the whole suite about a minute. Three answers matter:

| Result | Meaning |
|---|---|
| `KILLED`, several | protected |
| `KILLED`, **exactly one** | a single point of protection — worth a note in the walkthrough |
| `SURVIVED` | the test does not test this. Fix it now, while you still have the context |

> **Run it on the claims you are about to call proven, not on the ones you already doubt.**
> `TECH-017` ran six of these by hand and **four caught vacuous assertions** — a guard that passed
> with a bypass planted, a credential check that passed un-isolated, a repo root that globbed a
> directory which does not exist. Every one was written by someone who believed the claim.
>
> A *surviving* mutant is not automatically a gap: an **equivalent** mutant, one that does not change
> observable behaviour, survives for a reason that is not missing coverage. Confirm the edit changes
> something before acting on it.

For several claims at once — an audit, or a boundary with many FRs — use
`scripts/_mutate_campaign.py --campaign <json>`, which reuses one sandbox and writes a report to
`.tmp/` (gitignored). Nothing it produces is committed: a report is an input to your decision, never
a record of one.

## Campaigns and the durable corpus

**A probe answers today's question; a CAMPAIGN keeps answering it.** The two above are
throwaway — they tell you whether a claim holds right now and leave no record. When the claim is
one you are about to call **proven**, write it into the durable corpus instead:
`docs/roadmap/features/<topic>/<ID>/<ID>_mutants.json`, one campaign per (N)FR, scoped to the
tests that cover it.

The nightly session then re-asks it forever, and `symbol_sha` drift reports `STALE` when the code
a claim rested on moves. That is the difference between knowing a test was strong in August and
knowing it is strong today.

`python scripts/mutation.py --corpus <path> --no-baseline` runs one file while you write it.
Authoring, dispositions and the morning gate: `docs/dev_guides/writing_mutation_campaigns.md`.

**After moving code a mutant rests on**, repeat until nothing is stale:

1. `python scripts/stale_mutants.py` lists every STALE mutant (exit 1 while any is).
2. Re-anchor each one: its `old` must match exactly once inside its `symbol`.
3. Re-pin it, one mutant at a time:
   `python scripts/_corpus.py --corpus <json> --refresh "<FEATURE> <FR> <id>"`. Never hand-write a
   hash.
4. Rerun every corpus whose file or test scope you touched:
   `python scripts/mutation.py --corpus <json> --out .tmp/<dir> --no-baseline`.

## 3.2c Backfill on contact — a capability you touch gains the FRs it never had

**Measured 2026-08-16 (`TECH-053`): of 62 capabilities marked `✅`, exactly ONE passes its own FR
ledger.** Nineteen have no design document at all — eight from the "Step N" bootstrap, eleven from
the "Feature 3.x" era whose implementation plans carry real design reasoning and **zero FRs between
them**. They are invisible to `check_fr_sweep.py` by construction: no design means no FRs to be
uncited, so they score zero and read as perfect.

**So when a commit boundary touches one of them, it gives it FRs.** Not as a project — writing
nineteen designs at once manufactures nineteen claims nobody can falsify, which is worse than the
silence it replaces. On contact, you already have the context and a change to test against, which
is the whole reason it is cheap here and expensive as an audit.

Two rules make the difference between a requirement and a paraphrase:

1. **Write it from why the capability exists, not from what the code does.** An FR read off the
   implementation restates it, and a restatement can never fail.
2. **Kill a mutant with it before believing it.** Neutralise the line the new FR claims to cover
   (3.2b). If nothing dies, you transcribed rather than constrained — delete the FR and write a
   different one. This is the only mechanical way to tell the two apart, and it caught two vacuous
   tests in `TECH-051`/`TECH-053` written by someone who believed them.

**Where the code predates any recorded intent, a journey proof beats a reconstructed design.**
`D-FLOW-01`'s entire written record is *"SQLite Pipeline Runner & State Persistence."* There is
nothing to backfill *from* except the code, so a spec would describe the implementation with a
straight face. One falsifiable e2e — *a pipeline runs and its state survives a resume* — declares no
FRs, invents no history, and can fail. Prefer it.
