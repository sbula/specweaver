# B-SENS-03 SF-02 CB-1 — Walkthrough

**Commit boundary:** CB-1 of 2 · **DAL-B** · 2026-08-26 · **Proves**: `FR-5` · Plan:
[sf02](B-SENS-03_sf02_implementation_plan.md)

## Delivered

`extract_symbol_doc(code, symbol_name) -> str` on every parser: the description written above a
declaration, marker-free, or `""`. Never raises — it runs once per symbol in a whole-repository scan.
`extract_symbol` had dropped doc comments in every language but Python, whose docstring lives inside
the body.

- **Attachment is a position and a line gap.** A Go comment three blank lines above a function is
  still its `prev_sibling`; without a gap check every licence header becomes the first
  declaration's description — while every *present*-doc test still passes.
- **Anchor**: climb to the outermost ancestor starting on the same row, then read its previous
  sibling. Replaces the planned `_DOC_DEPTH` (deleted) in all ten languages; type-level cases
  (TypeScript `export_statement`, Go `type_declaration`, C/C++ `struct_specifier`) are what a fixed
  depth could not express.
- **Rust's `line_comment` owns its trailing newline**: adjacency uses the last *content* row, and
  the newline is stripped when joining stacked `///` lines.

## Proof

The licence-header case is written in **Go** with the comment after `package m` — the only shape
where the walk reaches the gap check. Python's docstring has its own test, named for that mechanism.

| # | Neutralised | Objections |
|---|---|---|
| M1 | the line-gap check | 3 |
| M2 | marker stripping | 13 |
| M3 | only the nearest comment is taken | 2 |
| M4 | Python's docstring reader | **1** |
| M6 | the wrapper climb stops | 4 |
| M7 | the climb never stops, and reaches the file | 21 |

| Check | Result |
|---|---|
| Full suite | **8,795 passed, 11 skipped** |
| `quality.py cb` | 15 of 15 · `doc` 13/13 · `mypy` clean · `tach` ✅ |
| New tests | 72 |

Duplication re-frozen on evidence from `check_duplication.py` run directly (the gate summary printed
only *"1 clone removed"*): TypeScript untouched, Python +2 lines outside the clone region.

## Findings still open

- **M4 has a single point of protection.**
- A doc comment carrying a `@trace(...)` tag reaches the description as text.
