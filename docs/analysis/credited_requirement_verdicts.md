# Credited-requirement verdicts

`TECH-017`, 2026-08-13. Every requirement the ledger counted as **proven** on a delivered story,
checked against the test that supposedly proves it.

This is the audit the threshold sweep could not do. That sweep compared numbers, and only **4 of
152** credited requirements state a number — so "no mismatches found" there meant four requirements
were inspected, not that the rest were sound. This one reads.

## The census

| | |
|---|---|
| Credited requirements on delivered stories | **152** across 20 stories |
| Survive the audit | **127** |
| **Revoked — the credit was never evidence** | **25** |

29 fell to the ambiguity rule; 4 were then restored by *qualifying* the mention — writing
`C-EXEC-06 FR-7` where the file said only `FR-7` — after reading each against its design row.

How the 152 were being credited before the audit:

| Mechanism | Count | Trustworthy? |
|---|---|---|
| Authoritative `Proves:` tag | 52 | Yes — an author's explicit claim |
| Bare id, but the file names only this story | 19 | Yes — unambiguous by elimination |
| Id qualified by its story nearby (`B-EXEC-01 FR-5`) | 44 | Yes |
| **Bare id in a file naming SEVERAL stories** | **37** | **No — ambiguous by construction** |

## Finding 1: requirement ids are unique only *within* a story

Nine designs declare an `FR-5`. The legacy rule credited a bare `FR-5` to **every** story the file
happened to name — which is not a heuristic that is occasionally wrong, it is wrong for all but at
most one of them, every time.

The clearest case: **`B-EXEC-01` FR-5** is the container executor's *"SHALL return the container's
exit code, stdout, and stderr"*. Its credit came from `test_headless_run_keeps_provider_none` —
*"no TTY (CliRunner default) → provider stays None; the draft parks"* — a test about interactive
drafting that shares nothing with it but the token `FR-5`.

Three more were traced to a single comment belonging to a different story entirely:

```
test_validate_tests_handler.py:  # INT-US-24 SF-01 T3 (FR-2 producer): ...
```

That line credited `B-EXEC-01` FR-2 (read-only source mount), `B-EXEC-01` FR-3 (writable scratch
mount) and `INT-US-09` FR-3 (isolation enablement policy). It is about none of them.

**Fixed in the grammar, not by hand:** a bare requirement id in a file naming more than one story
now credits nothing. Qualifying the mention (`B-EXEC-01 FR-5`) or adding a tag restores it, and both
make the claim checkable. After qualifying the mentions whose owner could be established by reading,
**25 remain revoked**:

| Story | Requirements revoked | n |
|---|---|---|
| `B-EXEC-01` | FR-2, FR-3, FR-5, FR-7, NFR-1, NFR-2 | 6 |
| `INT-US-02` | FR-2, FR-4, NFR-2, NFR-3, NFR-5 | 5 |
| `INT-US-09` | FR-3, FR-5, NFR-2, NFR-6 | 4 |
| `INT-US-03` | FR-5, NFR-1, NFR-2 | 3 |
| `C-EXEC-06` | FR-5, NFR-1 | 2 |
| `INT-US-21` | NFR-6, NFR-8 | 2 |
| `INT-US-24` | FR-5, NFR-5 | 2 |
| `TECH-006` | NFR-8 | 1 |

### Qualified rather than revoked — owner established by reading

Ten mentions were rewritten to name their owner, restoring the credit to the story that earned it
and removing it from the ones that had not:

| Was | Now | Owner confirmed by |
|---|---|---|
| `(NFR-1 backward compat)` | `(INT-US-09 NFR-1 …)` | *"isolation policy absent/disabled → byte-identical"* |
| `(FR-7 / NFR-2)` | `(C-EXEC-06 FR-7 / C-EXEC-06 NFR-2)` | *"keep per-run isolation opt-in / default-off"* |
| `[Boundary/NFR-2]` | `[Boundary/C-EXEC-06 NFR-2]` | *"no host-execution regression"* |
| `[Boundary/FR-5]` ×2 | `[Boundary/INT-US-02 FR-5]` | *"headless behavior preserved … park byte-identical"* |
| `the NFR-2 guard` | `the C-EXEC-06 NFR-2 guard` | same |
| `"""NFR-6 half …` ×2 | `"""TECH-006 NFR-6 half …` | *"a missed migration SHALL fail loudly at construction"* |
| `(NFR-2)` LLM calls | `(INT-US-24 NFR-2)` | *"happy path performs zero arbitration LLM calls"* |
| `# FR-4 end-to-end` | `# INT-US-24 FR-4 end-to-end` | *"feedback-aware scenario regeneration"* |
| `so NFR-3 (LLM economy)` | `so INT-US-21 NFR-3 (LLM economy)` | *"the journey costs exactly the decompose LLM call(s)"* |

`B-EXEC-01` is the worst hit and the least surprising: it is the container-executor contract, and
its requirements were being "proved" by the settings-loader and CLI-config tests, which mention it
in passing while testing worktree isolation.

## Finding 2 — WITHDRAWN. The control exists; the audit's grep was wrong

**This finding was published and is false.** It is kept, struck, because the way it was reached is
the same error the rest of this document is about.

The claim was that `INT-US-03` **NFR-6** — *"the proof test MUST include the paired un-isolated
control asserting `failed == 1` (probe ran) to prevent a false green"* — had no such control,
because `grep -E "failed\s*==\s*1"` returned one unrelated hit in the whole test tree.

The control exists. It is `test_low_dal_project_runs_on_host_and_probe_fails` in
`tests/e2e/sandbox/test_implement_loop_worktree_isolation_e2e.py`, it runs a DAL_E project with
escalation off so the worktree probe fails at the real root, and it asserts:

```python
assert probe.result.output.get("failed") == 1, probe.result.output
```

The pattern missed it because the code reads `.get("failed") == 1` — the token `failed` is followed
by `")`, not by whitespace and `==`. Both tests in that file pass and neither skips.

**The lesson is the document's own thesis, self-inflicted:** a search that finds nothing is not
evidence of absence, it is evidence about the search. The requirement really was uncredited — but
because its citation was a bare `NFR-6` in a skip note (Finding 1's ambiguity), not because the test
was missing. Fixed by tagging the file `Proves: INT-US-03 FR-8, NFR-4, NFR-6.`

## Finding 3: a test 40x looser than the requirement

`E-EXEC-01` **NFR-2** — the design says *"< 5ms overhead per invocation"*; the only test asserts
*"< 200ms"*. It does not establish the requirement. Revoked earlier the same day, and the reason
it stayed hidden is worth keeping: a disclaimer in the test saying *"NFR-2 is deliberately NOT
claimed here"* re-credited it, because naming a requirement was enough to cite it.

## Finding 4: right number, wrong subject

`C-INTL-01` **FR-4** — cited from a sub-pipeline-cascade test; the design's FR-4 is the 10-test
quality battery over each component spec. Different subject, revoked.

## What survives, and what that is worth

127 credits stand. That means a test cites them and the citation is unambiguous — **not** that the
test proves them. Attribution is all any of this measures; strength is only answerable by mutation
testing (`A-VAL-03`). Four of the 123 were additionally checked against a stated numeric threshold
and passed.

The honest summary: this audit could rule credits **out** mechanically once ambiguity was defined,
and it read the residue by hand. It cannot rule them **in**.

## Left standing

- `B-EXEC-01` NFR-10 is `[proof: meta]` — a rule about test tiering, correctly outside the
  behavioural ledger; its "credit" here was an artefact of the census, not a claim.
- The 20 unattributed claims from `TECH-017` finding 6 are unrelated to this list and still need an
  owner.
- Restoring a revoked credit is not a documentation task. Each needs the citing test read against
  the requirement, then qualified or tagged — or a test written, where there is none.
