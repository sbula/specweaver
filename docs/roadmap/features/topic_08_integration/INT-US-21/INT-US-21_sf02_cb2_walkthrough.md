# Walkthrough: INT-US-21 SF-02 CB-2 — Stub Component Specs (FR-6)

- **Feature**: INT-US-21 — Autonomous Feature Decomposition (base integration contract)
- **Sub-feature**: SF-02 — Decomposition Artifacts & Frozen Seams
- **Commit boundary**: 2 of 3
- **Implementation plan**: `INT-US-21_sf02_implementation_plan.md` §Work Breakdown → CB-2
- **Date**: 2026-07-26

## What changed and why

CB-1 made the decomposition durable as YAML. CB-2 makes it *tangible*: one
`<component>_spec.md` per component, beside the feature spec, that a user can carry straight into
`sw implement`. This is D-INTL-02 §6.2's second unshipped promise.

| Change | Where | Why |
|---|---|---|
| `COMPONENT_NAME_PATTERN` | `decomposition_artifacts.py` | One constant for the stub writer *and* the fan-out guard. Two copies of a security regex is one copy too many |
| `load_component_template()` | same | Reads `.specweaver/templates/component_spec.md` as a **file**; local skeleton fallback for unscaffolded projects (R-3). Never imports `workspace/project` |
| `write_component_stubs()` | same | Never-overwrite; renders Jinja (D3); reports `created`/`skipped`/`rejected`/`failed` |
| `decomposition_artifacts.py` | new module | `decompose.py` hit 586 lines against a 450 threshold |

Stubs land at `spec_path.parent` per **D7**, not `project_path/"specs"`. The CB-2 step text said the
latter; D7 is the binding decision, and following the step text would split a feature from its
components whenever the spec lives outside `specs/`.

**A stub problem never fails the step.** By the time stubs are written the decomposition is paid for
and the artifact is durable. Discarding that because one component name was malformed or one file
was unwritable is the identical defect the CB-1 gate found in the lineage path. Never-overwrite
makes a re-run safe, the fan-out keeps its own hard name guard, and every non-created component is
named in the report rather than silently dropped (R/B C1.2).

## Three defects found while building it

### 1. Inherited, security-relevant — the name guard accepted a trailing newline

Extracting the regex forced a proper test of it, and Python's `$` **also matches immediately before
a trailing newline**. Verified before fixing:

```
'auth\n'  ->  True    #  ^[a-zA-Z0-9_\-]+$
'auth\n'  ->  False   #  ^[a-zA-Z0-9_\-]+\Z
```

`"auth\n"` is a legal POSIX filename and a log-injection vector, and it defeated the guard's own
stated intent. Shipped in the fan-out since `C-FLOW-03`. Now `\Z`.

**Traversal was never possible, and that is now verified twice over.** `/`, `\` and `.` are outside
the character class, *and* `Path.with_name()` raises `ValueError` on any separator — so even with
the regex removed entirely, a traversal name cannot produce a path. The regex is the primary guard
(a clean rejection rather than an errored step); `with_name` is the backstop. CB-1's red/blue pass
asserted "no traversal" from reasoning; this establishes it from execution.

### 2. Mine — Jinja `default()` does not fire on `None`

`{{ purpose | default("TODO…") }}` renders the literal **"None"** when `purpose=None` is passed
explicitly, because `default()` tests for *undefined*. A component with no description would have
had "None" written into its spec file where the placeholder belongs. The writer now passes only
variables that have values, so the shipped template and the fallback both behave as their author
intended. Caught by the test written for it.

### 3. Mine — `exists()` mislabelled an obstruction as a user file

The never-overwrite check used `target.exists()`, which is `True` for a *directory* at the stub
path — reporting `skipped`, i.e. claiming a user spec was there when none was. Now `is_file()`,
matching `DraftSpecHandler`'s exists-skip precedent, so an obstruction falls through to an honest
`failed`.

## The extraction

`decompose.py` reached **586 lines** (threshold 450). Split into `decompose.py` (369) and
`decomposition_artifacts.py` (249); repo-wide size warnings returned to their 35 baseline with zero
decompose-related entries.

Named for the contract it owns — the artifacts a decomposition produces — so it cannot accrete
unrelated helpers. **This is not `TECH-016`:** that ticket unifies the
derive→uuid→tag→write→lineage sequence *across* handlers and owns its own commits, which D5 forbids
inside a feature commit. This keeps the sequence local to decomposition and gives it a home; when
TECH-016 lands it replaces one function body and the stub writer stays put.

## Test results

| Tier | Count | Notes |
|---|---|---|
| Integration | 23 | FR-6 claims files on disk a user can carry forward — a mocked filesystem cannot show that |
| Unit | 27 | Name-regex table (16 hostile inputs) and template-fallback branches, which are awkward to reach through a step |

Full suite **5772 passed, 19 skipped, 0 failed** (from 5734).

### The full suite caught what the targeted run hid

The first full run failed one test — and the code was correct; the log showed the guard rejecting
`../../../etc/pwned`. **The broken assertion was mine:**

```python
assert not (tmp_path.parent / "etc").exists()
```

`tmp_path.parent` is pytest's *shared session root*, so an unrelated test created an `etc/` there.
In isolation it passed and proved nothing; in the full suite it failed for a reason unconnected to
its claim. That is vacuous-proof pattern 6 in a test written during a session spent hunting exactly
that. It now asserts the exact traversal target file plus the exact contents of the spec directory,
so no other test can collide with it. **A targeted green is not evidence; only the full suite is.**

### Non-vacuity probes — all four bite

| Probe | Result |
|---|---|
| `\Z` → `$` | 2 unit tests fail |
| `is_file()` → `exists()` | the obstruction test fails |
| Remove the Jinja `None` guard | the placeholder test fails |
| Bypass the name guard entirely | the traversal test fails |

Zero probe residue in the source, verified after restoration.

## Quality gates

ruff · mypy · `tach check` *All modules validated* · C901 · `check_file_sizes` 0 errors ·
`check_roadmap_sync` · `check_skill_sync` 26/0 — all clean.

`check_fr_coverage.py INT-US-21` still blocks on FR-9 only, whose test is CB-3 work.

## What CB-2 does NOT do

No stale-stub reconciliation — a re-decomposition that drops or renames a component leaves the old
file, reported as `skipped` rather than silently (R/B C1.2); reconciling is hand-edit arbitration
(`C-FLOW-05`/`B-INTL-07`). No plan-bridge seam pin or park rendering (FR-9(b), FR-7 summary → CB-3).
No CLI journey or e2e (FR-8/FR-10 → SF-03).

## Known gaps carried to CB-3

- A component listed twice in one plan: the second occurrence reports `skipped` because the first
  created the file. Correct behaviour, untested.
- `rejected` when a component dict has no `component` key at all (the `not name` half of the guard)
  is covered for `""` but not for a missing key.
