# Draft design: the knowledge graph as a whole

**2026-08-25. A draft, and a record of what was measured — not an approved design.**

Not run through `specweaver-design`: that skill designs **one capability with an ID**, and this
spans nine. Minting an ID for an architecture view would put a capability in the registry that
nobody builds. `ADR-006` already holds the architectural decision; this is the survey underneath it.

Companion: [`language_families_and_the_graph_2026-08-25.md`](language_families_and_the_graph_2026-08-25.md)
holds the per-language measurements this leans on.

---

## 1. What it is for

One sentence, from `ADR-006`:

> The graph answers *what contains, calls, implements, imports, or depends on X?*
> The vector store answers *what looks relevant to this text?*

The distinction is a **hard property, not a tuning choice**. Graph traversal is exact — the result
is the complete set of nodes the edges reach, or it is a defect. Vector search is approximate, with
no completeness guarantee of any kind.

That property is the whole reason to build a graph. A refactoring decision made on vector output can
miss a dependent silently.

`ADR-006` fixes the pipeline: **locate → contextualize → verify**. Vectors locate a starting point
from a fuzzy description; the graph expands it exactly; the graph verifies nothing was broken.

---

## 2. Requirements — what it must do to be worth having

Derived from the three steps, not invented:

| # | Requirement | Why |
|---|---|---|
| R1 | A symbol can be found by **name and kind** | *Locate* is impossible without it |
| R2 | Traversal from a node returns **every** caller, callee and dependent | Exactness is the only reason to prefer it over vectors |
| R3 | An unresolved reference is **visible as unknown**, never invented | An invented dependency is worse than a missing one |
| R4 | Edges cover how the language actually binds — including where binding is not a call site | A call graph over framework code is incomplete by construction |
| R5 | It is cheap enough to rebuild as often as a reader needs it | A reader that packs per agent turn cannot wait for a full rebuild |

**R3 is the only one met today**, and it was met on purpose: `ADR-006` chose ghost nodes so an
unresolved name stays visible.

---

## 3. Promises it can hold, and promises it cannot

The distinction the benefit test asks for.

### Can hold today

- **Containment and imports are complete.** A file contains what it declares; a file imports what it
  imports. Both are read straight from the syntax with nothing to infer. These are exact now.
- **An unknown is visible.** A name that cannot be resolved becomes a ghost carrying the raw text,
  not a guess. Rare and worth keeping.

### Cannot hold today — and one is actively dangerous

- **"Exact impact analysis."** Exactness requires completeness. Measured: **48% of this repo's
  Python procedure declarations sit behind a name declared more than once**, so every call to them
  ghosts; TypeScript interfaces are never reported at all; framework binding produces no edge.
  **An incomplete answer that claims exactness is worse than an honest approximation** — `ADR-006`
  says so itself: *"analysis built on it reports safety that does not exist"* (Jasmine, ASE 2022,
  proved and repaired exactly this for Spring).
- **"Better context for the LLM."** No reader exists. Nothing has ever put a subgraph into a prompt,
  so no comparison against today's file-skeleton context has been made. **Unproven, not false.**
- **"It makes SpecWeaver faster / cheaper."** Never measured on a target project. The only figure
  that exists — 358 files, 2.71 s — is SpecWeaver parsing **its own source**.

### The hollow one to retire

**"A knowledge graph is table stakes for AI code tools."** True of tools whose graph is complete and
read. Ours is neither. Repeating it invites building more graph rather than the first reader — which
is how it came to have nine edge kinds and zero consumers.

---

## 4. What we already have

| Piece | State |
|---|---|
| Builder over 10 languages (`B-SENS-02`) | ✅ built |
| SQLite store, upsert + stale purge + per-file purge | ✅ built |
| Ontology: 11 node kinds, 9 edge kinds | ✅ declared |
| `CONTAINS`, `IMPORTS`, `CALLS`, `EXTENDS`, `IMPLEMENTS` emitted (`TECH-068`) | ✅ built, closed 2026-08-22 |
| Ghost nodes for unresolved names, carrying the raw text | ✅ built |
| `sw graph build` | ✅ the only entry point, typed by hand |
| **Readers** | ❌ **zero. Eight named, none designed** |

Measured: `GraphOrchestrator` and `SqliteGraphRepository` are referenced **only inside `graph/`**.

---

## 5. The gap

Ordered by what blocks what.

| # | Gap | Blocks | Owner |
|---|---|---|---|
| G1 | **`kind` and `name` are not persisted.** `graph_nodes` has no column for either; a stored node is an anonymous hash with a file path | R1, and therefore every reader | **nobody** |
| G2 | **Each parser's two lists disagree** — what it reports as a symbol vs what counts as a type. Six languages mis-file, two never report | R1, R2 | **nobody** |
| G3 | **Calls resolve on a globally unique bare name.** No type resolution, so `thing.save()` finds whatever lone `save` exists | R2 | **nobody** |
| G4 | **Framework binding produces no edges.** `CONSUMES`/`FULFILLS`/`PUBLISHES`/`SUBSCRIBES` have no writer | R2, R4 | `B-SENS-08` 🔜 |
| G5 | **Every build re-ingests every file** | R5 | `TECH-070` 🔴 |
| G6 | **Descriptions are parsed and dropped.** Every parser has a comment query the adapter never calls | context quality | **nobody** |

**G1, G2, G3 and G6 have no owner at all.** They are not on the roadmap in any form.

---

## 6. Where it integrates

The seam already exists and is occupied.

`core/flow/handlers/context_assembler.py` → `evaluate_and_fetch_skeleton_context()` fetches
background context for a prompt **file by file**, as AST skeletons, into `PromptSlot.CONTEXT`. That
is today's answer to *"what should the model see?"*

**A graph reader replaces the selection, not the plumbing.** Instead of *"skeletonize these files"*,
`B-SENS-09` would say *"pack the subgraph around this node"* and hand the result to the same slot.

That makes the integration small and the comparison honest: the same prompt slot, two ways of
filling it, measurable against each other on the same task. **That comparison is the proof the graph
has never had**, and it is available the day a reader exists.

Nothing else in SpecWeaver needs to change. The graph is not on any pipeline path today, so there is
nothing to unwire.

---

## 7. Planned versus implemented

| Capability | Role | State |
|---|---|---|
| `B-SENS-02` | the builder | ✅ delivered |
| `TECH-068` | five syntactic edge kinds | ✅ closed 2026-08-22 |
| `B-SENS-08` | framework edges — `ADR-006` calls it a **precondition**, not an enhancement | 🔜 no design |
| `B-SENS-09` | **deterministic context packing — the only reader on a user path** | 🔜 no design |
| `B-VAL-07` | graph-invariant verification | 🔜 no design |
| `B-FLOW-04` | hybrid RAG, hands to `B-SENS-09` | 🔜 no design |
| `C-UI-01` | god-node / centrality view | 🔜 no design |
| `B-SENS-06` | CVE reachability | 🔜 no design |
| `A-SENS-05` | stack trace → node, the dynamic half | 🔜 no design |
| `B-INTL-08` | semantic review on `B-VAL-07` | 🔮 no design |
| `TECH-070` | incremental build | 🔴 STUB |

**Eleven entries. Two delivered, nine with no design document.**

---

## 8. What this draft concludes

1. **The reason to build it is sound.** Exact traversal answers a question vectors cannot, and
   `ADR-006` draws the line correctly.
2. **The claim it currently makes is not.** It is sold on exactness and is not complete, and
   `ADR-006` names that failure mode itself.
3. **The next thing is a reader, not more graph.** `B-SENS-09` is the only capability that reaches a
   user path, and it is the only one that can produce evidence the graph is worth its cost.
4. **G1 blocks even that.** No reader can be built on a store of anonymous hashes. Two columns.
5. **The unowned gaps are the story.** G1, G2, G3 and G6 are on nobody's roadmap, and three of them
   are correctness rather than polish.

**What it does not conclude:** that any of this is urgent. There is no target project, no reader, and
no measurement of the cost on real work. This says what would have to be true for the graph to keep
its promises — not that it should be made true now.
