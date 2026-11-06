# Walkthrough: TECH-079 SF-04 — One ending table, one parser lookup

## CB-1: one parser lookup (FR-15)

**What changed**
- `workspace/ast/parsers/factory.py`: `get_default_parsers()` is built once per process (`@cache`)
  and returns a read-only `MappingProxyType` (F5 `[agreed 2026-11-06]`: py-tree-sitter holds the
  GIL for a whole parse, so threads sharing a parser never parse at once). New
  `parser_for(path, parsers=None)`: the ending, lower-cased, against the registry, or an injected
  one (F6).
- The nine lookups use it: `graph_adapter.extract_ast_dict`, the graph collector (through the new
  `graph_adapter.parseable(path)`, which replaces `parseable_suffixes`), the boundary check, the
  code-structure atom (its injected registry), the code-structure tool, `refactor/files.py`,
  `refactor/imports.targets_for`, `Resolver.parser_for` and `rename.resolver_for` (now a lower-cased
  dictionary lookup).
- The boundary check gets a note instead of a crash when no parser reads a target it named a
  language for (unreachable today; the type said so).

**What a user sees.** `A.PY`, `B.Java` and `x.TSX` are read like their lower-case names by the
graph, `sw check`'s boundary rule (C05) and rename; before, those three missed them and C05 raised.

**Tests**
- Red first: `tests/integration/workspace/ast/parsers/test_one_parser_lookup.py` (red: no
  `parser_for`; then `A.PY` missed in the graph, the boundary check and rename).
- Changed (NFR-1): two tests that injected a crashing parser by patching
  `graph_adapter.get_default_parsers` now patch `graph_adapter.parser_for`; same assertions.

**Mutants.** TECH-079 FR-15: `lookup-case-sensitive`, `registry-rebuilt`, `registry-writable`,
`resolver-pick-case-sensitive`, `graph-collects-by-old-rule`. 16 others (TECH-068, TECH-078,
TECH-082) re-pinned after their symbols changed, each re-run on its scope and objected.
`stale_mutants.py`: 0.

**Red/blue (2 cycles).** No finding above threshold. Checked: nothing in `src` writes into the
returned registry (`c_family` changes its own copy); `Resolver.parser_for` now raises `KeyError`
instead of `StopIteration` for an unknown ending and no caller catches either; collection matches
case-insensitively but keeps each path as found, so nothing is counted twice.

**Gate.** Full suite 12,596 passed, 9 skipped; `cb` 17/17; `doc` 14/14; tach OK; mypy clean.
`language_support_guide.md` says to use `parser_for`.

## CB-2: one ending table (FR-12)

**What changed**
- `commons/languages.py`: `.cts` and `.mts` join TypeScript (F2 `[agreed 2026-11-06]`);
  `main_suffix(language)` (F8).
- Read the table now: the structure analyzers (`TreeSitterAnalyzerBase(parser, language)`, files
  picked by `language_of`, so a `.kts`, `.tsx`, `.pyi` or `Main.JAVA` folder gets its analyzer —
  F1), the style analyzers' `file_extensions()` and the scanner (lower-cased), `scope_detector` and
  `recency` (the table plus their own `.rb .cs .swift .scala .clj`), the `sw init` hint (new
  `has_standards_code`: the languages `sw standards scan` reads), the refactor resolvers, the
  `index.*` package files (F4), `archetype_pipelines.language_of` (delegates; its
  `LANGUAGE_SUFFIXES` re-export is gone), `qa_targets`, the contract renderer and `run_targets`
  (`main_suffix`), `ImplementPolicy` (validators against `GENERATED_LANGUAGES` and `BUILD_TOOLS`,
  F3; the build tool had the same second copy) and the generation guides.
- Not in the plan: the refactor resolvers name `LANGUAGES` and the base class derives `SUFFIXES`
  from the table. The duplication gate flagged the repeated import blocks the first draft added to
  six resolvers; this removes the import and the per-class lookup.
- The TypeScript resolver resolves a bare import to `.ts`, then `.tsx` (`_BARE`), never `.cts` or
  `.mts`, as before.
- Guard: `tests/unit/commons/test_one_ending_table.py` fails on a string constant `.pyi .kts .tsx
  .jsx .mjs .cjs .hpp .cc .cxx` in any module outside `commons`; docstrings and comments pass.

**What a user sees.** `sw scan` and context inference find Kotlin build scripts, TSX and stub-only
folders; `sw standards scan` reads `A.TS` and `.pyi`; rename works from a `.pyi` stub; `sw init`
hints `sw standards scan` for an `.mjs` project.

**Tests**
- Red first: `tests/unit/commons/test_one_ending_table.py` (red: no `main_suffix`; the guard found
  seven modules), `tests/integration/commons/test_each_part_reads_the_ending_table.py` (red: no
  analyzer for `.kts`/`.tsx`/`.pyi`/`Main.JAVA`, `A.TS` unscanned, `.cc` unseen, no
  `has_standards_code`, rename from a stub failed). The index-file and `go`-refusal cases passed
  before and stay as agreement tests.
- Changed (NFR-1): the Python style analyzer's endings test (`{.py, .pyi}`), the parser-registry
  key test (TypeScript's four endings), the implement-policy agreement test (now reads every
  allowed value instead of comparing two lists). Added: a non-JVM file is no JVM test class.

**Mutants.** TECH-079 FR-12: `kotlin-analyzer-kt-only`, `style-scan-case-sensitive`,
`scope-own-list`, `init-hint-own-list`, `python-resolver-no-stub`. Re-anchored: D-INTL-08
`folders-filtered`, `empty-run-guard-python-only`; TECH-079 `contract-extension-unknown-is-py`,
`sw-init-writes-a-framework` (its symbol was a module constant `_corpus.py` cannot pin; now
`_scaffold_context_yaml`). `stale_mutants.py`: 0.

**Red/blue (2 cycles).** No finding above threshold. Checked: `language_of` for `.cts`/`.mts` now
says TypeScript everywhere (parsers, rename, a code-only root's profile), which is what F2 agreed;
the Python style analyzer reads `.pyi` with `ast`, which parses stubs; `CppResolver` inherits
`CResolver`'s `LANGUAGES`.

**Gate.** Full suite 12,629 passed, 9 skipped; `cb` 17/17 (duplication fixed, not re-frozen);
`doc` 14/14; tach OK; mypy clean.

**Slip, recorded.** During this boundary I ran `git stash list` inside a longer command; the output
was discarded and nothing changed, but the user had said never to run it.
