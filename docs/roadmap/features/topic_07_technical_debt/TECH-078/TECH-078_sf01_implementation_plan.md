# Implementation Plan: Review, Validation and the API Still Assume Python [SF-01: One table of languages]
- **Feature ID**: TECH-078
- **Sub-Feature**: SF-01 — One table of languages
- **Design Document**: docs/roadmap/features/topic_07_technical_debt/TECH-078/TECH-078_design.md
- **Design Section**: §Sub-Feature Breakdown → SF-01
- **Implementation Plan**: docs/roadmap/features/topic_07_technical_debt/TECH-078/TECH-078_sf01_implementation_plan.md
- **Status**: APPROVED

## Scope

FR-6 (one table of file endings to languages, read by the six places that keep their own) and the
convention half of FR-3 (a code file's test file name and folder, per language, in one place that
`task_files_for` and — in SF-02 — the C02/C03 rules read). Kind `bugfix`. No dependency. NFR-1, NFR-2
apply.

## Research Notes

- **The six tables today** (read 2026-10-23):
  - `core/flow/handlers/archetype_pipelines.py:28` `LANGUAGE_SUFFIXES` — python `.py`; java `.java`;
    kotlin `.kt .kts`; typescript `.ts .tsx`; javascript `.js .jsx`; rust `.rs`; go `.go`; c `.c .h`;
    cpp `.cpp .hpp .cc .cxx`. Read by `qa_targets.py:26` (is a path code?) and the archetype rules.
  - `infrastructure/llm/prompt/constants.py:17` `_LANG_MAP` — fence labels; code: py, js, ts, rs, go,
    java (**no `.kt`, `.kts`, `.tsx`, `.jsx`, `.c`, `.cpp`**); non-code: md, yaml, yml, json, toml,
    html, css, sql, sh, bash, rb, xml, txt. `detect_language(path)` is imported by `prompt/adders.py`,
    `prompt_builder.py`, `prompt/adapter.py` (through `_prompt_constants.py`).
  - `sandbox/code_structure/core/atom.py:328` inline `lang_map` — py, java, kt, kts, ts, tsx, rs.
  - `workspace/ast/parsers/factory.py:30` `get_default_parsers()` — endings → parser objects, also
    `.md .mdx` and `.sql`.
  - `infrastructure/llm/_skeleton.py:30` — an `if/elif` on endings; `.js .jsx` use the TypeScript parser.
  - `workspace/ast/refactor/rename.py:49` `_RESOLVERS` (endings → resolver) and `:66` `CODE_SUFFIXES`
    (also `.pyi .mjs .cjs .sql`).
- **The test convention today** lives only in `core/flow/engine/task_files.py:57-86`: Python
  `tests/test_<stem>.py`; Java/Kotlin `src/test/<lang>/<pkg>/<Name>Test.<ext>`; TypeScript
  `tests/<stem>.test.ts`; Rust `tests/<m>.rs`. C02/C03 hard-code `test_<stem>.py` (SF-02 moves them).
- **Layering**: `commons` forbids every `specweaver/*` import (`commons/context.yaml`), has no `tach`
  rules, and is importable from `assurance`, `core`, `infrastructure`, `sandbox`, `workspace`.

## Decisions (Phase 4, user answered "A" 2026-10-23)

1. The table holds every ending of a programming language — `.pyi` (Python), `.mjs` / `.cjs`
   (JavaScript) join today's archetype list; SQL and markdown stay outside it, as the parser
   registry's and rename's own extras `[agreed 2026-10-23]`.

## Approach (pseudocode, ordered)

**The table** (`commons/languages.py` [NEW])
1. `LANGUAGE_SUFFIXES: dict[str, tuple[str, ...]]` — every programming language today's tables name,
   with all its endings (decision 1).
2. `language_of(path) -> str | None` — the language a file's ending names, else None.
3. The test convention: `TESTS_ROOT[language]` (`tests` / `src/test/<lang>`) and
   `test_file_name(code_name, language)` (`test_<stem>.py`, `<Name>Test.<ext>`, `<stem>.test.ts`,
   `<m>.rs`).

**Readers** (each drops its own copy)
4. `archetype_pipelines.LANGUAGE_SUFFIXES` → the commons table (kept as a name for its readers).
5. `task_files_for` builds each test path from the convention.
6. `prompt/constants.detect_language`: the commons language first, then the non-code labels; Kotlin
   becomes `kotlin`.
7. The code-structure atom: `language_of`.
8. `get_default_parsers`, `_skeleton`, `rename._RESOLVERS` / `CODE_SUFFIXES`: keys built from the
   table's endings per language; their own extras (markdown, SQL; JavaScript parsed as TypeScript)
   stay, named as extras.

## Proposed Changes

| File | Change |
|---|---|
| `src/specweaver/commons/languages.py` [NEW] | the table, `language_of`, the test convention |
| `src/specweaver/core/flow/handlers/archetype_pipelines.py` [MODIFY] | reads the table |
| `src/specweaver/core/flow/engine/task_files.py` [MODIFY] | test paths from the convention |
| `src/specweaver/infrastructure/llm/prompt/constants.py` [MODIFY] | code fences from the table |
| `src/specweaver/sandbox/code_structure/core/atom.py` [MODIFY] | `language_of` |
| `src/specweaver/workspace/ast/parsers/factory.py`, `infrastructure/llm/_skeleton.py`, `workspace/ast/refactor/rename.py` [MODIFY] | endings from the table |
| `src/specweaver/commons/context.yaml` [MODIFY] | exposes the new names |

## Test Plan

| FR | Tier | Test file | Cases (bucket) |
|---|---|---|---|
| FR-6 | unit | `tests/unit/commons/test_languages.py` [NEW] | each language's endings name it, upper-case endings too (happy, boundary); an unknown or empty ending is None (degradation); a path whose folder looks like an ending (`a.py/b`) is judged by its own ending (hostile) |
| FR-3 | unit | same file | each language's test name and root from a code name (happy); a stem with dashes for Rust (boundary) |
| FR-6 | integration | `tests/integration/test_one_language_table.py` [NEW] | the six readers agree with the table on every ending it holds: the fence label, the atom's language, the parser chosen, the skeleton parser, the rename resolver, the archetype match (agreement); Kotlin is fenced `kotlin` (the defect) |
| FR-3 | integration | same file | `task_files_for`'s test path for each language is the convention's (agreement) |

Expected reds: the module does not exist; the fence for `.kt` is `text`; the atom has no `.cpp`;
the agreement test fails on every table that lacks an ending another has.

Mutants: an ending dropped from the table (FR-6); the fence reader skips the table (FR-6); the
Kotlin test name loses `Test` (FR-3); `task_files_for` builds its own Python test name (FR-3).

## Commit Boundaries

| CB | Tasks | Done when |
|---|---|---|
| CB-1 | the commons table and convention; `archetype_pipelines`, `task_files_for` read them | green; FR-3 mutants killed |
| CB-2 | fences, the atom, parsers, skeleton, rename read the table; the agreement test. Closes SF-01: stops for the user's acceptance | green; FR-6 mutants killed |

## Documentation

`docs/dev_guides/language_support_guide.md`: a new language is one row in `commons/languages.py`
and its test convention.

## Audit (Phase 2) — answered: A, 2026-10-23

| # | Question | Options | Proposal | Severity |
|---|---|---|---|---|
| 1 | Today's tables disagree on endings that are clearly one language: `.pyi` (Python), `.mjs` / `.cjs` (JavaScript) appear only in rename's list. Adding them to the one table also makes them count as code where the archetype rules and QA ask "is this code?". `.sql` and markdown are in the parser and rename lists but are not languages an archetype names. | A: the table holds every ending of a programming language (`.pyi`, `.mjs`, `.cjs` added); SQL and markdown stay outside it, as their readers' own extras. B: the table holds only the archetype list as it is today; the extra endings stay in rename's own list. | A — one place says what `.pyi` is; the extras that are not languages stay where they are used | LOW |

## Architecture Verification (Phase 3)

| Change | Module · archetype | I/O & state | Execution | LLM | Dependencies | Domain | Verdict |
|---|---|---|---|---|---|---|---|
| `commons/languages.py` | `commons` · raw-data | none (pure) | none | none | none | shared vocabulary | ok |
| six readers | their modules | unchanged | unchanged | unchanged | + `commons` (allowed everywhere) | unchanged | ok |

No cycle: `commons` imports nothing of SpecWeaver.

## Consistency Check and Red/Blue (Phase 5)

- **Coverage**: FR-6 (CB-1 table, CB-2 the six readers), FR-3's convention (CB-1; SF-02 moves the
  rules onto it). NFR-1: Python's endings and test name do not change. NFR-2: `commons` imports
  nothing; `tach check` and its `forbids: specweaver/*` hold.
- **Open questions**: none. All decisions are resolved and documented inline in the plan.
- **Handoff risk**: (a) TypeScript's test name stays `<stem>.test.ts` for a `.tsx` file too, as
  `task_files_for` writes it today. (b) `_skeleton` keeps parsing JavaScript with the TypeScript
  parser — an extra, not a table row. (c) `archetype_pipelines.LANGUAGE_SUFFIXES` stays as a name
  bound to the commons table, so its readers need no change.
- **Architecture**: one new pure module at the bottom; every link points down to it.
- **DDD/KISS/DRY/hexagonal/SoC**: six copies become one; each reader keeps only what is its own.
- **Code detail limit**: no code block; pseudocode only.
- **Red/Blue**, 2 cycles:
  - R1 (MEDIUM) `.pyi`, `.mjs`, `.cjs` now count as code where QA asks. Blue: decision 1; they are
    code.
  - R2 (LOW) fence labels change for `.c`, `.cpp`, `.jsx`, `.tsx` (from `text`). Blue: the intent
    of FR-6; the labels are the language names.
  - R3 (LOW) the parser registry's tuple keys are rebuilt; lookups take the first match. Blue: no
    two languages share an ending, which the unit test asserts.
  - Cycle 2: no new finding. Below every threshold.
