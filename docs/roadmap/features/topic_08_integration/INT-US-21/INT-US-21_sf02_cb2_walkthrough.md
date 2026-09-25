# INT-US-21 SF-02 CB-2 — Walkthrough: Stub Component Specs (FR-6)

**Commit boundary:** 2 of 3 (`ce00be20`) · **Date:** 2026-07-26 · Plan:
[sf02](INT-US-21_sf02_implementation_plan.md) §Changes → CB-2

## Delivered

One `<component>_spec.md` per component, beside the feature spec, ready for `sw implement` —
D-INTL-02 §6.2's second unshipped promise.

| Change | Where | Why |
|---|---|---|
| `COMPONENT_NAME_PATTERN` | `decomposition_artifacts.py` | One constant for the stub writer *and* the fan-out guard |
| `load_component_template()` | same | Reads `.specweaver/templates/component_spec.md` as a **file**; local skeleton fallback for unscaffolded projects (R-3). Never imports `workspace/project` |
| `write_component_stubs()` | same | Never-overwrite; renders Jinja (D3); reports `created`/`skipped`/`rejected`/`failed` |
| `decomposition_artifacts.py` | new module | `decompose.py` hit 586 lines against a 450 threshold → `decompose.py` (369) + `decomposition_artifacts.py` (249); size warnings back to the 35 baseline |

- **Stubs land at `spec_path.parent`** (D7 — the plan's step text said `project_path/"specs"`).
- **A stub problem never fails the step** — the decomposition is paid for and the artifact durable.
  Never-overwrite makes a re-run safe, the fan-out keeps its own hard name guard, and every
  non-created component is named in the report (R/B C1.2).
- **Name guard is `^[a-zA-Z0-9_\-]+\Z`.** Python's `$` also matches before a trailing newline, so
  `"auth\n"` — a legal POSIX filename and a log-injection vector — passed the fan-out guard since
  `C-FLOW-03`. Traversal was never possible: `/`, `\` and `.` are outside the class, *and*
  `Path.with_name()` raises `ValueError` on any separator. The regex is the primary guard (a clean rejection);
  `with_name` the backstop. Verified by execution.

```
'auth\n'  ->  True    #  ^[a-zA-Z0-9_\-]+$
'auth\n'  ->  False   #  ^[a-zA-Z0-9_\-]+\Z
```

- **Only valued variables reach Jinja.** `{{ purpose | default("TODO…") }}` renders the literal
  **"None"** for an explicit `purpose=None` — `default()` tests for *undefined*.
- **`is_file()`, not `target.exists()`**, for never-overwrite (matching `DraftSpecHandler`'s exists-skip):
  a directory at the stub path is an obstruction → `failed`, not a false `skipped`.
- The module is **not `TECH-016`** (which unifies derive→uuid→tag→write→lineage *across* handlers,
  in its own commits, per D5). When TECH-016 lands it replaces one function body.

## Proof

| Tier | Count | Notes |
|---|---|---|
| Integration | 23 | FR-6 claims files on disk a user can carry forward |
| Unit | 27 | Name-regex table (16 hostile inputs) and template-fallback branches |

Full suite **5772 passed, 19 skipped, 0 failed** (from 5734).

| Non-vacuity probe | Result |
|---|---|
| `\Z` → `$` | 2 unit tests fail |
| `is_file()` → `exists()` | the obstruction test fails |
| Remove the Jinja `None` guard | the placeholder test fails |
| Bypass the name guard entirely | the traversal test fails |

Zero probe residue in the source, verified after restoration.

The traversal test (`../../../etc/pwned`) asserts the exact target file and the exact
spec-directory contents. A first version failed only in the full suite, because `tmp_path.parent`
is pytest's shared session root:

```python
assert not (tmp_path.parent / "etc").exists()
```

Only the full suite is evidence.

ruff · mypy · `tach check` *All modules validated* · C901 · `check_file_sizes` 0 errors ·
`check_roadmap_sync` · `check_skill_sync` 26/0 — all clean. `check_fr_coverage.py INT-US-21` still
blocks on FR-9 only (CB-3).

## Findings still open

- Stale stubs: a re-decomposition that drops or renames a component leaves the old file, reported as
  `skipped` (R/B C1.2); reconciling is hand-edit arbitration (`C-FLOW-05`/`B-INTL-07`).
- Carried to CB-3 (both closed there): a component listed twice reports `skipped` on the second
  occurrence — untested; `rejected` for a dict with no `component` key (the `not name` half) covered
  for `""` only.
