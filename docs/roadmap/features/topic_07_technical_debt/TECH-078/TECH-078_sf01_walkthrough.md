# Walkthrough: TECH-078 SF-01 — One table of languages

Plan: [TECH-078_sf01_implementation_plan.md](TECH-078_sf01_implementation_plan.md).

## CB-1 — the table, the test convention, and four of the six readers (FR-6, FR-3)

### What changed

- `commons/languages.py` [NEW]: `LANGUAGE_SUFFIXES` (every ending of each programming language;
  `.pyi`, `.mjs`, `.cjs` added, decision 1), `language_of(path)`, and the test convention
  `root_of_tests(language)` / `name_tests_for(code_name, language)`. Named so pytest never collects
  them (`test_*` names would be).
- Readers: `archetype_pipelines.LANGUAGE_SUFFIXES` is the table; `task_files_for` builds every test
  path from the convention; the parser registry and rename build their keys from the table, with
  markdown and SQL kept as their own extras.
- Deviation from the plan: the parser registry and rename moved from CB-2 into CB-1. With `.pyi` in
  the table, two existing tests (`test_every_language_has_a_parser`, the rename/parser agreement)
  went red until both read it; a boundary may not commit red.

### Red first

`test_language_table.py`: collection error (no module). `test_one_language_table.py`: the archetype
rules lacked `.pyi`, `.mjs`, `.cjs`. The `task_files_for` cases were green from the start (the
convention already matched); their proof is the mutant `task-files-own-python-name`.

### Tests changed

`test_parsers_factory.py` looks Python's parser up under `(".py", ".pyi")`. The new unit file is
`test_language_table.py` (the basename guard refused a second `test_languages.py`).

### Mutants

New, OBJECTED and pinned: `upper-case-ending-unknown`, `parsers-own-endings` (FR-6),
`kotlin-test-loses-Test`, `task-files-own-python-name` (FR-3). Drifted: 0.

### Gates

Full suite 11588 passed, 9 skipped. `quality.py sf` 18/18. `tach check` clean.

### Red/Blue (code)

- R1 (LOW) `.pyi`, `.mjs`, `.cjs` now count as code for the archetype match and QA. Decision 1.
- R2 (LOW) a mutant cannot pin a module-level dict (`pin` takes functions and classes), so the
  table's own rows are proven through `language_of` and the parser registry.
- Cycle 2: no new finding.
