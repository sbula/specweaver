# Walkthrough: TECH-075 SF-03 — The engine judges paths by where they land

- **Design**: [TECH-075_design.md](TECH-075_design.md)
- **Plan**: [TECH-075_sf03_implementation_plan.md](TECH-075_sf03_implementation_plan.md)

## CB-1 — FR-6 (mentions) and FR-8 (`relative_to_root`)

### What changed

- `core/flow/handlers/review.py`: `_resolve_mentions` asks `project_file` (SF-02's helper) for each
  candidate and skips a refused one. The private `_is_within` and the one-root loop are gone.
- `core/flow/handlers/archetype_pipelines.py`: `relative_to_root` returns `str | None`. It reads a
  relative path from the working folder (`path.absolute()`), lets the boundary resolve links, and
  answers `None` outside the root. `add_payload` then logs a WARNING, calls no atom, and gives every
  step an empty `ast_payload`.
- `core/flow/handlers/qa_targets.py`: `generated_code` answers `""` with a WARNING for a module
  outside the root, so an outside folder never goes on the tests' `PYTHONPATH`.
- `sandbox/security.py` (found during dev): `validate_path` turns an `OSError` or `RuntimeError`
  from `resolve()` into `WorkspaceBoundaryError`. Python 3.11 and 3.12 raise `RuntimeError` on a
  link loop, so a mention or an API path naming one crashed instead of being refused
  (`requires-python >= 3.11`; the suite runs 3.14, so the test forces the error).
- `security_guardrails.md`: the "One boundary" bullet names mentions, engine paths and the loop.

### Red first

- `test_engine_paths_stay_inside.py`, written before the change: 7 failed. Every outside case
  answered the full outside path; the structure atom received it; the outside module became the
  QA `source`.
- `test_security.py` loop case: failed with the raw `RuntimeError` / `OSError`.
- FR-6 (decision 4): today's `_is_within` already worked, so the new mention tests and
  `test_mentions_stay_inside.py` were green on the old code. The proof is the mutant
  `mention-unchecked`: 4 tests object.

### Plan deviation — audit #2 (hydrator) moved to CB-2, needs the user

The plan said `_hydrate_coverage` lets an escaping link pass. That was wrong.
`hydrate_code_validation_context` resolves `code_path` first (`validation_hydrator.py:96`), so
`relative_to` on it is already a component compare on the real location. Probed: a code file that
is a link to an outside file → FAILED, the atom is never called. The test file comes from
`rglob` under the project and goes to the QA atom as `target`, which SF-01 checks. Nothing to fix;
routing it through `relative_to_root` would be a refactor with no red. Held for the user's choice
at the SF-03 stop.

### Combined analysis

Architecture: `core/flow/handlers` → `core.flow.engine.project_paths` (same module);
`sandbox/security.py` changes no import. `tach check` clean. No parallel mechanism: the private
`_is_within` is removed.

| Function | Unit | Integration | E2E |
|---|---|---|---|
| `_resolve_mentions` | ✅ inside, dedup, cap, `../`, absolute, escaping link, link inside, blank, NUL | ✅ P-5 prompt seam | — |
| `relative_to_root` | — | ✅ inside, alias, root itself, relative, outside, escape, `..`, NUL | — |
| `add_payload` | — | ✅ inside → atom gets relative path; outside → WARNING, no atom; no project → file's folder | — |
| `generated_code` | — | ✅ inside, outside (WARNING names the file), not generated yet | — |
| `WorkspaceBoundary.validate_path` | ✅ unresolvable (`RuntimeError`, `OSError`) | — | — |

Composition: `relative_to_root` and `_resolve_mentions` do one job; 
`test_mentions_and_atom_paths_refuse_the_same_link` asserts they agree. `add_payload` → atom is
driven as a sequence. Gap stories added in Phase 3: the root itself, a module not yet generated,
no project, the WARNING naming the file. `useless_asserts`, `test_basenames`: pass.

Mutants (all OBJECTED, pinned in `TECH-075_mutants.json`): FR-1 `unresolvable-path-crashes`;
FR-6 `mention-unchecked`; FR-8 `outside-path-handed-on`, `relative-path-joined-to-root`,
`payload-reads-outside`, `outside-module-is-source`.

### Gates

- Full suite: 11356 passed, 9 skipped.
- `tests.py cb TECH-075 --kind bugfix`: unit and integration ok.
- `quality.py sf`: 18/18 after one fix (`lost_errors`: the `except ProjectPathError` now states its
  reason; the FR-8 mutant was re-pointed and re-run).

### Red/Blue (code)

- R1 (LOW) a `sw check` over many outside files logs one WARNING each. Accepted: it names the
  skipped file, which is the point.
- R2 (LOW) `validate_path` now raises `WorkspaceBoundaryError` where it raised `OSError`. Only the
  failure path changes; callers already handle the boundary error.
- R3 (LOW) a mention naming a folder: `is_file()` is false, skipped, as before.
- Cycle 2: no new finding. Below every threshold.
