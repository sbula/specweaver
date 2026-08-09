---
description: "Shared test-quality reference: when a passing test is evidence and when it is not. Used by specweaver-dev (while writing tests) and specweaver-pre-commit (Phase 2, while auditing them)."
---

# Test Quality — when green means something

> Referenced by **`specweaver-dev`** (Phase 3, while writing tests) and
> **`specweaver-pre-commit`** (Phase 2 §2.5b, while auditing them). One home, two callers — this
> file is the source of truth for test *validity*; the skills own the *workflow*.

The 4-bucket adversarial matrix answers **what to test**. This answers the question that actually
bit us: **does a passing test prove anything?**

Every pattern below is a real defect found in this repository, with the story attached. None are
hypothetical.

---

## The eight vacuous-proof patterns

| # | Pattern | How to detect it |
|---|---|---|
| 1 | **Ambiguous exit code** — asserts `exit_code == 0` where two or more outcomes exit 0 | Which distinct end states share this code? PARKED and COMPLETED both exit 0 here. Assert the **persisted status**, never the process code |
| 2 | **Stubbed-away subject** — the test replaces the very thing under test | Grep for wholesale registry/handler substitution. If you double the component whose behaviour you are asserting, you asserted your double |
| 3 | **Never executed** — a skip guard that is always true | `if not path.exists(): pytest.skip(...)` with a wrong path skips forever. Compare skip counts before and after |
| 4 | **Fixture cannot satisfy the assertion** | Run the real subject against the fixture once and look at what it produces |
| 5 | **Escaped mock** — a "mocked" test reaching a real network or paid API | Look for alternative resolution paths that bypass the patch. Watch suite duration and quota errors |
| 6 | **Assertion weaker than the claim** — the name promises more than the assert checks | Read the name, then the asserts. "Flows through the whole chain" backed by one truthiness check is a gap |
| 7 | **Self-referential expectation** — the expected value is derived from the thing under test | *"If the implementation were wrong in the way this test names, would this test change?"* If no, it asserts nothing |
| 8 | **Subject never located** — the test runs, but the thing it inspects resolved to nothing | An absence proof over a real tree reports *clean* for a tree that does not exist. Call the locator with a deliberately wrong root: if it still reports clean, a moved test file or a renamed layout silently retires the proof while it goes on passing. Guard the inputs once, in one test, rather than restating them in every assertion |

### Pattern 4 has a subtle form: inert fixture input

The obvious version is a fixture whose values can never produce the asserted outcome. The subtle
version is a fixture field **the code never reads**.

`test_builder_ingest_ast_edge_delta` fed `{"type": "function_definition", "name": "foo",
"calls": ["bar"]}` to prove edge deletion. Nothing in `src/specweaver/graph/` reads `calls` — the
mapper builds edges from `children` only. No call edge was ever created, so the deletion path was
never entered, and both AST versions produced identical graphs. Combined with an
`assert len(edges) >= 0` (pattern 1's cousin: an assertion that cannot fail), the story it existed
to prove was unverified for the test's entire life.

**Check:** for each field your fixture sets, confirm the code under test actually consumes it.

### Pattern 7 is the most seductive

It looks rigorous. It references the right constant. It can never fail.

```python
# Claims to guard against re-hardcoding the suffix — but builds its expectation
# from the same constant, so a source hardcoding the identical literal passes.
assert resolved.name == f"onboarding{FEATURE_SPEC_SUFFIX}"
```

```python
# Class named "…SelectsTheFeatureBattery" that never invokes the selector,
# comparing two config files to each other instead.
assert len(feature.steps) == len(default.steps) - 1
```

Both were replaced with assertions on the property that matters — one definition repo-wide, and the
handler's actual behaviour (11 rules without `S04` for `kind=feature`, 12 with it as the control).

---

## Probe every fix — mandatory, not a tip

**Break the behaviour on purpose and confirm the test goes red.** If it stays green you have found
pattern 1, 2, 6 or 7.

This is cheap and it repeatedly paid:

- reverting `mode="json"` → 8 of 11 integration tests failed, proving the serialization fix
  load-bearing
- flattening a nested output key → exactly the 3 seam-agreement tests failed, and no others
- disabling a runner hook → exactly the 2 tests asserting the bridge failed, while the 2 asserting
  *absence* correctly stayed green
- disabling `if kind_str == "feature"` → *"kind=feature silently fell back to the default battery"*

Restore the probe immediately and **verify zero residue** before moving on.

A probe also tells you when a test is *broader* than you think: disabling edge removal in
`ingest_ast` did not fail its test, because node removal cascades and achieves the same outcome.
That is worth knowing and recording — it means one code path is exercised by nothing.

---

## Verify before "fixing"

A detector's finding is a **hypothesis**. Confirm it against the source before editing.

Of six hollow-test candidates flagged on 2026-07-26, **two were not defects**: one already used
`pytest.warns(..., match=...)` (the detector only looked for `raises`), and one was a pytest
**fixture** caught by the `test_` prefix — "repairing" it would have broken working code.

And a fix can over-assert. An early `assert len(edges) == 0` failed and nearly became a product-bug
report; the survivors were legitimate containment edges. The product was correct. **Every defect in
that sweep was in a test.**

---

## Detectors need the same proof as tests

A first hollow-test detector returned **630 candidates**, mostly noise from a rule that flagged any
CLI test asserting an exit code *plus* output text. Unusable — and dangerous, because a list that
long invites skimming.

The replacement reports only mechanically-decidable patterns and is itself tested against a
synthetic file containing one of each bad pattern **and** legitimate assertions that must not be
flagged (`tests/unit/scripts/test_check_test_quality.py`).

**A detector you cannot trust is as bad as a test you cannot trust.**

---

## Executable guards

These are checks, not advice, because advice gets skipped:

```bash
python scripts/quality.py cb --only useless_asserts,test_basenames
```

Both are registered in `scripts/quality.py` and run at every gate from `quick` upward, so the
full gate covers them too — `--only` is for when you want just these two while iterating on
tests.

`check_test_basenames.py` exists because duplicate basenames are not cosmetic: a truncated
reference search hid a twin file and stopped 5806 tests from collecting, minutes after a targeted
run reported green.

---

## Two workflow rules

**A targeted green is not evidence; only the full suite is.** Learned three separate ways in one
day: a targeted run passed while 5806 tests could not collect; a test passed in isolation and
failed in the suite because it asserted on pytest's *shared* session root; and a refactor's
targeted tests passed while two other files still imported the old symbol.

**The tree is frozen while a full suite runs.** A run whose source changed underneath it is not
evidence of anything — the same standard you apply to a test. Do read-only work, or wait.

**Never truncate a discovery search.** `head -N` on a grep meant to be exhaustive turns "I found
everything" into "I found the first few", with no visible difference. Use `head` for sampling,
never for "find every reference".
