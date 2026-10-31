# Design: Three Code Checks Read Every Language as Python

- **Feature ID**: TECH-093
- **Epic**: Topic 07 (Technical Debt)
- **Status**: STUB — not yet run through the `specweaver-design` skill
- **Kind**: `bugfix`
- **Origin**: 2026-10-31, the `TECH-087` live demo (`sw check --level code Cart.kt`). A defect in
  delivered work: C01, C06 and C08 have run Python's `ast.parse` on every file since before
  `20a5a4e2`, and `TECH-078` (every language gets validation) did not cover them.
  `finished-stories-immutable` bars editing those stories, so this ticket owns it.
  Chosen by the user over folding it into `TECH-089` `[agreed 2026-10-31]`.

## Problem Statement

`C01` (`rules/code/c01_syntax_valid.py`), `C06` (`c06_no_bare_except.py`) and `C08`
(`c08_type_hints.py`) call `ast.parse(spec_text)` whatever the file's language. Measured
2026-10-31 on small valid files:

| File | C01 | C06 | C08 |
|---|---|---|---|
| `Cart.kt`, `Main.java`, `lib.rs` | FAIL "Syntax error at line 1" | SKIP "Cannot parse file (syntax error)" | SKIP, same |
| `app.ts` (`x = 1`) | PASS | PASS | PASS |

So valid Kotlin, Java and Rust get a false FAIL, the SKIP reason calls valid code broken, and a
non-Python file that happens to parse as Python gets a false PASS. The promise `TECH-087` made for
QA tools, a check that did not run is never clean, does not hold here.

## Candidate Approaches (not yet designed)

- For a language a check cannot read, return SKIP and name the language, as `C05` does
  (`c05_import_direction.py:56`) `[agreed 2026-10-31]`.
- How the language is decided (the file suffix, or the project's one language table) is for the
  design. `TECH-079` records that language is decided in many places.

## Non-Goals (proposed, pending design)

- Real syntax, bare-except or type-hint checks for other languages.
- Moving the parsers (`TECH-089`).

## Next Step

`specweaver-design TECH-093`.
