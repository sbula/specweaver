# A-SENS-02 spike: the code graph in Postgres, tables against Apache AGE (2026-11-11)

The measurement behind `A-SENS-02` Q6. The user decides after reading it. Every AGE number is
**measured on the release candidate** (`1.8.0~rc0`), the only build PGDG ships for PostgreSQL 18.

## Setup

- **Data:** Apache Kafka, commit `5a3b9b32` (2026-11-09), Java only, graph built by
  `sw graph build`'s builder (`GraphBuilder`, in memory) and exported to CSV. Three nested samples:

  | Sample | Folders | Code lines (no comments, no blank lines) | Nodes | Edges | Ghost calls |
  |---|---|---|---|---|---|
  | S | `raft`, `metadata` | 87,644 | 8,301 | 42,814 | 71.8% |
  | M | S + `group-coordinator`, `storage` | 245,634 | 19,402 | 121,737 | 72.6% |
  | L | all Java | 1,138,856 | 96,589 | 561,570 | 77.9% |

  Without test code: S 38,910 lines, M 88,744, L 440,129 (L: 50,354 nodes, 157,132 edges, 76.6%
  ghost calls). Tests are 56-64% of the code and 74-78% of the calls; removing them does not lower
  the ghost share, it removes the largest ghost hubs (`assertEquals` 14,085 calls on L).
- **Server:** one local image `FROM pgvector/pgvector@sha256:2547711f871f…af79b` (0.8.7, PG 18.6)
  plus `postgresql-18-age 1.8.0~rc0-2.pgdg12+1` from PGDG apt. Rootless Podman, `--network none`.
- **Config, the same for both options:** `shared_buffers=4GB`, `work_mem=256MB`,
  `maintenance_work_mem=2GB`, `effective_cache_size=16GB`, `max_parallel_workers_per_gather=4`.
  89 GB RAM, 24 CPUs; every sample fits in memory.
- **Tables option:** `nodes(id, hash, kind, name, file, ghost, emb vector(384))`,
  `edges(src, dst, kind, ghost)`, btree on `(src, kind)` and `(dst, kind)`, HNSW on `emb`
  (cosine). Queries are `WITH RECURSIVE`.
- **AGE option:** one graph per sample, vertex label `Node`, one edge label per kind, btree on the
  vertex `nid` property and on every edge table's `start_id` and `end_id`. Queries are Cypher.
  Vectors stay in the tables option's table: AGE has no vector index.
- **Vectors:** random, 384 dimensions, one per node. They measure speed, never relevance.
- **Method:** per sample, option and query, Postgres is restarted, then one `psql` session runs the
  query once (**cold**), five more times (**warm**, median) and once under
  `EXPLAIN (ANALYZE, BUFFERS)`. Statement timeout 120 s; none was hit. Cold means Postgres's own
  cache is empty; the operating system's file cache cannot be dropped in a rootless container.
- **Correctness:** for every query and sample the three runs return the same count.

## Queries

- **Q1** everything that calls a function within 3 steps (reverse `CALLS`), for the most-called
  function (`hub`), one at the 99th percentile (`p99`) and one at the median. On L the hub is
  `Event.getMessage` (1,683 callers): mostly `Throwable.getMessage` calls a bare-name match gave
  it, the parser defect the exact-call-edges feature fixes.
- **Q2** the same for the hub at depth 5: the variable-length path test.
- **Q3** everything 2 steps forward from the file with the most outgoing edges, every edge kind,
  with and without ghost nodes.
- **Q4** hybrid: the 10 nearest vectors (non-ghost), then 2 steps forward, every edge kind. With
  tables one statement; with AGE two (the hits, then Cypher over them as a literal list).

## Results (ms)

"AGE naive" writes the pattern as `(a)-[:CALLS*1..3]->(x {nid: N})`; "AGE anchored" as
`MATCH (x:Node) WHERE x.nid = N MATCH (x)<-[:CALLS*1..3]-(a)`. Both return the same rows.

| Query | Sample | Result | Tables cold / warm | AGE naive cold / warm | AGE anchored cold / warm |
|---|---|---|---|---|---|
| Q1 callers<=3 hub | S | 206 | 2.7 / 0.3 | 70.9 / 41.1 | 20.3 / 1.6 |
| Q1 callers<=3 hub | M | 964 | 5.8 / 1.5 | 164.7 / 81.9 | 52.5 / 4.2 |
| Q1 callers<=3 hub | L | 2612 | 35.5 / 16.3 | 700.6 / 414.1 | 204.5 / 7.0 |
| Q1 callers<=3 p99 | S | 84 | 2.7 / 0.2 | 63.1 / 29.4 | 20.4 / 1.1 |
| Q1 callers<=3 p99 | M | 93 | 1.6 / 0.2 | 158.3 / 75.0 | 40.7 / 0.8 |
| Q1 callers<=3 p99 | L | 73 | 2.4 / 0.3 | 699.7 / 404.8 | 317.0 / 1.1 |
| Q1 callers<=3 median | S | 11 | 2.0 / 0.2 | 54.8 / 29.1 | 15.2 / 0.6 |
| Q1 callers<=3 median | M | 4 | 1.9 / 0.2 | 144.8 / 75.0 | 39.6 / 0.5 |
| Q1 callers<=3 median | L | 3 | 1.3 / 0.2 | 605.1 / 405.7 | 310.5 / 0.8 |
| Q2 callers<=5 hub | S | 206 | 1.7 / 0.2 | 61.8 / 37.2 | 17.1 / 1.0 |
| Q2 callers<=5 hub | M | 1043 | 8.7 / 2.3 | 187.8 / 98.5 | 62.0 / 6.3 |
| Q2 callers<=5 hub | L | 2779 | 29.6 / 13.0 | 676.4 / 464.0 | 326.9 / 15.2 |
| Q3 forward<=2 file with ghosts | S | 640 | 10.9 / 3.8 | 16.6 / 2.7 | 20.0 / 3.1 |
| Q3 forward<=2 file with ghosts | M | 2079 | 28.5 / 8.2 | 89.1 / 36.7 | 96.8 / 36.8 |
| Q3 forward<=2 file with ghosts | L | 2801 | 36.3 / 11.0 | 218.9 / 48.2 | 370.2 / 49.4 |
| Q4 hybrid knn10+2 with ghosts | S | 98 | 10.2 / 1.7 | 18.9 / 1.3 | 24.0 / 1.6 |
| Q4 hybrid knn10+2 with ghosts | M | 208 | 14.3 / 1.2 | 41.1 / 1.7 | 40.6 / 1.7 |
| Q4 hybrid knn10+2 with ghosts | L | 145 | 20.0 / 8.0 | 177.5 / 1.1 | 279.6 / 2.4 |
| Q3 forward<=2 file no ghosts | S | 369 | 13.9 / 6.2 | 20.5 / 3.5 | 22.2 / 2.7 |
| Q3 forward<=2 file no ghosts | M | 1446 | 38.0 / 13.6 | 64.1 / 27.0 | 81.6 / 25.1 |
| Q3 forward<=2 file no ghosts | L | 2154 | 88.0 / 50.4 | 270.2 / 38.4 | 214.2 / 29.0 |
| Q4 hybrid knn10+2 no ghosts | S | 28 | 13.0 / 2.2 | 26.2 / 1.3 | 21.4 / 1.5 |
| Q4 hybrid knn10+2 no ghosts | M | 87 | 21.7 / 8.0 | 49.6 / 2.1 | 54.0 / 1.4 |
| Q4 hybrid knn10+2 no ghosts | L | 97 | 10.2 / 0.7 | 175.3 / 1.2 | 173.8 / 1.3 |

## What the numbers say

1. **Warm, the two are close when AGE's query is anchored.** Q1/Q2 warm: tables 0.2-16 ms, AGE
   anchored 0.5-15 ms. Q3 and Q4 warm are within a factor of about 2 either way.
2. **AGE's speed depends on how the Cypher is written.** The naive form starts the path search at
   every vertex (`age_vle` with `loops=96589` on L) and ignores the `nid` index
   (`Seq Scan on "Node" x`); it costs about 405 ms on L even for 3 results, and grows with the
   graph, not the answer. The anchored form costs 0.8 ms for the same query.
3. **AGE is slow cold, and the cost grows with the graph.** First query after a restart, Q1 on L:
   tables 1-36 ms, AGE anchored 200-330 ms (S about 20 ms, M about 40-60 ms). A new connection pays
   it again.
4. **Ghost nodes change the answers, not the times.** L Q3: 2,801 nodes with ghosts, 2,154
   without; times within noise.

## Other findings about AGE (measured on the RC)

- **Maintenance:** 1.8.0 was released upstream on 06 Aug 2026 (Apache release catalog); in November
  PGDG ships only `1.8.0~rc0` for PostgreSQL 18. A decision for AGE needs the final release.
- No edge-type choice in a variable-length path: `[:CALLS|IMPORTS*0..2]` is a syntax error.
- Cypher cannot read the rows of an SQL query, so vector search plus graph expansion is two
  statements with the hit ids passed as text. With tables it is one statement.
- `load_labels_from_file` reads only below `/tmp/age/` inside the server, and stores every value as
  text unless `load_as_agtype` is true.
- Open, measured later with the real driver: parsing `agtype` results from Python.

## Not measured here

- The SCIP reindex time (the exact-call-edges feature, with Ktor and scip-kotlin; the user,
  2026-11-11).
- Concurrency, and write speed for deltas (the AGE loader bulk-writes; a delta writes rows).

Scripts: `.tmp/spike/` (gitignored): `sample_census.py`, `run_spike.py`, `sql/`, `explain/`.

## Extension: unbounded traversal on L (2026-11-11)

The user wants arbitrary depth with no fixed limit. Every AGE result is measured on RC.

**Method.** The driver is `.tmp/spike/run_unbounded.py`. For each query and option, Postgres is
restarted, then one `psql` session runs: a cold run, then 5 warm runs (the median is reported)
and `EXPLAIN (ANALYZE, BUFFERS)`.
- The Postgres config is the same as above. `statement_timeout` is 300 s and `temp_file_limit`
  is 20 GB.
- The container is capped at 16 GB of memory. This protects the other services on the host.
- Memory is the backend's peak RSS (`VmHWM`). It includes the shared buffers that the query
  touched.

**The table forms:**
- **CYCLE + BFS:** `UNION ALL` with `SEARCH BREADTH FIRST` and `CYCLE`. This walks paths, so
  "depth" is the longest simple path found.
- **UNION set:** `UNION` on the node only. Each node is kept once, and there is no depth.
- **bfs():** a plpgsql frontier loop. Each node is visited once, at its smallest depth, one level
  per step.

**Start nodes:**
- hub `Event.getMessage` (591);
- type `ApiException` (10499);
- its subtype `ClusterAuthorizationException` (10513);
- path A = `GroupMetadataManager.streamsGroupHeartbeat` (42028) → B = `standbyAndWarmupTasks`
  (43679);
- file `GroupMetadataManagerTest.java` (44568).

| Query | Option | Finishes | Cold ms | Warm ms | Result | Max depth | Peak RSS MB |
|---|---|---|---|---|---|---|---|
| U1 callers closure, hub | tables CYCLE+BFS | yes | 28.8 | 10.2 | 2,787 | 9 (path) | 100 |
| | tables UNION set | yes | 504.9 | 392.3 | 2,787 | — | 186 |
| | tables bfs() | yes | 17.3 | 9.1 | 2,787 | 7 | 45 |
| | AGE `<-[:CALLS*]-` | yes | 199.5 | 24.9 | 2,787 | 9 (path) | 166 |
| U2 subtypes closure | tables CYCLE+BFS | yes | 2.1 | 0.3 | 124 | 3 | 24 |
| | tables UNION set | yes | 2.0 | 0.4 | 124 | — | 24 |
| | tables bfs() | yes | 6.9 | 2.9 | 124 | 3 | 32 |
| | AGE `<-[*]-` + kind filter | **no**: 20 GB temp files after 20 s | — | — | — | — | 408 |
| U3 supertypes closure | tables CYCLE+BFS | yes | 1.2 | 0.1 | 5 | 5 | 24 |
| | tables UNION set | yes | 1.7 | 0.2 | 5 | — | 24 |
| | tables bfs() | yes | 6.4 | 1.6 | 5 | 5 | 32 |
| | AGE `-[*]->` + kind filter | yes | 209.7 | 0.8 | 5 | 5 | 162 |
| U6 reach CALLS+CONTAINS, file | tables CYCLE+BFS | yes | 79.5 | 45.8 | 1,172 | 5 (path) | 99 |
| | tables UNION set | yes | 86.9 | 54.9 | 1,172 | — | 139 |
| | tables bfs() | yes | 13.7 | 5.7 | 1,172 | 5 | 35 |
| | AGE `-[*]->` + kind filter | yes | 79,014 | 78,643 | 1,172 | 5 | 431 (+640 MB temp) |
| U4 path exists A→B | tables CYCLE+BFS, first hit | yes | 3.4 | 1.3 | yes, 5 | — | 25 |
| | tables bfs(), target | yes | 6.4 | 2.3 | yes, 5 | — | 32 |
| | AGE `-[:CALLS*]->` LIMIT 1 | yes | 174.2 | 0.6 | yes | — | 161 |
| U5 shortest path A→B | tables (U4 forms give it) | yes | 3.4 | 1.3 | 5 | — | 25 |
| | AGE min over all paths (no `shortestPath`) | yes | 190.7 | 1.0 | 5 | — | 161 |
| Q3 forward ≤2, file, no ghosts | tables, ghost flag on the edge | yes | 29.3 | 6.2 | 2,154 | 2 | 107 |

**Findings:**
1. **All counts agree** across all forms that finished.
2. **AGE cannot filter edge kinds while it walks.** It has no alternation `[:A|B*]`, and
   `all(...)` over the path fails ("no relation entry for relid 2"). The working form walks every
   edge kind and filters the paths afterwards. So U2 does not finish, and U6 takes 79 s, against
   6–14 ms for bfs(). One edge kind alone (U1, U3, U4) is fast warm.
3. **AGE has no `shortestPath`.** "Minimum over all paths" works here only because the call graph
   is shallow.
4. **Path forms (CYCLE, AGE) have no upper bound.** They are fast here because 78% of call edges
   end on ghosts, so the graph is shallow. Exact call edges make it denser, and the path count can
   grow exponentially. Their "depth" is the longest path (9), not the distance (7).
5. **bfs() has a bound: each node and edge at most once.** It is the only form that gives the
   smallest depth per node, can stop between levels and report "stopped at depth N", and can
   count per level. A single recursive CTE cannot do that: at a timeout it returns nothing.
6. **The Q3 gap was in the query, not the store.** No index was missing (`edges_src` is used).
   Postgres guessed 542,341 rows instead of 2,914, so it hashed all 86,242 nodes for the ghost
   filter (38 of the 50 ms). The ghost flag already sits on the edge (`to_ghost`). Ghosts have
   no outgoing edges, and the flag matches the node flag on all edges (both checked: 0
   exceptions). With the flag on the edge: cold 65 → 29 ms, warm 49 → 6.2 ms. AGE anchored is
   214 / 29 ms. With `jit = off`, it is 4.3 ms warm, but that is a config change for both options.

## Extension 2: where the BFS loop runs, and the frontier storage (2026-11-11)

**Method.** The driver is `.tmp/spike/run_bfs_loop.py`, with a time limit of 2,000 ms, checked
once per level.
- For each case and form, Postgres is restarted. The table shows a cold run and the median of 5
  warm runs.
- The client is one long-lived `psql` process inside the container, because no Python Postgres
  driver is installed. Each statement is one round-trip over a local socket (about 0.035 ms per
  level here). Over TCP, or to a remote sidecar, a round-trip costs more. The real driver is
  measured in the `A-SENS-02` dev work.

**The 4 forms:**
- **server temp table:** a PL/pgSQL function with a temp table (primary key + depth index).
- **server arrays:** a PL/pgSQL function with `int[]` and `EXCEPT` against the visited array.
- **Python, set:** the visited set lives in Python, and each level sends the frontier as an
  array.
- **Python, temp table:** the loop runs in Python, and the state lives in a session temp table.

| Case | Form | Cold ms | Warm ms | Round-trips | Peak RSS MB |
|---|---|---|---|---|---|
| L hub callers (2,787, depth 7) | server temp table | 31.3 | 14.7 | 1 | 45 |
| | server arrays | 19.9 | 6.8 | 1 | 43 |
| | Python, set | 14.6 | 5.6 | 8 | 37 |
| | Python, temp table | 27.3 | 13.5 | 10 | 40 |
| chain 1,000 | server temp table | 49.0 | 45.7 | 1 | 33 |
| | server arrays | 55.5 | 35.8 | 1 | 29 |
| | Python, set | 74.4 | 34.9 | 1,001 | 22 |
| | Python, temp table | 110.6 | 92.3 | 1,003 | 27 |
| chain 10,000 | server temp table | 321.4 | 266.0 | 1 | 38 |
| | server arrays | 1,452.2 | 1,415.2 | 1 | 30 |
| | Python, set | 344.4 | 345.2 | 10,001 | 25 |
| | Python, temp table | 936.6 | 867.4 | 10,003 | 36 |
| wide (60,000 per level, 2 levels) | server temp table | 235.6 | 219.7 | 1 | 54 |
| | server arrays | 68.3 | 99.3 | 1 | 60 |
| | Python, set | 96.4 | 90.6 | 3 | 51 |
| | Python, temp table | 214.3 | 204.4 | 5 | 50 |

All 16 results are correct (count and depth). No run reached the time limit.

**Findings:**
1. **Arrays grow quadratically with depth.** Each level compares against the whole visited array
   (`EXCEPT`): 1.4 s on the 10,000 chain. On the 60,000 frontier, arrays are the fastest server
   form (68 ms against 236 ms).
2. **The temp table has a fixed setup cost** (create + index, about 10 ms per call). It is linear
   in depth. It is the slowest form on the wide frontier: each insert also updates 2 indexes.
3. **Python with the set in Python** is the fastest or close to it in all 4 cases. Its cost per
   level is one round-trip. On the 10,000 chain it is as fast as the best server form. A round-trip
   of 0.1 ms (TCP) would make that chain about 1 s, but the real graph's depth is 7.

## Extension 3: lock time of an HNSW build inside a transaction (2026-11-12)

The migrations run in one transaction (Q32 A), so an index is built with plain `CREATE INDEX`,
never `CONCURRENTLY`. Measured on L: 96,589 vectors of 384 dimensions, `vector_cosine_ops`, 2
parallel maintenance workers. A second session probed the table during the build, each probe with
`lock_timeout = 500ms`. Script: `.tmp/spike/hnsw_lock.py`.

| `maintenance_work_mem` | Build = lock time | Read | Vector search | Write |
|---|---|---|---|---|
| 2 GB (spike config) | 21.5 s | works (95 ms) | works, old index (106 ms) | blocked (lock timeout) |
| 64 MB (Postgres default) | 64.2 s | works | works | blocked (lock timeout) |

- A plain `CREATE INDEX` takes a SHARE lock: reads and searches go on, writes wait until the
  transaction ends.
- The graph fits in memory at 2 GB, so the build is 3× faster. The official image keeps the
  64 MB default unless we set it.
- One run each; the build ran inside `BEGIN … ROLLBACK`, so no index was kept.
