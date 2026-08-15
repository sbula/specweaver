# TECH-049 SF-01 — Task List

Plan: `TECH-049_sf01_implementation_plan.md` · all unit tier · `scripts/_corpus.py`,
`tests/unit/scripts/test_corpus.py`

## CB-1 — Format, loader, validation

- [x] **T1** Corpus data model + JSON load. Rules 1–4 (schema known, `feature` matches the
      **filename stem** `<ID>_mutants.json`, campaign keys present, mutant keys present).
      `scripts/_corpus.py` · `tests/unit/scripts/test_corpus.py`
- [x] **T2** Rule 5 (`old != new`) and rule 6 (derived id `<feature> <requirement> <id>` unique in
      file). FR-1a. Same files.
- [x] **T3** Error messages name corpus file + campaign + mutant id. Asserted, not assumed (R-2).
      Same files.
- [x] **T4** `retired` campaigns parse and are counted, and skip rules 7–9 (rule 10).
      Same files.
- [x] **T5** `symbol_sha` is **optional**. Absent → `UNHASHED`, which is legal and not `STALE`.
      The normal authoring flow is a human writing a mutant without knowing the hash. Same files.

**Gate:** `tests.py cb TECH-049 --kind tooling` → pre-commit → HITL.
**Done when** the duplicate-id test kills a mutant: neutralise the uniqueness check and confirm
exactly that test goes red.

## CB-2 — Symbol resolution and hashing

- [x] **T6** Dotted symbol path resolution through direct bodies. Rule 8.
      Covers: module-level function, `Class.method`, absent segment, ambiguous at one level,
      module-level anchor rejected (Q5).
- [x] **T7** Docstring strip + `sha256(ast.dump(node))`. FR-2, Q1.
      Covers: reformat-stable, rename-sensitive, docstring-insensitive.
- [x] **T8** Rule 9 — anchor occurs exactly once **within the symbol's line range**; anchor outside
      the symbol rejected.
- [x] **T9** Drift state, returned as one of `OK` · `STALE` · `UNHASHED` on each mutant, for SF-02
      and SF-03 to consume. **Reported, never acted on here** — the shape is the seam, so it is
      named now rather than invented at the boundary.

**Gate:** `tests.py cb TECH-049 --kind tooling` → pre-commit → HITL.
**Done when** the docstring-insensitivity test kills a mutant on the strip step. It is the only
guard on Q1.

## CB-3 — Refresh and retire CLI

- [ ] **T10** `--refresh <derived-id>` — recompute and rewrite one mutant's `symbol_sha`, whether it
      was `STALE` or `UNHASHED`. One at a time; no bulk flag (R-3).
- [ ] **T11** `--retire <feature> <requirement> --reason "..."` — mark, never delete (Q4).
- [ ] **T12** Write-back preserves unrelated content byte-for-byte, and refreshing a mutant whose
      symbol is gone **fails** rather than writing a hash for nothing.

**Gate:** `tests.py cb TECH-049 --kind tooling` → pre-commit → HITL.
**Done when** a refresh round-trip leaves every other byte of the corpus file unchanged.

## Constraints carried from the plan

- `# fr-coverage: fixture-data` at the top of the test file; `Proves: TECH-049 FR-n` in the module
  docstring.
- No module-level `import specweaver` (NFR-7).
- `scripts/_corpus.py` stays under 451 lines (YELLOW); split the CLI out if CB-3 crosses it (R-5).
- Adversarial matrix per boundary: happy · boundary · degradation · hostile.
