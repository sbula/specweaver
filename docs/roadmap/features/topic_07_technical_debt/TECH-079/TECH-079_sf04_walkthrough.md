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
