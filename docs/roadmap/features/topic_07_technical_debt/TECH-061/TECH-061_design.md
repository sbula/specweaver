# Design: The Knowledge Graph Is Python-Only

- **Feature ID**: TECH-061
- **Epic**: Topic 07 (Technical Debt)
- **Status**: DELIVERED 2026-08-19
- **Origin**: found 2026-08-17 by `INT-US-10` FR-1, the first integration test written under `ADR-004`

## Problem Statement

`GraphOrchestrator.collect_files` accepts Python and nothing else:

```python
def collect_files(self, target_path: Path) -> set[str]:
    """Collects all python files from a target path."""
    target = Path(target_path)
    if target.is_file():
        if target.suffix == ".py":
            return {str(target)}
        return set()
    found = set()
    for p in target.rglob("*.py"):
```

`graph/core/builder/orchestrator.py:85-97`. Every other layer of the path is polyglot:

* `D-SENS-03` ✅ ships extractors for Go, Kotlin, Java, C/C++ and Rust.
* `graph_adapter.extract_ast_dict` resolves a parser by file extension from
  `get_default_parsers()` and handles whatever it returns
  (`workspace/ast/adapters/graph_adapter.py:30-38`).
* `OntologyMapper` is language-agnostic — it reads `type` and `name` and nothing else.

So the polyglot half of `B-SENS-02`'s graph is unreachable from `sw graph build`. Pointed at a real
Java file whose symbols the shipped extractor **does** report, the run persists **zero** nodes — not
even the FILE node the mapper always emits, because collection drops the file before the mapper is
reached.

**Why no existing test saw it.** Each part is green on its own and the composition was never driven:
`test_graph_adapter.py` proves the adapter with a real parser; `test_builder_integration.py` proves
the builder with `fake_java_parser`; `test_orchestrator.py:149` names `build_target` and then
`MagicMock`s the repository, topology and engine to assert `persist_semantic_digraph` was *called*.
Three passing suites, no proof the shapes meet. This is the fourth instance of the shape the
2026-08-16 handover recorded: **a well-covered mechanism reached through an untested seam.**

This is a defect in delivered code, so per `ADR-004` clause 6 it is a new ticket rather than an edit
to `B-SENS-02`, and `INT-US-10` stays open until it lands.

## Functional Requirements

| # | FR | Actor | Action | Outcome |
|---|-----|-------|--------|---------|
| FR-1 | Collection asks the parser registry | `GraphBuilder.collect_files` | derives its accepted suffixes from `get_default_parsers()` | every language a shipped parser can read is collected, and a language added to the registry needs no second edit here |
| FR-2 | A directory of mixed sources is walked | `GraphOrchestrator.build_target` | is pointed at a directory rather than one file | both a Java and a Python file under it reach the graph — which is what `sw graph build <dir>` on a monolith actually does |

## What the fix was

Approach 1, as the filing predicted. Collection and extraction now cannot disagree by construction:
both read the same registry.

**A second gap surfaced while proving it.** Reverting the directory walk from `*` to `*.py` killed
nothing — the existing test hands `build_target` a single FILE, so the walk branch was never driven,
and the real entry point is a directory. FR-2 covers it, and asserts BOTH languages: a walk that
collected Java and stopped collecting Python would satisfy a Java-only assertion perfectly.

**Two details worth recording rather than rediscovering.** `_nodes` in that suite reports the
*service* name, which is `default` for every row — the file each node came from is what says which
languages were reached. And the store normalises `file_id` to lower case, so `UserService.java` is
persisted as `userservice.java`; a case-sensitive match reports the Java file as absent when it is
there.

## Verifiable Proof

| FR | Test |
|---|---|
| FR-1 | `tests/integration/graph/test_real_extraction_to_graph.py::test_a_non_python_source_also_reaches_the_graph` — was `xfail(strict=True)` against this ticket and turned XPASS the moment the fix landed. Pinning the suffixes back to `.py` fails it |
| FR-2 | the same file, `::test_a_polyglot_directory_reaches_the_graph` — reverting the walk to `*.py` fails it, and pinning the suffixes fails both |

## Candidate Approaches (as filed)

1. **Ask the parser registry.** Derive the accepted suffixes from `get_default_parsers()` so
   collection and extraction cannot disagree by construction. One source of truth; the likely answer.
2. **A suffix allow-list on the orchestrator.** Cheaper, and reintroduces the same divergence the
   moment a parser is added.
3. **Collect everything and let the adapter refuse.** Simple, but walks a whole monolith's
   non-source files to discard them.

## Non-Goals

- Language-specific graph semantics. The mapper reads `type` and `name`; whether a Kotlin `object`
  should be a distinct `NodeKind` is `B-SENS-02` scope, not this fix.
- `.specweaverignore` behaviour (`C-SENS-02`), which already filters what is collected.
- Making the Java grammar available where it is absent — the proof skips explicitly there.

## Delivery

Delivered 2026-08-19. The guardrail worked exactly as the stub required: the strict marker turned
XPASS on the first run after the fix, which is the signal to remove it, and
`check_xfail_blockers.py` reports every remaining strict xfail still names an unbuilt blocker.
