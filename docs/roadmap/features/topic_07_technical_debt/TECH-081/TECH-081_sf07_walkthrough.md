# Walkthrough: TECH-081 SF-07 — Pure-logic and contract modules do no I/O

Plan: [TECH-081_sf07_implementation_plan.md](TECH-081_sf07_implementation_plan.md).

## CB-1 — the context writer leaves the contract module (FR-19)

### What changed

- `ContextInferrer` moved whole from `workspace/context/inferrer.py` to
  `workspace/analyzers/inferrer.py`. `assurance/graph/topology.py` and
  `workspace/project/interfaces/cli.py` import the new path.
- Tests moved: `test_inferrer.py` to `tests/unit/workspace/analyzers/`; `test_exposes_seam.py` and
  `test_scan_and_infer.py` to `tests/integration/workspace/analyzers/`.
- `tach.toml`: the `inferrer` expose moved from `workspace.context` to `workspace.analyzers`;
  `workspace.project.interfaces` no longer depends on `workspace.context` (unused report). The
  analyzers manifest exposes `inferrer`; the project interfaces manifest drops the edge.
- `B-SENS-03` corpus scope re-pointed. 0 stale mutants.
- `test_logging_rollout.py` imports `inferrer` from its new module. That one edit makes the
  boundary kind `tooling` `[agreed 2026-10-28]`.

### Red first

None of its own: a move proven by the existing tests (plan R5). CB-3's purity guard is the check
that keeps `workspace/context` free of I/O.

### Gate notes

Full suite 11834 passed, 9 skipped; `tests.py cb --kind tooling`, `quality.py cb`, `doc`,
`tach check` green. The `refactor` gate refused the logging test's import split.

### Red/Blue (Phase 7.5), 2 cycles

- R1 (MEDIUM) `workspace/analyzers` now writes files. Blue: it is an `adapter` that already reads
  them; the design puts the writer there (AD-12).
- R2 (LOW) `D-SENS-01_design.md:32` names the old path. Blue: a finished story's design records its
  own time; it is not edited.
- R3 (LOW) an empty `tests/integration/workspace/context/` with only `__pycache__` stays on disk.
  Blue: git does not track it; nothing collects from it.
- Cycle 2: no new finding.

## CB-2 — the validation readers move to `assurance/validation/io` (FR-18)

### What changed

- New tach module `specweaver.assurance.validation.io` (archetype `adapter`), depending on
  `assurance.validation` and `core.config`. Its manifest and tach expose list name the two readers.
- `pipeline_loader.py` moved whole to `io/pipeline_loader.py`; `rubrics/loader.py` to
  `io/rubrics.py`, whose `_SHIPPED_DIR` points at the `rubrics/` data folder. `rubrics/__init__.py`
  re-exports nothing; the folder keeps the shipped `.md` files.
- `assurance.validation` no longer exposes the readers; it exposes `inheritance.resolve_pipeline`,
  which the pipeline reader calls. The validation manifest equals the tach list.
- Callers import the new path: `interfaces/api/v1/validation.py`,
  `core/flow/handlers/archetype_pipelines.py` and `review.py`, `core/config/interfaces/cli.py`,
  `assurance/validation/interfaces/cli.py`. Their modules depend on `assurance.validation.io`;
  `core.config.interfaces` lost its unused `assurance.validation` edge.
- 24 test files re-pointed (import paths; ruff re-sorted six import blocks).
  `test_logging_rollout.py` imports `pipeline_loader` from `io`, so the kind is `tooling`, as in
  CB-1.
- `developer_guide.html` names the new path.
- Mutants: the five `C-VAL-05` mutants point at `io/rubrics.py`; those and four others whose
  symbol held a re-pointed import (`C-FLOW-06` `dal-ignored`, `B-INTL-01` x2, `TECH-075`
  `check-name-not-bare`) were re-run, all OBJECTED, then re-pinned one by one. 0 stale.

### Red first

Registering the module and shrinking the expose list first turned `tach check` red on all nine
caller imports.

### Gate notes

Full suite 11834 passed, 9 skipped; `tests.py cb --kind tooling`, `quality.py cb` (after the
import re-sort), `doc`, `check_proof_tier.py`, `tach check`, mypy green.

### Red/Blue (Phase 7.5), 2 cycles

- R1 (MEDIUM) a package named `io` beside `import io` in `pipeline_loader.py`. Blue: absolute
  imports resolve the stdlib; `io.StringIO` runs in every pipeline test.
- R2 (MEDIUM) `from ...validation.rubrics import load_rubric` now fails. Blue: grep finds no user;
  mypy covers `src`.
- R3 (MEDIUM) the shipped rubrics must still be found and packaged. Blue: the files did not move;
  hatchling ships every file in the package; `test_rubrics.py` loads them. CB-3 adds
  `rubrics-from-old-dir`.
- R4 (LOW) `validation` exposes one more name. Blue: only `io` uses it, and `io` depends on
  `validation`, not the other way.
- Cycle 2: no new finding.

## CB-3 — the guard holds both labels (FR-18, FR-19) — closes SF-07

### What changed

- `test_pure_modules_do_no_io.py` reads `commons`, `assurance/validation` and `workspace/context`.
  A sub-folder whose own `context.yaml` names another archetype (`io/`, `interfaces/`) is not read;
  a pure one (`rules/`) is. Three files may do I/O while the ledger names them (`project_root.py`,
  C09, S04); a new test fails when one has no ledger row, another when one does no I/O any more.
- `assurance/validation/loader.py` and `test_loader.py` deleted (AD-11); `loader` left the expose
  list, the manifest, `registry.py`'s docstring, `test_logging_rollout.py` and the developer guide.
- Ledger rows for C09 and S04 (DEFERRED, Q1 `[agreed 2026-10-28]`).
- `D-VAL-02` FR-3 ("a project's own rules run") removed from its design with the reason: the loader
  had no caller in `src`, so it never ran `[agreed 2026-10-28]`. The topic entry says so.
- `ValidationStep.path` (the custom rule file the loader read) removed, with its copies in
  `executor.py` and `inheritance.py` `[agreed 2026-10-29]`. A pipeline file that still has `path:`
  loads; the key is dropped (two new tests).

### Red first

The widened guard failed on `loader.py` (`is_dir`, `glob`), and the ledger test on C09 and S04.
Deleting the loader first turned the FR sweep red (29 → 30 uncited): `test_loader.py` was
`D-VAL-02` FR-3's only proof. The user chose to remove the FR.

### Proof

Mutants `validation-reads-again` (FR-18, `pipeline.py` opens a file), `context-writes-again`
(FR-19, `provider.py` writes one), `rubrics-from-old-dir` (FR-18, the shipped rubrics looked for
beside the reader), `dead-path-field-back` (FR-18, the field returns): all OBJECTED. 0 stale.

### Gate notes

Full suite 11829 passed, 9 skipped (the loader's tests went; guard and path tests came);
`tests.py cb --kind tooling`, `quality.py cb`, `doc`, `check_proof_tier.py`, mypy, `tach check`
green.

### Red/Blue (Phase 7.5), 2 cycles

- R1 (MEDIUM) the guard reads archetypes from `context.yaml`, so relabelling a folder `adapter`
  hides its I/O. Blue: the label is the claim; `test_manifests_match_tach` and review hold the
  labels, and this test then checks the code against them.
- R2 (MEDIUM) `ValidationStep.path` was left with nothing to load it. Blue: removed in this
  boundary; old pipeline files still load (pydantic drops unknown keys).
- R3 (LOW) aliased I/O passes the guard. Blue: unchanged limit, stated in the docstring.
- Cycle 2: no new finding.
