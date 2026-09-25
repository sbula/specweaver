# E-VAL-05 — Suppression Ratchet (Gate-Bypass Census)

**Status**: STUB — not yet run through the `specweaver-design` skill · **Topic**: 05 (Validation
Engine) · **Feature ID**: E-VAL-05 · **Origin**: user-driven metric review, 2026-07-28, after
`ruff --select C901` reported clean on this repo while `--ignore-noqa` returned 20 errors including
a complexity-30 function.

## What it does

Counts every gate bypass (`# noqa`, `# type: ignore`, …) per file and per rule code, and fails when
the count rises. Every rule in the battery can be switched off from inside the file it judges; a
census of the bypasses is the only check that cannot itself be bypassed.

## Why

**Measured on SpecWeaver, 2026-07-28:**

```
ruff check src/ tests/ --select C901                 ->  exit 0, "All checks passed!"
ruff check src/         --select C901 --ignore-noqa   ->  Found 20 errors
```

Worst offenders under suppression, against a limit of 10: `handlers/decompose.py::execute` at
**30**, `cli_drift.py::drift_check_rot` at **20**, `engine/runner.py::_execute_loop` at **19**.
Every commit boundary in INT-US-21 reported "C901 clean" — true of the check, false of the code.

**Why a product capability, not repo hygiene.** For an LLM agent under a gate, **adding the
suppression is the cheapest correct solution to the stated constraint** — less work than fixing the
code, and it satisfies the gate exactly. The same pressure produces assertion-free tests under a
coverage rule (`C04`); that is why `check_useless_asserts.py` had to be written by hand. Once agents
run unsupervised on customer code, nobody reads each diff for a new `# noqa`. The census has to be
a rule.

## Scope (proposed)

Markers to census:

- `# noqa`, `# noqa: XXX` · `# type: ignore`, `# type: ignore[code]` · `# pragma: no cover`
- `# nosec` · `# pylint: disable=` · `@pytest.mark.skip`, `@pytest.mark.xfail`

Two independent signals, because they fail differently:

1. **Ratchet** — a frozen baseline count; the rule fails when the total rises. Never a zero target:
   that makes the rule unshippable on any real codebase and it gets disabled.
2. **Blanket-suppression ban** — a bare `# noqa` or bare `# type: ignore` with no rule code and no
   reason is rejected regardless of the count. Ruff's pygrep-hooks `PGH003`/`PGH004` implement
   exactly this and are not enabled here.

## Open decisions (not yet designed)

- **Home.** A `code`-tier rule in the existing registry (`rules/code/register.py`), inheriting
  `C-VAL-03`'s DAL machinery. Slot check (2026-07-28): registered IDs are `C01`–`C09`, `C12`,
  `C13`. `C10` is **reserved** — `B-VAL-03` names `C10_test_completeness.py`. `C11` is a gap with no
  claimant in `docs/` or `src/`; establish *why* (renumbering artefact vs. silent reservation)
  before taking it — an unexplained gap is how `TECH-009` acquired two meanings.
- **Baseline storage.** Must survive across runs and be diffable in review. A checked-in file is the
  obvious answer; open: per-repo vs per-module granularity.
- **Ticket link.** Does an approved suppression need a linked ticket ID in its reason string —
  enforced or advisory?

## Non-goals (proposed, pending design)

- **Not** removing any existing suppression. This ticket counts them; each site's own ticket fixes
  it.
- Not a new lint engine — it reads markers other tools left behind.
- **Not DAL-graduated.** This rule runs at every DAL including DAL-E and at every pipeline stage. It
  guards the rest of the battery; a rule that can be suppressed at DAL-E gives an agent a free
  bypass and makes the whole battery advisory.

**Next**: run `specweaver-design`. Build the rule against the two `ruff` commands above, and confirm
it goes red on the current tree before it may go green.
