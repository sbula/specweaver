# Implementation Plan: The Knowledge Graph Emits One of Its Nine Declared Edge Kinds [SF-03: Supertypes, with extension and implementation told apart]

- **Feature ID**: TECH-068
- **Sub-Feature**: SF-03 — Supertypes, with extension and implementation told apart
- **Design Document**: docs/roadmap/features/topic_07_technical_debt/TECH-068/TECH-068_design.md
- **Design Section**: §Sub-Feature Breakdown → SF-03
- **Implementation Plan**: docs/roadmap/features/topic_07_technical_debt/TECH-068/TECH-068_sf03_implementation_plan.md
- **Status**: APPROVED (2026-08-21)

## Scope

`FR-4` (`extract_supertypes` on the parser contract), `FR-6` (the seam carries them with their kind),
`FR-9` (`EXTENDS` edges) and `FR-10` (`IMPLEMENTS` edges). Depends on `SF-02`, which is committed.

## Research Notes

### A supertype names a SYMBOL, and symbols are not known until every file is parsed

`FR-8` resolved imports against **paths**, which `collect_files` knows before any file is read. A
supertype names a class, so resolution needs to know what each file *contains* — and that is only
known after parsing it.

The mapper is called once per file. Resolving against what the engine has accumulated so far would
make the answer depend on ingestion order, and **ingestion order is not deterministic**:
`collect_files` returns a `set` (`orchestrator.py:115`) and `ingest_target` iterates it directly
(`orchestrator.py:127`). Set iteration over strings varies with `PYTHONHASHSEED`, so the same
repository would produce a different graph on different runs. That is not a weaker guarantee, it is
no guarantee.

**A symbol index built before any edge is emitted is the only deterministic option**, and `FR-11`
in `SF-04` needs precisely the same thing to resolve a callee. The design has `SF-03` and `SF-04`
running in parallel on the grounds that neither reshapes the seam — true, but they share a
prerequisite that neither owns. This is a decomposition finding, not an implementation detail.

### Two of five languages separate the two kinds cleanly; one nearly does; two cannot

Measured against the real grammars:

| Language | Grammar | Distinguishes? |
|---|---|---|
| Java | `superclass` / `super_interfaces` | Yes, cleanly |
| TypeScript | `extends_clause` / `implements_clause` | Yes, cleanly |
| Kotlin | one `delegation_specifiers` holding both | **Only by convention** — `Base()` carries a constructor call, `Runner` does not |
| Python | no such distinction in the language | No |
| Rust | `impl Trait for Type`, not a class hierarchy | Different construct |

`FR-4` says "for every language whose syntax distinguishes them". Kotlin sits exactly on that line:
the parentheses usually say which is which, and `by` delegation or a base with no explicit
constructor invocation breaks the rule.

### The contract that must not change

`extract_framework_markers` returns one flat `extends` list and has three consumers outside this
feature, one an agent-facing tool intent. `NFR-7` forbids changing its shape, and `AD-2` settled
that `extract_supertypes` is a **new** method beside it rather than a widening.

### Surfaces this plan touches

| Symbol | Signature as it exists | File |
|---|---|---|
| `extract_framework_markers` | `(self, code: str) -> dict[str, dict[str, list[str]]]` | `workspace/ast/parsers/interfaces.py` |
| `map_ast_to_nodes` | `(self, filepath, ast_data, known_files=frozenset())` | `graph/core/builder/mapper.py` |
| `resolve_module` | `(module: str, known_files: frozenset[str]) -> str | None` | same — the shape a symbol resolver mirrors |
| `ingest_target` | `(self, target_path) -> int`, sets `known_files` then loops | `graph/core/builder/orchestrator.py` |

## Decisions taken with the user at the Phase 4 gate

1. **`SF-03` builds the symbol index and `SF-04` depends on it.** Its dependency moves from `SF-02`
   to `SF-03`. The parallelism the design claimed was never real — the two shared a prerequisite
   neither owned — so the design is corrected rather than the finding worked around.
2. **Every Kotlin supertype is reported as extension.** The parentheses convention is right for
   ordinary Kotlin and silently wrong for `by` delegation and for a base with no explicit
   constructor invocation. A reader querying `IMPLEMENTS` gets nothing for Kotlin rather than
   something right most of the time — the same call made for ambiguous imports, for the same
   `ADR-006` reason. The design records that `IMPLEMENTS` is not derivable there.

## Red/Blue findings, merged

- **The prepass must not double the parse cost.** Parsing every file once to index its symbols and
  again to ingest it takes the measured 2.8 ms/file to roughly 5.6 — at the reference workload's
  3,000 files that is ~17 s where `NFR-1` budgets 60 for everything this ticket adds. The prepass
  keeps what it parsed and the ingest pass reuses it, so the tree is built once. **`CB-2` owns
  proving that**, not just producing a correct index.
- **A supertype name that matches two symbols becomes a `GHOST`**, exactly as `FR-13` requires of a
  callee. Two classes named `Config` in different files are not one class.
- **The index is keyed on bare type names.** A supertype is written bare — `class Impl : Base` — so
  `Base` is the lookup key, while `list_symbols` also returns qualified members like `Derived.m`.
  Members belong in the index `SF-04` needs for callees, not in the one a supertype consults.
- **A supertype from outside the parsed set becomes a `GHOST`**, which is what makes an inheritance
  traversal distinguishable from an empty one.

## Commit Boundaries

### CB-1 — A parser reports supertypes with their kind

**Proves**: `FR-4`. **Tier**: unit per language — the claim is one parser's reading of syntax.

1. Red first: `extract_supertypes` does not exist. Java must separate `superclass` from
   `super_interfaces`; TypeScript `extends_clause` from `implements_clause`; Kotlin reports every
   delegation specifier as extension; Python reports all bases as extension.
2. `extract_framework_markers` is untouched (`NFR-7`, `AD-2`).

**Done when**: green, and a mutant collapsing Java's two clauses into one goes red.

### CB-2 — A symbol index, built once, before any edge

**Proves**: the prerequisite `FR-9`, `FR-10` and later `FR-11` rest on.
**Tier**: integration — determinism across a whole build is not a claim one module can make.

1. Red first: two builds of the same tree must produce the same edges. Resolving against what the
   engine has accumulated cannot, because `collect_files` returns a set and `ingest_target`
   iterates it.
2. Prepass over the collected files, keeping each parsed payload; ingest reuses it rather than
   re-parsing.

**Done when**: green, and three mutants go red — the index dropped, the prepass parsing a second
time instead of reusing, and a name matching two symbols resolving to one of them.

### CB-3 — The seam carries supertypes

**Proves**: `FR-6`. **Tier**: integration.

1. Red first: `extract_ast_dict` declares `supertypes` and leaves it empty (`SF-02` `AD-1`).

**Done when**: green, and a mutant emptying the field goes red.

### CB-4 — `EXTENDS` and `IMPLEMENTS` edges

**Proves**: `FR-9`, `FR-10`. **Tier**: integration.

1. Red first: a Java class extending one type and implementing another yields one edge of each kind;
   a Kotlin class yields `EXTENDS` only; an unknown supertype yields a `GHOST`.

**Done when**: green, and mutants go red for each kind emitted as the other, and for the `GHOST`
fallback removed.

## Test Plan

| Test | Tier | Proves | Goes red because |
|---|---|---|---|
| Java separates the two clauses | unit | FR-4 | `extract_supertypes` does not exist |
| TypeScript separates the two clauses | unit | FR-4 | same |
| Kotlin reports extension only | unit | FR-4 | same |
| Python reports all bases as extension | unit | FR-4 | same |
| two builds of one tree agree | integration | CB-2 | order-dependent resolution cannot |
| the tree is parsed once, not twice | integration | CB-2 | a prepass that re-parses doubles the cost |
| an ambiguous supertype ghosts | integration | FR-9 | a heuristic would pick one |
| the seam carries supertypes | integration | FR-6 | the field is declared and empty |
| `EXTENDS` and `IMPLEMENTS` land distinctly | integration | FR-9, FR-10 | nothing emits either |
| an unknown supertype ghosts | integration | FR-9 | nothing emits a ghost for supertypes |

Four buckets: happy path (Java's two clauses), boundary (a class with no supertypes, a name matching
two symbols, Kotlin's single list), graceful degradation (a supertype outside the parsed set),
hostile input (a supertype string that is empty, and a cyclic hierarchy).

## Non-Goals

- `CALLS`. `SF-04` owns it and reuses `CB-2`'s index.
- Changing `extract_framework_markers`. `NFR-7` and `AD-2` forbid it.
- `IMPLEMENTS` for Kotlin, Python or Rust. Decision 2 records why.
- Resolving a supertype from an external library to anything but a `GHOST`.
