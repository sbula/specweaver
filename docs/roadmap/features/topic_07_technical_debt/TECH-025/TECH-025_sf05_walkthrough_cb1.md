# Walkthrough: TECH-025 SF-05 CB-1 — two absence claims, proven without borrowing credit

- **Feature ID**: TECH-025 / SF-05 (TECH-002 FR Ledger)
- **Date**: 2026-08-11
- **Implementation Plan**: `TECH-025_sf05_implementation_plan.md` §3, §Commit Boundaries
- **Boundary**: CB-1 of 2. Ledger stays RED on purpose — this boundary answers *is the claim true?*,
  CB-2 answers *is it linked?*

## What changed

| File | Change |
|---|---|
| `tests/fixtures/arch_scanners.py` | **NEW** — `import_offenders(root, prefixes, *, recursive)`, the generalised AST scanner |
| `tests/unit/test_layer_import_isolation.py` | **NEW** — 15 tests, carries `Proves: TECH-002 FR-5.` and `FR-6.` |
| `tests/unit/test_architecture.py` | Scanner extracted; `config_orchestration_offenders` is now a thin caller |

## The finding that changed the plan

The plan put both invariants in `tests/unit/test_architecture.py`. That file **already names
`TECH-001`**, and `check_fr_coverage.cited_frs_in_tests` attributes whole-file — name the story,
then every `FR-N` token in the file is credited. Simulated before writing any code, by appending
only the two intended tags:

```
  6 FR(s) cited by tests naming TECH-002
  FR-4    NO PLAN  1 test file(s)     <- FALSE. TECH-002 FR-4 is "each domain facade inherits
  FR-5    NO PLAN  1 test file(s)         BaseTool"; the test crediting it asserts CLI commands
  FR-6    NO PLAN  1 test file(s)         live in their own domains.
```

Third appearance of the class SF-01 was built to prevent and SF-04 CB-3 caught in `TECH-022`.

**And the plan's own verification could not have caught it.** It checks TECH-001 stays 0 — it does,
because that file already cited its FR-5/FR-6. TECH-005 and TECH-022 stay 1 — they do. The only
ledger that moves is TECH-002, and it going green *is the declared goal*, so a borrowed citation and
a real one look identical from the exit code.

The invariants moved to a file naming exactly one story. Result after CB-1:

```
  2 FR(s) cited by tests naming TECH-002
  FR-4    NO PLAN  NO TEST      <- correctly still uncited; CB-2 will cite it from the file
  FR-5    NO PLAN  1 test file(s)    that genuinely proves it
  FR-6    NO PLAN  1 test file(s)
```

Exactly two, and they are the two this boundary earned.

## The two invariants are not symmetric, and the docstrings say so

Probed rather than assumed:

- **FR-5** — `tach` already enforces it. Planting
  `from specweaver.sandbox.registry import ToolRegistry` into
  `assurance/validation/rules/code/c03_tests_pass.py` makes `tach check` fail. The new test is the
  *citable* second proof: the test that runs `tach` carries no requirement tag and shells out to a
  bare `tach` binary, which is silently absent unless `.venv/bin` is on `PATH` — observed failing
  exactly that way this session.
- **FR-6** — **nothing enforces it.** `specweaver.interfaces` is not a declared module in
  `tach.toml`, so the boundary checker has no opinion. This test is the only guard.

Both docstrings state this, so neither gets deleted as a duplicate of the other.

## Pattern 8, not inherited

The plan's R4 claimed a proof placed in `test_architecture.py` "inherits the guard that its live
inputs actually exist". It does not — that guard asserts *its own* paths (the sandbox tree,
`core/config/*.py`, two llm modules) and covers neither new root. The new file writes its own, and
proves the failure mode rather than asserting it cannot happen:
`test_a_nonexistent_root_reports_clean_which_is_why_that_guard_exists`.

## The self-guard failed twice, which is why it is worth having

`test_this_module_carries_only_the_tokens_it_earns` asserts the file holds exactly two requirement
tokens and names exactly one story. It caught two real violations during development:

1. The first version spelled the two expected ids out in its assertion — reporting four tokens where
   two were expected.
2. The fix's explanatory comment quoted them while describing failure 1 — four again.

Both were genuine instances of the defect it exists to catch, in the file written to avoid it. Ids
are now assembled through a `_token()` helper, following SF-01's precedent.

## Probes

| Probe | Result |
|---|---|
| Mutate the scanner to `glob("*.py")`, dropping recursion | 2 tests fail — the recursion assertions are load-bearing |
| Point the scanner at a non-existent root | Reports clean — which is why the guard test exists |
| Plant a sandbox import in a real validation rule, run `tach check` | Fails — FR-5 has a second enforcer |
| `git stash -u`, re-measure `cycles` | 16 both ways — pre-existing, `TECH-024`'s |
| `git stash -u`, re-measure integration and e2e | 14 and 9 both ways — CB-1 introduces no regression in any tier |

## Gates

| Gate | Result |
|---|---|
| `tests/unit/test_layer_import_isolation.py` + `test_architecture.py` | 37 passed |
| `tests/unit -n auto` | 5582 passed, 6 failed — accepted Linux delta, no seventh |
| `tests/integration -n auto` | 576 passed, **14 failed** — identical on a stashed clean HEAD |
| `tests/e2e -n auto` | 182 passed, **9 failed** — identical on a stashed clean HEAD |
| `quality.py cb` | 9 passed; `complexipy` and `cycles` fail, both chronic and pre-existing |
| `check_fr_coverage` TECH-001 / INT-US-21 | exit 0 — unchanged |
| `check_fr_coverage` TECH-002 / TECH-005 / TECH-022 | exit 1 — correct, citations are CB-2 |

`complexipy` scans `src/` only and every file changed here is under `tests/`, so it cannot have been
affected; `cycles` measures 16 with and without the change. Both are registered as `TECH-023` and
`TECH-024` and are recorded rather than fixed, per pre-commit §1.8.

## HITL decisions taken during this boundary

| Gate | Presented | Outcome |
|---|---|---|
| Dev Phase 1 | Three open questions from the plan (scanner generalise-vs-duplicate; FR-5 citation home; citation grain) | All three plan recommendations confirmed |
| Dev Phase 2 | Task list + Red/Blue review, 8 findings, 1 CRITICAL | Approved, "start CB-1" |
| Pre-commit Phase 2 | Combined architecture + test-gap analysis: A2 (test-module import deviates from the `tests/fixtures/` precedent, 4 of 4) and gaps G1–G4 | *"move the scanner and close G1-G4"* — all actioned |

A2's fix is why `import_offenders` lives in `tests/fixtures/arch_scanners.py` rather than inside a
test module. G1–G4 added four tests: multi-prefix matching, the empty-tuple case (`str.startswith(())`
is always False — inherited behaviour, now chosen), sibling-relative imports, and the non-UTF-8 read
that raises `UnicodeDecodeError` outside the path-naming wrapper. The scanner's docstring was
narrowed to promise path-naming for parse errors only, which is all it delivers.

## Tier coverage — a gap found at the commit gate

The boundary gate was first run as `tests.py cb TECH-025 --kind tooling`, which reported unit only.
That is the profile, not an omission: `tests.py matrix` shows `TECH --kind tooling` selecting the
**unit tier at every state** — `quick`/`cb`/`sf`/`feature` — with no integration or e2e row at all.

Asked about the other tiers, the run was widened with `--all`, matching what SF-01 and SF-02 both
did at their own boundaries. It surfaced **14 integration and 9 e2e failures** that the default gate
would never have shown. A stashed clean HEAD produces exactly the same numbers, so none is this
boundary's doing — but the accepted-delta baseline recorded in `CLAUDE.md` had been written from the
unit tier alone and claimed 6 failures where the real figure across three tiers is **29**.

`CLAUDE.md` now carries per-tier baselines and the reason the other two were missed. The
integration/e2e cluster is git worktree / session isolation and is **not yet diagnosed**; it wants
the same accepted-or-fix decision the unit six already had.

**Carried into CB-2:** that boundary edits two files under `tests/integration/`, so `--all` is not
optional there — the default profile would not run the tier the change lands in.
