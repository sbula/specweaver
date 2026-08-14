# What it takes to close something

A `🟢` or a `✅` is a claim that the implementation stands up to the ticket's promise. It is not a
claim that work happened, that a commit landed, or that a follow-up was filed.

This contract exists because none of that was written down and the artifact says so. Measured
2026-08-13 with `scripts/check_fr_coverage.py` across every capability that has a design document:

| | |
|---|---|
| capabilities with a design | 103 |
| **clean** | **8** |
| `BLOCKED` — an FR carried by no plan, or cited by no test | **46** |
| could not run | 49 |

`C-INTL-01` is the worked example. It is marked `✅`. Its design specifies recursive multi-level
decomposition three separate ways — `FR-3`, `AD-2`, and an agent-sized split heuristic. **None of it
was built, none of it was descoped, and all five of its FRs are cited by no test.** Two were never
carried by any implementation plan. The `✅` was taken on trust for months.

## The four conditions

All four, before any status becomes `🟢` / `✅`:

1. **Every FR has a test that proves it.** `python scripts/check_fr_coverage.py <ID>` exits 0. A
   design saying the behaviour exists is not evidence that it does.
2. **Every FR you are not building is deleted from the design's FR table**, so the descope is
   visible in the artifact rather than inferred from its absence. The checker's own failure message
   says this; follow it.
3. **The `Verifiable Proof` field names test FILES**, and those tests pass and do not skip. A
   directory, a bare `pytest -m integration`, or a suite named in prose is not a proof — nothing
   pins which test carries the claim. `scripts/check_proof_tier.py` enforces the tier; it cannot
   enforce the truth.
4. **The proof is at the right tier.** An `INT-US-NN` story is an integration contract, so its proof
   is integration and e2e tests. Unit tests belong there only to fill a narrow gap found while
   integrating.

## What FR coverage proves, and what it cannot

**`check_fr_coverage.py` proves attribution, never strength.** It answers *which FR does this test
claim to cover*. It cannot answer *does the claim hold* — an `assert True` tagged to an FR satisfies
it exactly.

That is not a gap to be closed with a stricter tagging rule, and the reason matters: for an LLM
agent under a gate, **the cheapest correct solution to "every FR needs a tagged passing test" is a
tagged passing test that asserts nothing.** Strictly less work than proving the FR, and it satisfies
the constraint perfectly. This is `E-VAL-05`'s thesis applied to proof rather than to suppressions.

`check_useless_asserts.py` raises the cost and cannot close it. It reports six mechanically-decidable
patterns, deliberately — a broader hollow-test detector was prototyped and returned 630 candidates,
mostly noise. This passes all six and proves close to nothing:

```python
def test_fr3():
    """Proves: C-INTL-01 FR-3."""
    plan = decompose(spec)
    assert plan is not None
```

**The only mechanical answer to strength is mutation testing** — mutate the code an FR covers; if
the FR's tests still pass, they do not test it. That is `A-VAL-03` (Mutation Testing Gates), and it
is expensive on purpose.

Two proposals that look like cheaper substitutes and are not:

- **Per-test-function `Proves:` tags.** Worth building **only** as the addressing layer `A-VAL-03`
  needs — tags tell mutation testing which tests must die when which code is mutated. Shipped alone
  they are a checkbox that makes the ledger look better while proving nothing, which is the shape
  of the 46 capabilities already marked delivered.
- **Red-green evidence** (a new test must fail against the pre-change code). Catches vacuous tests
  on *existing* code paths, but a test calling a new function fails with `ImportError` when `src/`
  is reverted — which reads as red while proving nothing.

**So the lever is not a checker.** A gate can tell you a test exists; only a reader can tell you it
matters. Ask what breaks if the test is deleted — that is what `specweaver-red-blue-review` is for.
Do not add another mechanical proxy for it; the appearance of rigour is worse than none.

## Filing a follow-up ticket is not one of the conditions

**A new ticket is not a resolution. It is a deferral, and deferrals do not close anything.**

On 2026-08-13 six tickets were filed in a single day, several of them as the "outcome" of resolving
an earlier one. That is inflation: the backlog grows, the verification does not, and each ticket
carries the appearance of progress.

Before filing, answer out loud:

- **Can I verify this now?** Then verify it. A finding backed by a failing test beats a ticket that
  says someone should look.
- **Can I fix this now?** Then fix it. "It is out of scope for the current commit" is a real answer;
  "it deserves its own ticket" usually is not.
- **Does this need a decision I cannot take?** That is the one good reason to file — a scope
  question, a descope, anything that changes what the product does. Say in the ticket which decision
  is needed and who takes it.

A ticket that only records a fact you could have checked is a note, and notes belong in the design
document of the thing they concern.

## An audit's findings are verified, not filed

An audit ticket is the shape most likely to end in a ticket pile: it exists to look, so its natural
output feels like a list of things for someone else to do. **It is not.**

Decided 2026-08-13 while designing `TECH-017`, whose own Goal — written in July — said *"each
unproven claim becoming a filed finding"*. Followed literally across 13 delivered contracts that
would have produced dozens of tickets, none of them verified.

**The order to work in:**

1. **Verify.** Record each claim as proven / unproven / unprovable, with the evidence. The matrix
   is the deliverable, and it is a record, not a queue.
2. **Cite** where the behaviour is genuinely tested elsewhere and only the pointer is missing — but
   only after reading the test and confirming it proves the claim.
3. **Write the test** where the claim is genuinely untested. This is the audit's work, not a
   follow-up's.
4. **File** only where a decision is needed that you cannot take — a scope change, a descope,
   anything that alters what the product does. Name the decision and who takes it.

An audit that ends with more open tickets than it started with has moved work, not done it.

## Do not rush the close

The pressure runs the other way: closing looks like delivery. Two counters worth keeping.

**A specification is a claim under test, not a given.** `C-INTL-01`'s design was read as evidence of
recursion for months. Read the FRs against the code, then against the tests. Where they disagree,
the code is what shipped.

**Verify what the check verifies.** `check_story_preconditions.py` would have caught `INT-US-25`'s
delivered-with-no-proof state any day and never ran; `check_class_health.py` reported *"nothing in
scope"* for a whole session while 23 classes failed; `check_fr_coverage.py` could have blocked
`C-INTL-01` since it was written. All three are story-scoped, and a story-scoped check only fires
when a human remembers the story. **Run it, read its output, and confirm it examined what you think
it examined.**

## Where a citation goes, and what it must not name

`check_fr_coverage.py` credits **any** `FR-N` that appears in a test file naming the story. It reads
text, not intent. Two consequences, both hit for real on 2026-08-13 while re-attributing
`INT-US-28`'s tests (`TECH-017` SF-01):

- **Put the citation in the *module* docstring.** Many test files have none, so "the first `"""`
  in the file" is a fixture's or a helper's docstring. A citation buried there is still counted by
  the gate — it looks green while being filed under the wrong thing.
- **Never name a requirement you are NOT citing.** Writing *"FR-1, FR-6 and FR-7 are deliberately
  not proven here"* in a test marks all three **covered**. The disclaimer is honest and its effect is
  a lie: the sweep read 3 lower for a file that had just admitted a gap. Name the uncited
  requirements in the capability's design document, where nothing scans for citations.

The gate is not the problem and does not need loosening — measured the same day, **102 of 104**
declared-FR credits across every delivered story carry a deliberate attribution. The hazard is
specific: **a file that *discusses* requirements is credited as proving them.** A test about a
checker, or a docstring explaining a gap, is discussion.

**Corollary — a number that improves for a reason you cannot name in one sentence has not improved.**
Re-run the ledger for the specific capability after citing, not just the repo-wide sweep: the
per-capability output names which requirements are still uncited, and that list is the thing to check
against what you actually read.

## NFRs are part of the claim, and were exempt from it until 2026-08-13

The contract above says *"every FR proven by a test"*. That silently excused **a third of the
declared requirement surface**: measured on 2026-08-13, 235 NFRs across 50 designs, and **no script
in the repo contained the string `NFR`** — while 49 test files carried 62 NFR attributions nobody
ever read. NFRs are where the security, isolation, credential-stripping and performance claims live,
so it was the worst third to leave unchecked.

`check_nfr_sweep.py` now ratchets it, counting **behavioural** NFRs only. A row is excused solely by
an explicit `[proof: arch|meta|none]` marker in the design — see the design skill's Phase 3 for
which to use. Two rules:

- **The excuse is per row and lives in the design.** Not a bucket, not a skip-list in the checker.
  `C-FLOW-05` NFR-1 is proved by `tach check`; that is a fact about the requirement and belongs
  next to it, in review and in git history.
- **Do not mark a row to make the number fall.** `[proof: none]` admits the requirement was written
  so nothing can check it; the fix is usually a threshold, not a marker.

Baseline at introduction: **128 uncited behavioural NFRs across 42 delivered designs** (187 before
the 62 non-behavioural rows were classified). Same caveat as every ratchet here — it measures
attribution, never strength.

**It was frozen at 123 first, and 123 was wrong** — worth recording, because the mistake is the one
this whole page is about. `test_check_nfr_sweep.py` quotes `C-FLOW-05 NFR-1`, `E-EXEC-01 NFR-6`,
`TECH-025 NFR-3` and `D-VAL-04 NFR-2` as worked examples of rows a pytest cannot prove. The new
sweep did not yet honour `# fr-coverage: fixture-data`, so it read those four worked examples as
citations and credited five NFRs to stories that had none. **A test explaining why something is
untestable made it look tested**, and the baseline was frozen on that number.

So: **a checker's own tests must declare `# fr-coverage: fixture-data` before its baseline is
frozen**, and a freeze is not a formality — measure once with the marker in place, and treat a
suspiciously good number as a bug until explained.

## Strength: you can now measure it, on one claim at a time

Everything above measures **attribution** — whether a test cites a requirement. None of it can tell
you whether the test would notice the behaviour disappearing. That gap is real and this page has
pointed at `A-VAL-03` for it since it was written.

`scripts/_mutate.py` closes it for a single claim at a time:

```
python scripts/_mutate.py --file src/... --old '<exact anchor>' --new '<neutralised>'
```

It applies the edit in a detached **git worktree**, proves the subprocess imported the sandbox's
source rather than yours, runs the suite, and reports which tests objected. Three verdicts matter:

| Result | What it means |
|---|---|
| `KILLED`, several tests | the behaviour is genuinely protected |
| `KILLED`, **exactly one** | a single point of protection — one flaky or skipped test from none |
| `SURVIVED` | nothing noticed. The claim is unproven **whatever cites it** |

**Use it on the claims you are about to call proven, not the ones you already doubt.** `TECH-017`
ran six of these by hand and four caught vacuous assertions *in the audit's own work* — a guard that
passed with a bypass planted, a credential check that passed un-isolated, a repo root that globbed a
directory which does not exist. Every one of those was written by someone who believed the claim.

The first real measurement it produced: neutralising `sw check --lineage` orphan detection is caught
by **one test out of 6829**, and that test failed at `COLUMNS=80` until 2026-08-14 — so the feature
was unprotected on any 80-column CI while its ledger entry looked green.

Two limits, both real:

- **A surviving mutant is not automatically a gap.** An *equivalent* mutant — one that does not
  change observable behaviour — survives for a reason that is not missing coverage. Confirm the edit
  actually changes something before recording a finding.
- **It cannot mutate code that does not exist.** Where an audit cannot find the code a claim names,
  mutation has no target, and the question is whether the thing was ever built — a scope decision,
  not a coverage measurement.

Because the mutant runs in its own worktree, **your working tree is never touched and you can keep
working while it runs** — a full-suite mutant costs about a minute.

