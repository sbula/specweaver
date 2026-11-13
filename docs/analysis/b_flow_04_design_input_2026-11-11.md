# B-FLOW-04 and exact-call-edges: design input from the user (2026-11-11)

Status: **OPEN**. Input for the `B-FLOW-04` design and the exact-call-edges feature. Nothing here
is decided yet; each point is settled in that feature's design grilling.

## 1. Evidence

- **LocAgent** (arXiv 2503.09089, ACL 2025): graph tools over contain / import / invoke / inherit
  edges. File Acc@5 92.7% against 84.7% with embeddings only. Fine-tuned Qwen 7B/32B come close to
  Claude-3.5 agents at 86% lower cost.
- **Its ablation:** entity/keyword search matters most (−18 points without it), BM25 −11, graph
  traversal −5, 1-hop only −5, contain edges only −5.
- **Counter-view:** Cline and Claude Code use agentic grep and no index (reasons given: staleness,
  chunking, a copy of the IP).

## 2. Baselines in the recall@k test

BM25, agentic grep, embeddings, BM25 + graph, embeddings + graph. RAG must beat **BM25 + graph**,
not only grep. (Extends the done-when: pinned test set, recall@k and precision, held-out part.)

## 3. The graph as agent tools

Search entity, traverse with an edge-kind policy, retrieve entity. Not bulk prompt context.

## 4. Use cases, each with 2–3 test queries

| Use case | What it needs |
|---|---|
| Localize | the candidates for a fuzzy task |
| Coder context | signatures and types of the callees |
| Impact | reverse calls, overrides, implements |
| Review check "signature changed, callers not updated" | deterministic, no LLM |
| Test selection | tests that reach the changed code |
| Refactor references | every reference to a symbol |
| Declared-vs-extracted drift | declared contracts against the code |

## 5. Service boundaries

Code graphs end at service boundaries on purpose: an agent that works on service A never learns
B's internals.

- **Three levels:**
  - code graph per service (internals);
  - service graph (contracts only: services, Kafka topics, protobuf messages, gRPC services and
    methods, REST endpoints; edges produces / consumes / calls / serves; no file paths, no internal
    symbols);
  - module graph (`context.yaml`, declared intent).
- **Declared vs extracted** (`ADR-006` #4): declared from `.proto`, AsyncAPI (Kafka), OpenAPI
  (REST); extracted from code (who really publishes, consumes, calls). A mismatch is a finding.
- **Isolation is enforced in tools, not by convention:**
  - the RAG index or query is hard-scoped per service;
  - file grants (`E-SENS-03`) = own service + shared contracts;
  - a direct code edge A→B is flagged as a boundary violation (`boundary_rule`);
  - a shared library is its own unit, public API only.
- **A contract change in A:** the service graph names the consumers (B, C) and the contract only.
  The change in B becomes its own task for B's agent (decomposition at service level).
- **Quarkus CDI:** calls through injected interfaces need `implements` edges to reach the
  implementation inside the service.
- **Test:** a hostile query from service A's agent never returns a chunk, symbol or path of
  service B.

## 6. Who owns the service graph — decided `[agreed 2026-11-11]`

- **`A-SENS-04`:** the service graph (contracts only) and the declared-vs-extracted check
  (`.proto`, AsyncAPI, OpenAPI against the code).
- **`B-SENS-08`:** the extracted edges, incl. Quarkus `@Incoming` / `@Outgoing`, `@GrpcService`
  and CDI `implements`.
- **`B-FLOW-04`:** the per-service scope (from the `context.yaml` boundaries) and the
  hostile-query test.
- No new capability. `A-SENS-04` stays in its place in the order.

## 7. No fixed traversal depth — decided `[agreed 2026-11-11]`

A decision on delivered code (`TECH-088`, COMPLETE 2026-11-08): `MAX_NEIGHBOURHOOD_DEPTH`
(`graph/core/engine/models.py`, 5) goes, for the code graph and the module graph. No fixed depth
anywhere. A caller that wants a limit passes `max_depth`. `A-SENS-02` implements it `[agreed 2026-11-11]` (Q23 A).

## 8. Graph tools for the agent — sketch (open)

The agent calls typed tools. It never writes SQL or Cypher.

### Rules for every tool

- **Hard service scope.** The scope comes from the task's grant, not from a parameter. A node
  outside the scope is never returned, counted or named.
- **Precision per result.** Each edge carries `precision` (exact / type-aware / name-only) and
  `status` (valid / stale).
- **Deterministic order.** The same graph and the same call give the same order: depth, then
  relevance, then node ID.
- **Never silent truncation.** Each result says `returned`, `total` and whether it is `complete`.
  A cut result has a cursor and a reason.

### The tools

| Tool | Typed parameters | Returns |
|---|---|---|
| `find` | `query: str`, `kinds: set[NodeKind] \| None` | ranked entities (keyword + BM25 + embedding) |
| `get` | `node: NodeId` | one entity: kind, signature, types, file span |
| `neighbours` | `node: NodeId`, `direction: In \| Out \| Both`, `edge_kinds: set[EdgeKind]` | one hop, every edge |
| `reach` | `seeds: list[NodeId]`, `direction`, `edge_kinds`, `max_depth`, `budget`, `cursor` | a `Traversal` |
| `path` | `source: NodeId`, `target: NodeId`, `edge_kinds`, `max_depth` | the shortest path, or "no path" with the depth searched |
| `hierarchy` | `type: NodeId`, `direction: Up \| Down \| Both`, `max_depth`, `budget`, `cursor` | a `Traversal` over extends / implements / overrides |
| `impact` | `symbol: NodeId`, `max_depth`, `budget`, `cursor` | a `Traversal` over reverse calls, overrides and implements, plus the tests that reach the symbol |
| `check_change` | `change: CommitRange \| Diff` | findings "signature changed, caller not updated"; deterministic, no LLM |

### Traversal parameters (`reach`, `path`, `hierarchy`, `impact`)

Two optional parameters. No default values, no constants.

- `max_depth: int | None`. If given, the traversal stops at that depth.
- `budget: int | None`. If given, at most that many nodes are returned. The traversal still runs
  fully. The summary counts everything. The nodes are the top-k by relevance, with a cursor for
  the rest.
- **Neither given:** the traversal runs until done, or until the time limit X. Then it stops and
  reports "stopped after X ms at depth N". X is configurable, 2,000 ms `[agreed 2026-11-11]` (Q21 A; the
  slowest bfs() cold on L is 17 ms).

### `Traversal`

- `nodes`: the returned page.
- `summary`: counts per depth, per module, per edge kind, per precision. Always over the whole
  traversal.
- `complete: bool`, `stopped: {reason: max_depth | time_limit, after_ms, depth} | None`.
- `cursor: Cursor | None`.

### Open: how many nodes come back with no budget

To be decided by the user.

Option C was added by the user, 2026-11-11: no fixed number. The default budget comes from the
calling model's context window (a share of it), so a small model gets fewer nodes. The tokens per
node are measured on real results, then A and C are compared. Measurement: pending.

## 9. Traversal rules — decided `[agreed 2026-11-11]`

Calls fan out to 1,000+ edges per level, and recursion makes cycles legal.

- **Never enumerate paths.** A traversal returns a node set (BFS with a visited set, each node
  once) and at most one shortest path. The cost is bounded by the service's size, not by its path
  count. It terminates on cycles. Depth = the shortest distance.
- **No fixed depth anywhere.** `max_depth` and `budget` are optional. Without them, the time limit
  stops the traversal and reports "stopped after X ms at depth N".
- **Filters as tool parameters,** more useful than depth: edge kinds, direction, stop at a
  boundary (module / public API), include or exclude tests, precision (exact only / incl.
  name-only / incl. stale).
- **The summary is the main result of a wide traversal:** counts per level, per module, per edge
  kind, and how many reached nodes lie in cycles (which SCCs, i.e. strongly connected components).
- **Code-graph cycles are information, not violations.** Module-graph cycles are violations. The
  two stay apart.
- **SCC ID per node,** computed with the nightly full index, and marked stale in deltas.

### Tests (red first), for both in-memory engines and the DB traversal

- **Depth:** a chain of 7 and a chain of 10,000 are reached in full. A hidden cap at 10 or 100
  must fail.
- **Width:** a synthetic fan-out of 1,000 over 4 levels, and the densest real hub on Kafka L:
  time, memory, and it finishes within the time limit.
- **Cycles:** self-recursion, mutual recursion, a cycle of 10,000 nodes, and a cycle combined with
  a fan-out of 1,000. Each finishes, each node is returned once, and the depths are correct.

### Open in the exact-call-edges feature

Re-run the unbounded spike on the denser graph (today 78% of call edges end on ghosts).

## 10. Traversal output: edges and paths — decided `[agreed 2026-11-11]`

- **BFS tree, one entry per returned node:** its predecessor on its shortest path, the edge kind
  and the edge precision. The tool can rebuild one shortest path per node from it, never all
  paths.
- **Induced edges** (the edges between reached nodes): only on request, with their own budget.
- **Short handles** in results (`n1`, `n2`, …), mapped to full IDs on the server side. Full hash
  IDs cost tokens.
- **The BFS loop runs in Python,** one query per level, with the visited set in Python (Q24 A).
  The round-trip with the real driver over TCP is measured in the `A-SENS-02` dev work.

Token count per node: lines with handle, predecessor, edge kind and precision, in JSON and in
compact form (`.tmp/spike/tokens/*_tree.{jsonl,tsv}`). Count: pending (GB10 `/tokenize`, LAN
only, Q25 A; the URL is still missing).

## 11. Default budget — decided `[agreed 2026-11-11]` (Q22 C)

- **The default budget comes from the calling model's context window** (a share of it), so a
  small model gets fewer nodes.
- **Budget 0** = the summary and a cursor only (option A, as a special case).
- **Tokens are estimated as bytes / 3** (conservative for code and paths) until a tokenizer is
  available.
- **Open: calibration.** Replace bytes / 3 with the measured value once the GB10 runs again (its
  `/tokenize`, LAN only). Also open: the share of the context window.

### Bytes per node by path form (BFS-tree lines from L, `.tmp/spike/tokens/path_forms.py`)

"Service root" here = Kafka's top-level module.

| Result (nodes / files) | Form | Compact | JSON | ≈ tokens, compact (bytes / 3) |
|---|---|---|---|---|
| Hub callers (2,787 / 660) | repo path | 191 | 271 | 64 |
| | (a) service-relative | 182 | 262 | 61 |
| | (b) grouped by file | 121 | 197 | 40 |
| | (c) no path | 101 | 172 | 34 |
| Reach, 2 kinds (1,172 / 55) | repo path | 144 | 220 | 48 |
| | (a) service-relative | 132 | 212 | 44 |
| | (b) grouped by file | 82 | 154 | 27 |
| | (c) no path | 79 | 150 | 26 |
| Subtypes (124 / 124) | repo path | 161 | 241 | 54 |
| | (a) service-relative | 153 | 233 | 51 |
| | (b) grouped by file | 155 | 245 | 52 |
| | (c) no path | 72 | 143 | 24 |

- (a) saves little. Most of a Java path is `src/main/java/<package>`, which repeats the qualified
  name.
- (b) saves 37–43% when the nodes share files, and costs about 1% when each node is in its own
  file.
- (c) is the smallest, but the agent then needs one `get()` per file it wants to open.
- Compact is 30–50% smaller than JSON in every form.

## 12. Open in B-FLOW-04: the index build lock with the real embedding

Measure the HNSW build lock again with the real embedding dimension (768–1,024 likely). `A-SENS-02`
measured 384 dimensions on L: 21.5 s at `maintenance_work_mem` 2 GB, 64.2 s at 64 MB
(`a_sens_02_graph_store_spike_2026-11-11.md`, Extension 3).

## 13. Libraries — decided `[agreed 2026-11-12]` (A-SENS-02 Q37 A)

`A-SENS-02` builds and tests the mechanism: a library schema, its role, an API schema of
owner-rights views, granted to named consumers. `B-FLOW-04` decides, from `context.yaml`, which
unit is a library, which of its symbols are public, and which services consume it.
