# Implementation Plan: Language and Toolchain Are Decided in a Dozen Places That Disagree [SF-05: Analyzers on one base]
- **Feature ID**: TECH-079
- **Sub-Feature**: SF-05 — Analyzers on one base
- **Design Document**: docs/roadmap/features/topic_07_technical_debt/TECH-079/TECH-079_design.md
- **Design Section**: §Sub-Feature Breakdown → SF-05
- **Implementation Plan**: docs/roadmap/features/topic_07_technical_debt/TECH-079/TECH-079_sf05_implementation_plan.md
- **Status**: APPROVED (the user, 2026-11-06)

## Scope

SF-05 closes FR-16, FR-17 and FR-18 (added 2026-11-06, Q6). SF-04 already did the half of FR-16 that reads endings from `commons`
(both families, guard test). What is left:

- **FR-16, the name.** The style base `TreeSitterAnalyzer` (`assurance/standards/tree_sitter_base.py:31`)
  becomes `TreeSitterStyleAnalyzer`. Its users: `languages/javascript/analyzer.py:19,99` (TypeScript
  inherits from JavaScript) and `tests/unit/assurance/standards/test_tree_sitter_base.py`. The
  structure base `TreeSitterAnalyzerBase` (`workspace/analyzers/factory.py`) keeps its name.
- **FR-17, the parser.** `PythonStandardsAnalyzer` (`languages/python/analyzer.py:70`) parses with the
  standard library `ast`. It becomes a `TreeSitterStyleAnalyzer` on `PythonCodeStructure().parser`
  (`workspace/ast/parsers/python/codestructure.py`), and gives the same six category results
  (naming, error_handling, type_hints, docstrings, import_patterns, test_patterns) on a fixture set
  that is pinned first.
- **Copies that go with it.** `_file_weight` is in the base and in the Python analyzer;
  `_compute_confidence` is in the Python and the JavaScript analyzer; JavaScript imports the private
  `_classify_name` from the Python analyzer. They move to the base module once.

## Decisions (Phase 4, the user 2026-11-06: all proposals taken)

| # | Decision |
|---|---|
| Q1 | A Python file that starts with a UTF-8 byte order mark (BOM) is read by the style check. Today `read_text` keeps the mark, `ast.parse` fails and the file is skipped (measured); every tree-sitter grammar reads it (measured for all 8) `[agreed 2026-11-06]` |
| Q2 | A file with a syntax error stays skipped: the Python style analyzer skips a tree whose root `has_error`; JavaScript and TypeScript keep reading such trees, as today `[agreed 2026-11-06]` |
| Q3 | `classify_name`, `compute_confidence` and `_file_weight` live once in `tree_sitter_base.py`; the Python and JavaScript analyzers use them `[agreed 2026-11-06]` |
| Q4 | The file `tree_sitter_base.py` keeps its name; only the class is renamed `[agreed 2026-11-06]` |
| Q5 | The tests of the private `_parse_file` (`test_python_analyzer.py:462,473`) test the same two facts through `extract_all`: a broken file is skipped, bad bytes are still read `[agreed 2026-11-06]` |
| Q6 | The same BOM bug fails C01 (and makes C06, C08 skip) on a valid Python file on every door of `sw check`, the API check and the validate steps (measured: "Syntax error at line 1: invalid non-printable character U+FEFF"). SF-05 fixes it: the code rules' Python parse drops one leading BOM, as Python does for a file on disk; a BOM later in the file stays a syntax error `[agreed 2026-11-06]` |

No architecture finding: `assurance/standards` already consumes `workspace/ast/parsers`
(`context.yaml`), the JavaScript and TypeScript analyzers already parse through it, and no tach edge
changes. `exposes:` keeps `PythonStandardsAnalyzer`; the base is not exposed today.

## Architecture (Phase 3)

| Mechanism | Home | Allowed? |
|---|---|---|
| Rename of the style base | `assurance/standards/tree_sitter_base.py` | yes |
| Python analyzer on the Python parser | `assurance/standards/languages/python/analyzer.py` → `workspace.ast.parsers.python` | yes: consumed today |
| File reads (`read_bytes`, `stat`) | the style base, as today | yes: `orchestrator` |

No cycle: `workspace/ast/parsers` imports nothing from `assurance`.

## Commit Boundaries

**CB-1 — pin the Python results, one style base (FR-16).**
- Pin first: integration `tests/integration/assurance/standards/test_python_style_results_pinned.py`
  runs `StandardsScanner().scan(files)` (`scanner.py:51`) on fixture files written into `tmp_path` at test time and compares each category's `dominant`,
  `confidence` and `sample_size` with literal values written by hand from the fixtures (never read
  from the analyzer). The fixtures cover, per category, the shapes where `ast` and tree-sitter
  differ:
  - naming: nested functions, methods, `async def`, decorated defs, private names skipped;
  - type_hints: only plain parameters count (`a` before `/`, `*args`, keyword-only after `*` and
    `**kw` do not), the return annotation counts;
  - docstrings: a plain string, a concatenated string, an f-string (not a docstring), a bytes
    string (not), an empty `""""""` (not), a string that is not the first statement (not);
  - error_handling: `except:`, `except E:`, `except* E:`;
  - import_patterns: `from __future__ import …` (absolute), `from . import a`, `from ..b import c`;
  - test_patterns: `test_x.py` and `x_test.py`; a file whose first top-level statement is a
    function that imports `pytest` and whose second imports `unittest` (`ast.walk` is breadth-first,
    so today's answer is `unittest`);
  - a file with a syntax error (skipped), a file with bad UTF-8 bytes (read). The BOM file is not in this pin: today it is skipped, and Q1 changes that in CB-3.
- This test is green on today's code by design: it pins behaviour. Its power to fail is shown by
  mutants after CB-3.
- Rename `TreeSitterAnalyzer` → `TreeSitterStyleAnalyzer`; move `classify_name` and
  `compute_confidence` into the base module (Q3); JavaScript uses them.
- Tests first: `from …tree_sitter_base import TreeSitterAnalyzer` raises `ImportError` (NFR-3) — red
  until the rename.

**CB-2 — the code rules read a leading BOM (FR-18, Q6).**
- Where: `assurance/validation/rules/code/_python_only.py` gains one parse helper that drops a
  single leading `﻿` before `ast.parse`; `python_tree` (C06, C08) and C01 call it. One place
  covers every door, because each door hands the rules the text it read (`validation/interfaces/cli.py:280`,
  `interfaces/api/v1/validation.py:102`, `core/flow/handlers/validation.py:334`).
- Tests first: integration `tests/integration/assurance/validation/test_check_reads_a_bom.py` —
  `sw check` on a Python file with a leading BOM: C01 passes and C06, C08 judge it (red today: C01
  fails, C06 and C08 skip); a BOM in the middle of the file still fails C01 with its line.
- Mutant: the helper keeps the BOM → the leading-BOM case objects.

**CB-3 — Python style on tree-sitter (FR-17). Closes SF-05 (HITL).**
- `PythonStandardsAnalyzer(TreeSitterStyleAnalyzer)`: `get_code_structure()` returns
  `PythonCodeStructure()`; `get_extractors()` returns the six extractors, each now walking
  tree-sitter nodes. `ast` is no longer imported.
- The Python analyzer skips a tree whose root `has_error` (Q2), logged at debug as today; the base gains a `_readable(tree)` hook that is True by default, so JavaScript and TypeScript do not change.
- The test-framework search walks breadth-first, as `ast.walk` did.
- Tests first: a unit test that the module no longer imports `ast` (red today); a BOM Python file
  is counted in every category (red today: skipped, Q1); the old
  `_parse_file` tests move to `extract_all` (Q5). The CB-1 pin must stay green unchanged.
- Mutants (corpus `TECH-079_mutants.json`, FR-17): the docstring check accepts an f-string; the
  type-hint check counts keyword-only parameters; the relative-import check ignores the dots; the
  `has_error` skip removed. Each must be OBJECTED by the CB-1 pin.

**After CB-3 (feature closure, `specweaver-feature` Phase 4):** `check_fr_coverage.py TECH-079`,
`tests.py feature TECH-079`, the live demo, README counts, then the finished message.

## Research Notes

- tree-sitter 0.25.2, tree-sitter-python 0.25.0. Both read `def f[T]()`, `except A, B:`, `match`,
  `except*`, t-strings without `has_error`; a real syntax error sets `has_error` (probe 2026-11-06).
- Node shapes: `from __future__` is `future_import_statement`, not `import_from_statement`;
  `except*` is an `except_clause` with a `*`; a docstring is a `string` (or `concatenated_string`)
  as the only child of the block's first `expression_statement`; parameters list
  `positional_separator`, `typed_parameter`, `list_splat_pattern`, `dictionary_splat_pattern`.
- Today `ast.get_docstring` returns only a `str` constant and cleans it, so an empty docstring
  counts as undocumented; `node.args.args` holds only the plain parameters.
- `legacy_feature_map.md:121` says the Python analyzer uses AST; it changes in CB-3.

## Consistency (Phase 5)

- FR-16 → CB-1 (the name; the `commons` half shipped in SF-04 CB-2); FR-18 → CB-2; FR-17 → CB-3.
  NFR-1: tests that change are the rename's imports, `_classify_name`'s import (`test_python_analyzer.py:543`)
  and the `_parse_file` tests (Q5); JavaScript and TypeScript results do not change (Q2 hook).
  NFR-2: `commons` untouched. NFR-3: the old class name raises `ImportError`, no alias. NFR-5: the
  TECH-093 corpus has 5 mutants in `c01_syntax_valid.py`, `c06`, `c08` and `_python_only.py`;
  CB-2 re-runs and re-pins them; `stale_mutants.py` must report none.
- Architecture: no new import edge; `assurance/standards` consumes `workspace/ast/parsers` today;
  the BOM helper stays inside `assurance/validation/rules/code`.
- Red/blue, 2 cycles. Cycle 1: (MEDIUM) a pin whose expected values were read from the analyzer
  proves nothing — values are written by hand from the fixtures; (MEDIUM) recency weights depend on
  file times — fixtures are written at test time, so every weight is 1; (MEDIUM) the `has_error`
  skip in the base would change JavaScript and TypeScript — moved to a Python-only hook;
  (MEDIUM) the BOM case cannot sit in the CB-1 pin, which is green on today's code — it is a CB-3
  red test; (LOW) identifier bytes decode with `errors="replace"`, as `read_text` did. Cycle 2: none
  above threshold.
- Handoff: a fresh agent needs only this plan and the design; the node shapes it must match are in
  Research Notes.

## Backlog

None.
