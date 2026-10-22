# Integration is implicit in the (sub)story

**Integration is implicit in the (sub)story. There is no integration story.** `ADR-005` retires
the `INT-US` family outright — `INT-US-NN`, `INT-US-NN-SFxx` and `-MIG` alike. Never mint one,
never reference one, not as a dependency and not as a tombstone.

**A test that cannot go RED proves nothing, and RED is only available before the code exists.**
A test written after the code is green on its first run: it asserts the present state instead of
a contract the code must satisfy. So the test comes first, and it gets the chance to fail.

**A (sub)story owns every test it needs, including the ones that span features.** If one feature
alone cannot prove it, the spanning test is still part of this (sub)story. It is not deferred, and
it is not handed to a separate entry.

**When a related (sub)story is unbuilt, write the test now anyway** and commit it as
`pytest.mark.xfail(strict=True)` naming the blocker. It fails today for the right reason.
`strict=True` makes an unexpected pass a failure, so the suite says so out loud the moment the
last related (sub)story lands. `check_xfail_blockers.py` fails any such marker whose named
blocker has become `✅`, so it cannot rot into a permanent exemption.

**The (sub)story is finished when those tests are green** — not when its own feature compiles.

**What integration actually is.** A feature's (N)FRs are not all local. Any FR whose satisfaction
needs something from outside — a call into another module, data handed across a boundary, a format
or schema both sides must agree on, an ordering, a shared file — is a **seam FR**: a hidden
contract with another feature. Those, and only those, are what a spanning test proves. Name them
as seams when you write the FR table, because a seam FR proven by a unit test with the other side
mocked proves the mock, not the contract.

**A missing spanning test under an already-finished (sub)story is a defect in delivered work**, so
it becomes a `TECH` ticket that owns the test and writes it red first. That is the rule for every
other defect in closed code.

**A cross-feature test is written when its interface is defined, not when the code lands**
(`ADR-004` clause 4). Where the implementation is absent, commit it as
`pytest.mark.xfail(strict=True, reason="blocked on <CAPABILITY-ID> ...")` — the blocker **must**
be named. `check_xfail_blockers.py` also fails any strict xfail whose reason names no blocker at
all — an unnamed one can never be judged stale and becomes a permanent exemption.
