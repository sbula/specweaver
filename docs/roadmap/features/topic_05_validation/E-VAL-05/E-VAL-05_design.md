# Design: Suppression Ratchet (Gate-Bypass Census)

- **Feature ID**: E-VAL-05
- **Epic**: Topic 05 (Validation Engine)
- **Status**: STUB — not yet run through the `specweaver-design` skill
- **Origin**: User-driven metric review, 2026-07-28, after `ruff --select C901` reported clean on
  this repo while `--ignore-noqa` returned 20 errors including a complexity-30 function.

## Problem Statement

Every rule in the battery can be switched off from inside the file it judges. A census of the
bypasses is the only check that cannot itself be bypassed, and it does not exist.

**Measured on SpecWeaver itself, 2026-07-28:**

```
ruff check src/ tests/ --select C901                 ->  exit 0, "All checks passed!"
ruff check src/         --select C901 --ignore-noqa   ->  Found 20 errors
```

Worst offenders under those suppressions: `handlers/decompose.py::execute` at **30**,
`cli_drift.py::drift_check_rot` at **20**, `engine/runner.py::_execute_loop` at **19** — against a
limit of 10. Every commit boundary in INT-US-21 reported "C901 clean". True of the check, false of
the code.

**Why this is a product capability and not repo hygiene.** For a human author a `# noqa` is
laziness. For an LLM agent under a gate, **adding the suppression is the cheapest correct solution
to the stated constraint** — strictly less work than fixing the code, and it satisfies the gate
exactly. The same pressure produces assertion-free tests under a coverage rule (`C04`), which is
why `check_useless_asserts.py` had to be written by hand. An agent optimising "make C04 pass" is
behaving rationally; the battery is what has to be built for it.

Once agents run unsupervised on customer code, nobody is reading each diff for a new `# noqa`. The
census has to be a rule.

## In Scope (proposed)

Markers to census, per file and per rule code:

- `# noqa`, `# noqa: XXX` · `# type: ignore`, `# type: ignore[code]` · `# pragma: no cover`
- `# nosec` · `# pylint: disable=` · `@pytest.mark.skip`, `@pytest.mark.xfail`

Two independent signals, because they fail differently:

1. **Ratchet** — a frozen baseline count; the rule fails when the total rises. Not zero, ever;
   a zero target makes the rule unshippable on any real codebase and it gets disabled.
2. **Blanket-suppression ban** — a bare `# noqa` or bare `# type: ignore` with no rule code and no
   reason is rejected outright regardless of the count. Ruff's pygrep-hooks `PGH003`/`PGH004`
   already implement precisely this and are not enabled here.

## Candidate Approaches (not yet designed)

- A `code`-tier rule in the existing registry (`rules/code/register.py`), so it inherits
  `C-VAL-03`'s DAL machinery for free. **Slot check done 2026-07-28:** registered IDs are
  `C01`–`C09`, `C12`, `C13`. `C10` is **reserved** — `B-VAL-03` names `C10_test_completeness.py`
  explicitly. `C11` is a genuine gap with no claimant found anywhere in `docs/` or `src/`;
  establish *why* it is a gap (renumbering artefact vs. silent reservation) before taking it,
  because an unexplained gap is how `TECH-009` acquired two meanings.
- Baseline storage: needs to survive across runs and be diffable in review. A checked-in file is
  the obvious answer; the open question is per-repo vs per-module granularity.
- Whether an approved suppression needs a linked ticket ID in the reason string, and whether that
  is enforced or advisory.

## Non-Goals (proposed, pending design)

- **Not** removing any existing suppression. This ticket counts them; fixing them is separate work
  under the ticket that owns each site.
- Not a new lint engine — it reads markers other tools left behind.
- Not DAL-graduated. **This rule runs at every DAL including DAL-E and at every pipeline stage.**
  Everything else in the battery scales with criticality; this one cannot, because it is what
  guards the others. A rule that can be suppressed at DAL-E gives an agent a free bypass and makes
  the whole battery advisory.

## Next Step

Run the `specweaver-design` skill. The failing case is reproducible today on this repo with the two
`ruff` commands above — build the rule against that, and confirm it goes red on the current tree
before it is allowed to go green.
