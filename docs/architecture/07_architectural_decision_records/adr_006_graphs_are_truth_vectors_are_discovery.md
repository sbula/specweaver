# ADR 006: Graphs Are Deterministic Truth; Vectors Are Probabilistic Discovery

**Status:** Accepted
**Date:** August 21, 2026
**Context:** the 2026-08-20 benefit-chain review (`docs/analysis/benefit_chain_analysis_2026-08-20.md`)
found the knowledge graph written and never read; this ADR names its readers and draws the line
between the two retrieval stores before any reader is designed.

## Context and Problem Statement

SpecWeaver plans two stores that select code for the LLM:

* a **code graph** (`B-SENS-02`, SQLite; `A-SENS-02` adds Apache AGE at scale) — typed nodes
  (modules, classes, functions) and typed, directed edges;
* a **vector store** (`A-SENS-02` pgvector, fed by `B-SENS-03` chunks, orchestrated by
  `B-FLOW-04`) — embeddings of code chunks, queried by similarity.

The two stores answer different questions, and the difference is a hard property, not a tuning
choice. Graph traversal is **exact**: the result is the complete set of nodes the edges reach, or
it is a defect. Vector search is **approximate**: the result is the nearest neighbours of an
embedding, with no completeness guarantee of any kind. A refactoring decision made on vector
output can miss a dependent silently. A discovery query answered only by the graph needs the exact
symbol name the user does not have.

Measured state when this ADR was written:

* The graph had **zero readers** outside its own builder. Its ontology declares nine edge kinds;
  the mapper emitted one (`CONTAINS`). `TECH-068` owned that defect and has closed it in code:
  a real build now persists `CONTAINS`, `IMPORTS`, `EXTENDS` and `CALLS`.
* Framework code hides its edges from every parser: Spring/Quarkus dependency injection, HTTP
  routes, and event listeners produce **no syntactic call site**. A call graph over such code is
  incomplete, and analysis built on it reports safety that does not exist (Jasmine, ASE 2022,
  proved and repaired exactly this for Spring).
* The repo already holds framework knowledge — five schema files
  (`workflows/evaluators/frameworks/`: spring-boot, quarkus, nestjs, fastapi, actix-web) — but
  that knowledge flows only into prompt comments (`B-INTL-02`), never into edges.
* Four graph-shaped stores existed with overlapping claims (module topology, knowledge graph,
  Merkle hash topology, lineage). Two checks had already gone silently green over the overlap
  (`TECH-064`; the `B-SENS-07` analysis).

Without a recorded boundary, the next capability picks a store by convenience, correctness
decisions drift onto approximate data, and the graph family grows a fifth member.

## Decision

1. **Two stores, two questions — never swapped.**
   The graph answers: *what contains, calls, implements, imports, or depends on X?*
   The vector store answers: *what looks relevant to this text?*
   A capability states which question it asks. If it asks both, it uses both stores in the
   pipeline order below — never one store for the other's question.

2. **The retrieval pipeline is: locate → contextualize → verify.**

   | Step | Question | Mechanism | Owners |
   |---|---|---|---|
   | **Locate** | "Where should the agent look?" | vector similarity, lexical search, telemetry | `B-SENS-03` (chunks) · `A-SENS-02` (pgvector) · `B-FLOW-04` (scoring) |
   | **Contextualize** | "What exactly does that code touch?" | graph traversal: target + callers + callees + contracts | `B-SENS-02` (graph) · `TECH-068` (edge truth) · `B-SENS-08` (framework edges) · `B-SENS-09` (packing) |
   | **Verify** | "Did the change break a dependent?" | graph diff against invariants | `B-VAL-07` (gate) · `B-INTL-08` (review narrative on top) |

3. **The invariant: no correctness decision consumes vector output.**
   Vectors nominate; graphs decide. A gate, a blast radius, a merge decision, or a verification
   verdict reads graph traversal only. Vector output may start a search, rank candidates, or
   suggest context. It may never be the evidence that a change is safe. A design that violates
   this is wrong by definition, not by review.

4. **There is one code graph.** `B-SENS-04` (control flow) and `B-SENS-05` (dataflow) are
   **layers on `B-SENS-02`'s graph**, following the Code Property Graph model (Joern): one store,
   more edge kinds. They are not separate graphs. `D-SENS-01`'s module topology is different in
   kind, not in scale: it records **declared intent** (`context.yaml`); the code graph records
   **extracted reality**. Comparing the two is an architecture check; merging them would destroy
   the comparison. Lineage (`B-SENS-01`) records provenance and stays orthogonal.

5. **Edge truth precedes readers.** Sequencing is fixed: `TECH-068` (syntactic edges: `IMPORTS`,
   `CALLS`, `EXTENDS`, `IMPLEMENTS`) → `B-SENS-08` (framework-semantic edges from the delivered
   schema files: injection, routes, listeners) → the readers (`B-SENS-09`, `B-VAL-07`, the
   blast-radius seams). A reader built before its edges exist is green and useless — the defect
   class the 2026-08-20 review was written to stop.

6. **Calibrated claims only.** On dynamic languages, a graph check is **graph-checked, not
   guaranteed**: `getattr`, duck typing, and reflection escape static edges. Unresolved references
   become `GHOST`-node edges so a traversal can tell *no dependents* from *dependents unknown*.
   Designs and registry entries write "graph-checked"; the words "proves", "guarantees", and
   "mathematically" are reserved for claims a machine actually enforces.

## The wiring map

What produces what, and who reads it — the single orientation table for this architecture.

| Component | Produces | Read by |
|---|---|---|
| `D-SENS-02/03` parsers ✅ | AST symbols per file | `B-SENS-02` builder · skeletons (`D-VAL-04`) |
| `B-SENS-02` builder ✅ | graph nodes + `CONTAINS` | `B-SENS-09`, `B-VAL-07`, blast-radius seams, `C-UI-01`, `B-SENS-06`, `A-SENS-05` *(all pending `TECH-068`)* |
| `TECH-068` 🟡 | syntactic edges (`IMPORTS`, `CALLS`, `EXTENDS`, `IMPLEMENTS`) — **built 2026-08-22**, closure outstanding | every graph reader |
| Framework schemas ✅ (`workflows/evaluators/frameworks/`) | annotation semantics | `B-INTL-02` prompt comments ✅ · `B-SENS-08` edges 🔜 |
| `B-SENS-08` 🔜 | framework edges (`INJECTS`-class, routes, listeners; `PUBLISHES`/`SUBSCRIBES`) | blast radius · `B-SENS-09` · `B-VAL-07` · `A-SENS-04` (cross-service linkage) |
| `B-SENS-03` 🔧 | symbol chunks | `A-SENS-02` embeddings 🔜 |
| `A-SENS-02` 🔜 | pgvector index + AGE graph backend | `B-FLOW-04` locate 🔜 |
| `B-FLOW-04` 🔜 | ranked candidates (locate) | hands over to `B-SENS-09` — never to a gate |
| `B-SENS-09` 🔜 | packed subgraph context in prompts | `sw draft`/`implement`/`review` loops |
| `B-VAL-07` 🔜 | broken-dependent findings post-generation | pipeline gates · `B-INTL-08` 🔮 |
| `A-SENS-01` ✅ | Merkle staleness | incremental graph/pipeline refresh (`A-SENS-03` = trigger only) |
| `C-UI-01` 🔜 | god-node / centrality visualisation | developers — meaningless before `TECH-068` |
| `B-SENS-06` 🔜 | CVE reachability (`CALLS` closure to vulnerable functions) | fleet remediation (US-26) — behind `TECH-068` |
| `A-SENS-05` 🔜 | stack-trace → graph-node resolution | self-healing loop (US-27) — behind `TECH-068` |

## Prior Art

* **Jasmine** (ASE 2022) — Spring DI breaks vanilla call graphs; framework-aware completion
  repairs them. The proof that `B-SENS-08` is a precondition, not an enhancement.
* **jQAssistant Spring plugin** — production precedent: Java architecture graph in Neo4j with
  framework concepts as first-class rules.
* **CodexGraph** (NAACL 2025) — LLM agents querying a code graph DB; its schema
  (`MODULE/CLASS/FUNCTION`, `CONTAINS/INHERITS/USES/CALLS`) independently matches `B-SENS-02`'s
  ontology. RepoGraph reports +32.8% relative on SWE-bench for graph-guided agents.
* **Joern** — the Code Property Graph: AST, CFG, and dataflow as layers of one graph. The model
  for decision 4.
* **HybridRAG / GraphRAG literature** — vector-seeded graph traversal beats either store alone
  (reported 15–30% faithfulness gains). The model for decision 2.

Full links: `ORIGINS.md` § Graph & Retrieval.

## Consequences

* `TECH-068` is built and committed, so the reader family is unblocked in code; its closure is
  outstanding. `TECH-069` and `TECH-070` are also open, so it is no longer the only debt ticket —
  the Debt Sequencing section carries all three.
* `B-SENS-08`, `B-SENS-09`, `B-VAL-07` are designed **against this ADR**: their designs cite the
  step they implement, their seam FRs name the stores they read, and their first tests go red
  against the missing edges.
* `B-INTL-08` builds its review narrative on `B-VAL-07`'s graph diff. It augments text diffs; it
  does not replace them.
* Any future capability that gates on vector output is rejected at design review by decision 3 —
  no discussion needed, that is what the rule is for.
