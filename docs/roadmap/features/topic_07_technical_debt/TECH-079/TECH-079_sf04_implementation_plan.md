# Implementation Plan: Language and Toolchain Are Decided in a Dozen Places That Disagree [SF-04: One ending table, one parser lookup]
- **Feature ID**: TECH-079
- **Sub-Feature**: SF-04 — One ending table, one parser lookup
- **Design Document**: docs/roadmap/features/topic_07_technical_debt/TECH-079/TECH-079_design.md
- **Design Section**: §Sub-Feature Breakdown → SF-04
- **Implementation Plan**: docs/roadmap/features/topic_07_technical_debt/TECH-079/TECH-079_sf04_implementation_plan.md
- **Status**: APPROVED (the user, 2026-11-06)

## Scope

Every "which language is this file" and "which endings does this language have" reads `commons`;
`.h` follows the project; one parser lookup. FRs: **FR-12, FR-13, FR-15**. NFRs: NFR-1 (only tests
that pin a removed table change), NFR-2 (`commons` stays I/O-free), NFR-3 (no shims), NFR-5 (mutants
re-pointed). Path: P-8, and the table half of P-6 and P-7. SF-05 renames the style base and moves
Python style onto tree-sitter (FR-16, FR-17).

Today (measured 2026-11-06; paths under `src/specweaver`):

- **The table**: `commons/languages.py:14` `LANGUAGE_SUFFIXES` — python (.py .pyi), java, kotlin
  (.kt .kts), typescript (.ts .tsx), javascript (.js .jsx .mjs .cjs), rust, go, c (.c .h), cpp
  (.cpp .hpp .cc .cxx); `language_of(path)` lower-cases the ending.
- **Tables of their own** (FR-12):
  - structure analyzers `workspace/analyzers/factory.py`: `TreeSitterAnalyzerBase(parser, ext)`;
    `detect` and `extract_imports` glob `*{ext}`; one ending each (.py :258, .java :287, .kt :306,
    .rs :328, .ts :345), so a folder of `.kts`, `.tsx` or `.pyi` files gets no analyzer.
  - style analyzers `assurance/standards/languages/*/analyzer.py` `file_extensions()`: python
    `{.py}` (:77), typescript `{.ts .tsx .cts .mts}` (:40), javascript `{.js .jsx .cjs .mjs}`
    (:105). Picked by `assurance/standards/scanner.py:70-80` `ext_to_analyzer.get(path.suffix)`,
    case-sensitive.
  - `assurance/standards/scope_detector.py:33` and `recency.py:29` `_SOURCE_EXTENSIONS`: commons
    endings minus .pyi .mjs .cjs .cc .cxx (scope also minus .kts), plus their own .rb .cs .swift
    (.scala .clj in scope). Scope compares case-sensitively (:133), recency lower-cases (:140).
  - `workspace/project/interfaces/cli.py:84` `source_exts = {.py .js .jsx .ts .tsx}`: only for the
    `sw init` hint "run sw standards scan".
  - refactor resolvers' `SUFFIXES`: `python.py:50` `(.py,)` although rename sends `.pyi`;
    `jvm.py:105`, `typescript.py:90` and `:33` `_JS`, `go.py:78`, `rust.py:93`, `c_family.py:118`
    restate the table. `imports.py:31` index files `index{.ts .tsx .js .jsx}`.
  - `assurance/validation/orchestration/archetype_pipelines.py:119` `language_of(path) -> str`
    re-searches the table (bare ending as fallback); callers `core/flow/handlers/validation.py:323,
    324, 367`; `qa_targets.py:27` imports its `LANGUAGE_SUFFIXES` re-export.
  - language → main ending: `workflows/implementation/contract_renderers.py:34` `_EXTENSIONS`
    (already refuses an unknown language since SF-02); `sandbox/language/core/run_targets.py:20`
    `{java: .java, kotlin: .kt}`. (`detect.py:24` is gone since SF-02.)
  - the five generatable languages: `commons/project_profile.GENERATED_LANGUAGES` (the one),
    `core/config/implement_policy.py:17` `Language = Literal[...]`,
    `workflows/implementation/languages.py:18` `_LANGUAGES`.
- **`.h`** (FR-13): `commons` says C. The boundary check (`sandbox/language/core/boundary_check.py:97`)
  reads a `.h` target as C with the C resolver; rename starting at a `.h` picks `CResolver`
  (`refactor/rename.py:72`); `CppResolver` (`c_family.py:336-343`) reads `.h` as C++ when the rename
  starts at a C++ file. So one header is C in one tool and C++ in another.
- **Parser lookups** (FR-15), each `next(p for exts, p in get_default_parsers().items() if … in exts)`
  or a loop: `workspace/ast/adapters/graph_adapter.py:62` (case-sensitive),
  `graph/core/builder/orchestrator.py:156` collection (`p.suffix in suffixes`, case-sensitive),
  `boundary_check.py:113` (`target.endswith(exts)`, case-sensitive), `refactor/rename.py:72`
  `resolver_for` (`path.endswith`, case-sensitive), `sandbox/code_structure/core/atom.py:107` (its
  injected registry, lower-cased), `code_structure/interfaces/tool.py:497` and `refactor/files.py:37`
  (rebuild the registry on every call), `refactor/_base.py:31`, `refactor/imports.py:139`.
  `workspace/ast/parsers/factory.py:29` `get_default_parsers()` builds 11 parser objects per call.

## Decisions (Phase 4, the user 2026-11-06: all proposals taken)

| # | Decision |
|---|---|
| F1 | The analyzers' endings read `commons` in SF-04, with the guard test; SF-05 keeps the style-base rename and Python style on tree-sitter `[agreed 2026-11-06]` |
| F2 | `.cts` and `.mts` join `commons` typescript `[agreed 2026-11-06]` |
| F3 | `ImplementPolicy.language` is a `str` checked against `GENERATED_LANGUAGES`; the refusal still names the five `[agreed 2026-11-06]` |
| F4 | `refactor/imports.py` index files are built from the typescript and javascript endings `[agreed 2026-11-06]` |
| F5 | One registry per process; `get_default_parsers()` returns a read-only view (py-tree-sitter holds the GIL for a whole parse) `[agreed 2026-11-06]` |
| F6 | `parser_for(path, parsers=None)`; the code-structure atom keeps its injected registry `[agreed 2026-11-06]` |
| F7 | `commons.language_of(path, *, cpp_sources=False)`; the flag comes from the project's files the caller already holds `[agreed 2026-11-06]` |
| F8 | `commons.main_suffix(language)` (the first ending) replaces `contract_renderers._EXTENSIONS` and `run_targets._EXTENSIONS` `[agreed 2026-11-06]` |

## Architecture (Phase 3)

| Mechanism | Home | Allowed? |
|---|---|---|
| Endings, `language_of(path, cpp_sources=)`, `main_suffix` | `commons/languages.py` | yes: pure |
| `parser_for(path, parsers=None)`, the cached registry | `workspace/ast/parsers/factory.py` | yes: its own registry |
| Graph collection "can a parser read this?" | `workspace/ast/adapters/graph_adapter.py` (already exposes `parseable_suffixes`; `graph` may not import `parsers`) | yes |

No new tach edge: every caller already imports `commons` or `workspace.ast.parsers`.

## Commit Boundaries

**CB-1 — one parser lookup (FR-15).**
- `parser_for(path, parsers=None)` matches `language_of(path)` (plus `.md`, `.mdx`, `.sql`)
  case-insensitively; `get_default_parsers()` is built once and returned read-only (F5, F6).
- The 9 lookups call it; `graph_adapter` gains `parseable(path)` for the collector.
- Tests first: integration `tests/integration/workspace/ast/parsers/test_one_parser_lookup.py` —
  `A.PY`, `a.py`, `B.Java`, `x.TSX` get the same parser in each of the 9 lookups (through their
  public functions: `extract_ast_dict`, `collect_files`, the boundary check, `resolver_for`, the
  atom, the tool, `create_file`, a resolver, `targets_for`); a file no parser reads gets none; the
  registry is built once (same object twice). Red: `A.PY` misses in four lookups.
- Mutant: `parser_for` drops `.lower()` → the `A.PY` case objects.

**CB-2 — one ending table (FR-12).**
- `commons`: `.cts`, `.mts` (F2); `main_suffix` (F8).
- Read `commons`: structure analyzers (all endings of the language; `detect` and `extract_imports`
  glob each), style analyzers' `file_extensions()` and the scanner (lower-cased), `scope_detector`
  and `recency` (commons endings plus their own `.rb .cs .swift .scala .clj`), the `sw init` hint
  (the endings of the languages with a style analyzer), refactor `SUFFIXES` and `_JS`, the index
  files (F4), `archetype_pipelines.language_of` delegates, `qa_targets` imports `commons`,
  contract renderer and `run_targets` use `main_suffix`, `ImplementPolicy.language` and
  `languages._LANGUAGES` use `GENERATED_LANGUAGES` (F3).
- Guard: `tests/unit/commons/test_one_ending_table.py` parses every module under `src/specweaver`
  outside `commons` and fails on a string constant equal to `.pyi .kts .tsx .jsx .mjs .cjs .hpp
  .cc .cxx`.
- Tests first: a `.kts`-only and a `.tsx`-only folder get their structure analyzer; `A.TS` gets the
  style analyzer; rename of a Python symbol edits a `.pyi` stub; `scope_detector` sees `.cc`;
  `language = "go"` in `[implement]` is refused naming the five.
- Mutants: the Kotlin analyzer back to `.kt`; the guard's ending list emptied.

**CB-3 — `.h` follows the project (FR-13). Closes SF-04 (HITL).**
- `language_of(path, *, cpp_sources=False)`: `.h` is `cpp` when `cpp_sources`.
- The boundary check passes `cpp_sources` from the files it walked; rename and move pick the
  resolver with it (`CppResolver` for a `.h` in a C++ project); the parser registry's `.h` follows.
- Tests first: integration `test_header_follows_the_project.py` — in a C++ project a `.h` is read
  by the C++ parser in both the boundary check and rename; in a C project by the C parser in both.
  Red: the boundary check reads C.
- Mutant: `cpp_sources` ignored in `language_of` → the C++ project case objects.

## Research Notes

- py-tree-sitter 0.25.2: `Parser.parse` runs with the GIL held (the binding releases it only around
  `print_dot_graphs`), so a shared parser is never entered by two threads at once (context7,
  `tree-sitter/py-tree-sitter` architecture notes).
- `contract_renderers.contract_extension` already refuses an unknown language (SF-02).
- `rename.CODE_SUFFIXES` and `imports._SCRIPT_SUFFIXES` already derive from the table.

## Consistency (Phase 5)

- FR-15 → CB-1; FR-12 → CB-2 (with the guard); FR-13 → CB-3. NFR-1: tests that pin a removed
  table (`.kt`-only analyzer, `{.py}` style set, the `Literal` message) change; NFR-2: `commons`
  gains no I/O; NFR-3: `archetype_pipelines.LANGUAGE_SUFFIXES` re-export goes, no shim; NFR-5:
  mutants anchored in changed symbols are re-pinned and re-run.
- Red/blue, 2 cycles. Cycle 1: (HIGH) a cached registry shared with callers that set state on a
  parser — none found (`_base._parsers` only reads `type(default)`), the read-only view stops
  dict changes; (MEDIUM) `get_default_parsers` patched in tests by module path — the cache must be
  cleared between such tests, so `parser_for` reads the registry through `get_default_parsers()`
  each call (cheap once cached), never a module global; (MEDIUM) the guard must ignore docstrings
  and comments — it compares whole string constants from `ast`, so prose mentioning `.tsx` passes;
  (MEDIUM) case-insensitive collection in the graph could double-count `a.py` and `A.PY` on a
  case-insensitive disk — paths stay as found, only the match ignores case. Cycle 2: none above
  threshold.

## Backlog

None.
