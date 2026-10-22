# Test tier must match the claim

**TEST TIER MUST MATCH THE CLAIM (`TECH-017`, `ADR-003`).** Tier is chosen per requirement, not
per story type: behaviour of this module alone → **unit**; a **seam** (calling, reading or
persisting through another module) → **integration**; a user-visible journey across capabilities →
**e2e**.

`ADR-003` folded integration into the story that creates the seam, so if your commit boundary
touches another module's surface, **this boundary owns that integration test** — no later story
will write it. Where step *n*'s interface depends on step *n−1*'s output, write the seam test
BETWEEN the two: that is the only moment it can fail for the right reason. Note the red and its
reason in the walkthrough.

**This binds the e2e too.** A journey test written once the journey already works cannot fail for
the right reason either, so the e2e is authored in **3.1 Red like any other test** — before the
wiring it exercises — and turned green inside the same boundary. The tier profile in
`scripts/tests.py` decides which tiers **run** at this commit state; it never decides when a test
is **written**, and "the profile runs e2e later" is not a reason to author it later.

`ADR-003`'s worked example is `C-EXEC-06` FR-8: an e2e whose **pipeline** step 1 generates a file
a later **pipeline** step consumes. Note which "steps" those are — they are steps inside the test,
not commit boundaries. Multi-step is what makes the journey falsifiable; it does not license a
test that stays red past its own commit.

**If the journey genuinely cannot go green inside one boundary**, that is a finding about the
boundaries, not a red to carry: the plan drew them so a user-visible journey spans several. Raise
it — redraw the boundary, or descope the e2e to the journey that IS complete here. Do not commit
a red, and do not `skip`/`xfail` it to green: a silent skip is the failure mode
`check_proof_tier.py` and `_silent_skips.py` exist to catch.

Writing many unit tests where a seam was expected is a **diagnostic**: the capability you build on
shipped incomplete, and that is a finding against *it*, not tests to adopt under your own name.
Before Phase 2, check whether a CLI surface already works well enough for an e2e: an explicit spec
path often works long before bare-name resolution does.
