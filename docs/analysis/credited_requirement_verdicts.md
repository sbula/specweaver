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
| Survive the audit | **123** |
| **Revoked — the credit was never evidence** | **29** |

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
make the claim checkable. 29 credits fell away:

| Story | Requirements revoked | n |
|---|---|---|
| `B-EXEC-01` | FR-2, FR-3, FR-5, FR-7, NFR-1, NFR-2 | 6 |
| `INT-US-02` | FR-2, FR-4, NFR-2, NFR-3, NFR-5 | 5 |
| `INT-US-09` | FR-3, FR-5, NFR-1, NFR-2, NFR-6 | 5 |
| `C-EXEC-06` | FR-5, FR-7, NFR-1 | 3 |
| `INT-US-03` | FR-5, NFR-1, NFR-2 | 3 |
| `INT-US-21` | NFR-3, NFR-6, NFR-8 | 3 |
| `INT-US-24` | FR-5, NFR-5 | 2 |
| `TECH-006` | NFR-6, NFR-8 | 2 |

`B-EXEC-01` is the worst hit and the least surprising: it is the container-executor contract, and
its requirements were being "proved" by the settings-loader and CLI-config tests, which mention it
in passing while testing worktree isolation.

## Finding 2: the requirement that exists to prevent a false green is itself unproven

`INT-US-03` **NFR-6** — *"Determinism of proof: the proof test MUST include the paired un-isolated
control asserting `failed == 1` (probe ran) to prevent a false green."*

Its credit came from a skip-condition note (*"Requires only git + bash; skips cleanly otherwise
(NFR-6 / NFR-4)"*). Searched for the control it demands: **`failed == 1` appears once in the whole
test tree, in `test_python_runner.py`, unrelated to worktree isolation.** The paired control does
not exist.

So the isolation e2e can pass without ever demonstrating the probe ran — exactly the false green
NFR-6 was written to prevent. Recorded, not repaired: writing that control is real test work and
belongs to whoever owns `INT-US-03`, not to the audit that found it.

## Finding 3: a test 40x looser than the requirement

`E-EXEC-01` **NFR-2** — the design says *"< 5ms overhead per invocation"*; the only test asserts
*"< 200ms"*. It does not establish the requirement. Revoked earlier the same day, and the reason
it stayed hidden is worth keeping: a disclaimer in the test saying *"NFR-2 is deliberately NOT
claimed here"* re-credited it, because naming a requirement was enough to cite it.

## Finding 4: right number, wrong subject

`C-INTL-01` **FR-4** — cited from a sub-pipeline-cascade test; the design's FR-4 is the 10-test
quality battery over each component spec. Different subject, revoked.

## What survives, and what that is worth

123 credits stand. That means a test cites them and the citation is unambiguous — **not** that the
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
