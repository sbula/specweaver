# Why boundary enforcement works for one language and reports success for the rest

- **Measured**: 2026-08-18
- **Origin**: writing the `INT-US-20` P-5 journey test, and a user asking whether folder structure was the
  right discriminant for it. It was not, and the question kept being right at every level it was applied.
- **Owns nothing.** This is the measurement behind `B-SENS-07` and `TECH-064`; both link here rather than
  restating it.

## What was measured

Each language analyzer was run against an equivalent source file in a temp directory. The interface is
uniform — `extract_imports(directory) -> list[str]`, five implementations. The results are not.

| Language | Source | Returned | What the string actually is |
|---|---|---|---|
| Python | `import src.core` | `src.core` | a module path |
| Java | `import com.acme.core.Ledger;` | `com.acme.core.Ledger` | a **type**, not a module |
| TypeScript | `import {A} from './core/a'` | `./core/a` | a **relative file path** |
| TypeScript | `import B from '@scope/pkg'` | `@scope/pkg` | a package specifier |
| Rust | `use crate::core::ledger;` | `crate::core::ledger` | a path relative to *which* crate |
| Kotlin | `import com.acme.core.Ledger` | *(empty list)* | nothing was extracted |

**One type signature, five kinds of thing.** A module path, a type name, a file path, a package specifier
and a crate-relative path. Anything downstream that treats them alike is guessing.

Three consequences follow directly:

- **Java returns a type.** Reaching the module means dropping the last segment — but only if it *is* a
  type, and the string does not say.
- **TypeScript returns a relative path and the API has already discarded what it is relative to.**
  `extract_imports` takes a *directory*, globs every file in it and unions the results into a set. Which
  file wrote `./core/a` is gone before the caller sees the answer.
- **Rust's `crate::` needs to know which crate.** A workspace has several.

## The Kotlin extraction gap

Two valid samples — one with a package declaration, one without — both returned an empty list. No error.
The file simply reports that it imports nothing.

That silence does not stay silent. Archetype inference reads the imports, finds none, and classifies the
module `pure-logic`. **Missing data became a confident wrong answer** rather than a gap, and the wrong
answer is an architectural classification.

## A universal representation already exists, and the enforcement path does not use it

`graph/core/engine/ontology.py` declares what its own docstring calls *"The Universal Ontology"*:

```
NodeKind:  SYSTEM · MICROSERVICE · FILE · MODULE · NAMESPACE · DATA_STRUCTURE
           PROCEDURE · STATE · API_CONTRACT · MESSAGE_QUEUE · GHOST
EdgeKind:  CONTAINS · IMPORTS · CALLS · IMPLEMENTS · EXTENDS
           CONSUMES · FULFILLS · PUBLISHES · SUBSCRIBES
```

`MODULE`, `IMPORTS` and `CONSUMES` are already there. So is `GHOST` — a node referenced but not
resolvable, which is exactly what an unresolved import ought to become instead of vanishing.

Two facts about it, both verified by grep:

- **`GHOST` is declared and referenced nowhere else in `src/`.**
- **The `context.yaml` → topology → `tach.toml` pipeline never mentions the ontology at all.**

So the project holds two representations of "the structure of a codebase" that never meet: a universal one
the enforcement path ignores, and an ad-hoc string-based one the enforcement path uses.

`B-SENS-02` (Knowledge Graph Builder, `✅`) does not close this. Its FRs are parse-AST-to-nodes,
deduplicate, persist, query, export. **No delivered capability has ever claimed cross-module import
resolution**, which is why this is unbuilt work rather than debt.

## Enforcement is a different mechanism per language, and two are empty

| Language | Mechanism | Reads |
|---|---|---|
| Python | tach across the project, plus a per-file check | `tach.toml` + `forbids` |
| TypeScript | ESLint `no-restricted-imports` | `forbids` only |
| Java | a generated ArchUnit test, run via Maven | `forbids` only |
| Kotlin | returns "0 violations" — a stub | nothing |
| Rust | returns "0 violations" — a stub | nothing |

Kotlin and Rust report a clean architecture for any input whatsoever. The docstrings say "deferred",
which is honest as a note and dishonest as a return value: no caller can distinguish *checked, nothing
wrong* from *not implemented*.

## Two boundary fields with opposite models

A generated `context.yaml` carries both, and which one is authoritative depends on the language being
scanned:

```yaml
consumes: []        # allow-list — "may depend on", enforced by tach
forbids:            # deny-list  — "must not depend on", used by TS and Java
  - specweaver/sandbox/*
```

An empty `consumes` under an allow-list means *nothing is permitted*. An empty `forbids` under a
deny-list means *everything is permitted*. Same file, same blank field, opposite meaning.

## The Python path is itself broken on an undocumented repository

Scanning a repo with no `context.yaml`, then running the generated config:

```
[WARN] Warning: Module containing 'api' not found in project.
[WARN] Warning: Module containing 'core' not found in project.
✅ All modules validated!            exit=0
```

Inference names a module after its directory (`core`), the sync writes that into `path` alongside
`source_roots = ["."]`, and the package is at `./src/core`. tach reports the modules are missing and then
exits 0 — **a green run over an architecture nobody checked**.

Setting `source_roots = ["src"]` instead makes `core` and `api` resolve and breaks three others, and the
code's `import src.core` stops being first-party. So the defect is a **disagreement between three coupled
things**: the names inference produces, the source roots the sync writes, and the import convention the
code uses. Any fix that adjusts one in isolation moves the failure rather than removing it.

Behind it sits a second gap: inference never records dependencies at all. `ContextInferrer.infer_and_write`
calls `analyzer.extract_imports(directory)`, stores the result on `InferredNode.imports`, and writes no
`consumes` key — and `TopologyGraph._auto_infer_missing` builds its `TopologyNode` without carrying it
either. `InferredNode.imports` has **no reader anywhere in `src/`**. Even with resolvable paths, every
inferred module would declare `depends_on = []`, and under `exact = true` every ordinary import becomes a
violation.

## The generated config overwrites a config the customer maintains

`sync_tach_toml` preserves root properties but deletes `[[modules]]` and `[[interfaces]]` and rebuilds
them from the graph — the comment says *"graph is the source of truth"*. For a Python shop already using
tach, `sw scan` silently replaces hand-written architecture rules with inferred ones.

This is separable from the polyglot question and argues that emitting a tool-specific config into someone
else's repository is the wrong integration shape regardless. Reading an existing `tach.toml` as a declared
architecture is defensible; overwriting it is not.

## What this invalidated

The `INT-US-20` P-5 journey test written on 2026-08-17 was **circular by construction**: it planted a
violating import, then ran the scan that derives the architecture *from the source including that import*.
If inference recorded dependencies as it should, the planted violation would have been recorded as a fact
about the project and legalised on the spot.

The coherent shape is baseline-then-drift — infer once to establish a baseline, let the code change, then
check against the unchanged baseline. The product already supports the mechanics of it, since inference
skips any directory that already has a `context.yaml`. The test was deleted rather than committed.

## What is not claimed here

No resolver has been designed or costed. Building one per language needs build-system awareness —
`tsconfig`, Maven or Gradle layout, `go.mod`, crate manifests — and that is real work. Delegating to
mature external tools has genuine advantages that deciding on the graph gives up. Every measurement above
is reproducible; the conclusions drawn from them in `B-SENS-07` are arguments, not measurements.
