# Topic 02: Context & Sensors (Perception)

Capabilities for the AST, knowledge graphs, and workspace understanding.

Seven keyed fields per entry, plus optional `Limits:` and `Note:` — no prose (`R-ENTRY`). Values are written plainly.
**🟡 marks a guess** · **🔴 marks nothing found**. Markers are the exception.

## DAL-E: Prototyping

* **`E-SENS-01` ✅: Loom FS Tools** (Legacy: Step 1b)
  > - **Purpose:** Give agents filesystem access that is role-gated, so an agent sees only the files its task allows
  > - **Trigger:** When an agent or the engine reads or writes a file
  > - **Precondition:** —
  > - **Reads:** the workspace, within whitelisted boundaries
  > - **Produces:** file access, refused outside the boundary
  > - **Enables:** every agent tool that touches disk
  > - **Done when:** an agent cannot read a file outside its granted boundary

* **`E-SENS-02` ✅: Agentic Research Tools** (Legacy: 3.10)
  > - **Purpose:** Let the LLM look things up itself — read files, search the web — instead of guessing from what it was handed
  > - **Trigger:** When an LLM call is made with tools enabled
  > - **Precondition:** `E-SENS-01` → boundary enforcement
  > - **Reads:** workspace files · the web
  > - **Produces:** tool results returned into the model's context
  > - **Enables:** Reviewer · Planner
  > - **Done when:** six tools — four filesystem, two web — resolve through one provider-agnostic call

* **`E-SENS-03` ✅: Context Ledgers & Workspace Boundaries**
  > - **Purpose:** Restrict what an agent can see to the scope of its assigned task, not the whole repo
  > - **Trigger:** When a task is dispatched to an agent
  > - **Precondition:** —
  > - **Reads:** the task's declared scope
  > - **Produces:** a task-scoped grant — READ / WRITE / FULL
  > - **Enables:** `E-SENS-01` · `E-SENS-02` · the `US-5` contract
  > - **Done when:** an agent's grant is built from its task and refuses everything outside it

## DAL-D: Internal Tooling

* **`D-SENS-01` ✅: Topology Graph** (Legacy: Step 7)
  > - **Purpose:** Know which module depends on which, so impact can be judged and prompts can carry the right neighbours
  > - **Trigger:** When the project is scanned
  > - **Precondition:** —
  > - **Reads:** `context.yaml` files
  > - **Produces:** memory → an in-memory dependency graph
  > - **Enables:** impact analysis · context-enriched prompts
  > - **Done when:** 🟡 a missing `context.yaml` can be generated from the code

* **`D-SENS-02` ✅: Polyglot AST Extractor** (Legacy: 3.22)
  > - **Purpose:** Read and edit code by symbol rather than by line, so an agent never has to hold a whole file
  > - **Trigger:** When a caller asks for a skeleton, a symbol, or a symbol edit
  > - **Precondition:** —
  > - **Reads:** source files in the supported languages
  > - **Produces:** memory → skeletons, symbol bodies, and applied AST mutations
  > - **Enables:** `context_assembler` · every AST-editing tool · `B-SENS-02`
  > - **Done when:** read and write both work across five languages

* **`D-SENS-03` ✅: Polyglot Expansion (C++, Go)** (Legacy: 3.32e)
  > - **Purpose:** Cover the languages enterprise targets actually use — systems, cloud, schemas, and spec documents
  > - **Trigger:** When a file of one of these types is parsed
  > - **Precondition:** `D-SENS-02` → the extractor to extend
  > - **Reads:** Markdown · C/C++ · Go · standard ANSI SQL
  > - **Produces:** memory → parsed symbols per language
  > - **Enables:** spec traceability (Markdown) · legacy and cloud codebases · the DB context harness
  > - **Done when:** all four parsers report symbols with dot-notation and capability filtering

* **`D-SENS-04` 🔜: Parallel AST Extraction Engine**
  > - **Purpose:** Parse very large codebases concurrently, when a serial scan is measurably too slow
  > - **Trigger:** When a scan's wall time hurts on a real target
  > - **Precondition:** `D-SENS-02` · a measured scan time on a real target — none is recorded
  > - **Reads:** source files
  > - **Produces:** 🟡 the same ASTs, extracted in parallel via Rust Rayon through PyO3
  > - **Enables:** 🔴
  > - **Done when:** 🔴

* **`D-SENS-05` 🔜: Markdown AST Mutators**
  > - **Purpose:** 🟡 Inject and extract structured data in spec documents reliably, rather than by text matching
  > - **Trigger:** When a spec document is written to or read structurally
  > - **Precondition:** `D-SENS-03` → the Markdown parser
  > - **Reads:** spec documents
  > - **Produces:** 🟡 edited spec documents
  > - **Enables:** 🔴
  > - **Done when:** 🔴

## DAL-C: Enterprise Standard

* **`C-SENS-01` ✅: Spec-Mention Detection** (Legacy: 3.11)
  > - **Purpose:** When the model names a file or spec it has not been shown, fetch it and hand it back — instead of letting it invent the contents
  > - **Trigger:** When an LLM response is received
  > - **Precondition:** `E-SENS-01` → boundary enforcement
  > - **Reads:** LLM responses · the files they name
  > - **Produces:** memory → mentioned files injected into the follow-up call
  > - **Enables:** Reviewer → follow-up calls that see what was referenced
  > - **Done when:** a named file is pulled into the next call, and one outside the boundary is refused

* **`C-SENS-02` ✅: Smart Scan Exclusions** (Legacy: 3.32b)
  > - **Purpose:** Keep binaries, caches and vendor trees out of every scan, so the agent's view is the project and not its litter
  > - **Trigger:** When files are collected for any scan
  > - **Precondition:** —
  > - **Reads:** file extensions · default patterns · per-project overrides · `.specweaverignore`
  > - **Produces:** memory → the filtered file set every scan uses
  > - **Enables:** every scan, parse and hash
  > - **Done when:** three tiers apply in order and a project override wins

* **`C-SENS-03` 🔜: Symbol Index Gates** (Legacy: 4.1)
  > - **Purpose:** 🟡 Refuse generated code that calls a symbol which does not exist — an anti-hallucination gate
  > - **Trigger:** 🟡 After code is generated, before it is accepted
  > - **Precondition:** 🟡 a symbol index — `B-SENS-02` is the nearest candidate
  > - **Reads:** 🟡 generated code
  > - **Produces:** 🔴
  > - **Enables:** 🔴
  > - **Done when:** 🔴

* **`C-SENS-04` 🔜: Infrastructure-as-Code Extraction (HCL2)**
  > - **Purpose:** Understand infrastructure the same way as code — what resources exist, what depends on what, and where the spec has drifted
  > - **Trigger:** When a Terraform or OpenTofu file is parsed
  > - **Precondition:** `D-SENS-02` → the extractor to extend
  > - **Reads:** HCL2 files
  > - **Produces:** 🟡 cloud resource nodes and dependencies
  > - **Enables:** 🟡 IaC spec-drift validation
  > - **Done when:** 🔴

* **`C-SENS-05` 🔮: Embedded SQL Extraction**
  > - **Purpose:** Link code to the database it actually touches, by parsing SQL written inside host languages
  > - **Trigger:** When a host-language file contains an SQL string
  > - **Precondition:** `D-SENS-03` → the SQL parser
  > - **Reads:** Python, Java and similar sources containing embedded SQL
  > - **Produces:** 🟡 cross-domain edges between code and schema
  > - **Enables:** 🔴
  > - **Done when:** 🔴
  > - **Note:** deferred out of `B-SENS-02` to prevent scope creep

* **`C-SENS-06` ⚰️ RETIRED:** *(Event-Sourced 4D Graph — retired 2026-08-20 by the
  [benefit review](../../analysis/benefit_chain_analysis_2026-08-20.md): no story claims it, no
  consumer ever asked a point-in-time architecture question, and git already holds history.
  ID is dead — do NOT reuse.)*

* **`C-SENS-07` 🔜: Polyglot Expansion (TypeSpec)**
  > - **Purpose:** 🟡 Map API contracts written in TypeSpec, so cross-platform interfaces are visible to the graph
  > - **Trigger:** When a TypeSpec file is parsed
  > - **Precondition:** `D-SENS-02` → the extractor to extend · a community tree-sitter grammar
  > - **Reads:** TypeSpec files
  > - **Produces:** 🟡 API contract symbols
  > - **Enables:** 🟡 `A-SENS-04` cross-service linkage
  > - **Done when:** 🔴

## DAL-B: High-Assurance

* **`B-SENS-01` ✅: Artifact Lineage Graph** (Legacy: 3.17)
  > - **Purpose:** Know which LLM produced which artifact, so provenance and cost can be attributed per feature
  > - **Trigger:** When an artifact is generated
  > - **Precondition:** —
  > - **Reads:** generation events
  > - **Produces:** db → lineage records · `#sw-artifact` tags in the artifacts
  > - **Enables:** `A-UI-01` tamper-evidence · `D-UI-06` telemetry · cost-per-feature
  > - **Done when:** every generated artifact traces back to the model and request that made it

* **`B-SENS-02` ✅: Knowledge Graph Builder** (Legacy: 3.32f)
  > - **Purpose:** Hold a class- and function-level map of the codebase that survives restarts, so questions about structure are answered exactly rather than by search
  > - **Trigger:** When `sw graph build` is run
  > - **Precondition:** `D-SENS-02` → parsed ASTs
  > - **Reads:** source files of every supported language
  > - **Produces:** db → nodes and edges in SQLite · memory → NetworkX for fast queries
  > - **Enables:** `B-SENS-09` · `B-VAL-07` · blast radius (`B-EXEC-03`, `A-FLOW-04`) · `A-SENS-04` · `C-UI-01`
  > - **Done when:** a rebuild reproduces the graph without re-reading everything from scratch
  > - **Limits:** a stored node keeps no `kind` or `name`; six languages mis-file their types; a call resolves only on a globally unique bare name

* **`B-SENS-03` 🔧: AST Semantic Chunking** (Legacy: 4.2)
  > - **Purpose:** Cut code into chunks a retrieval hit can be cited from — one per top-level symbol, each carrying its path and symbol
  > - **Trigger:** When a file is chunked for the vector store
  > - **Precondition:** `D-SENS-02` → symbols per file
  > - **Reads:** source files
  > - **Produces:** memory → chunks carrying path, symbol and language
  > - **Enables:** `A-SENS-02` vector store · `B-FLOW-04` retrieval
  > - **Done when:** an oversized symbol splits into numbered parts, and a parser failure falls back to line windows
  > - **Note:** one of two Core MVS items in `US-11`. A TypeScript interface is never reported as a symbol, so it can never become its own chunk

* **`B-SENS-04` 🔮: Static Control Flow Graph (CFG)**
  > - **Purpose:** 🟡 Know which branches can execute, so analysis can follow paths rather than just call names
  > - **Trigger:** 🔴
  > - **Precondition:** `B-SENS-02` → the one graph this layers onto
  > - **Reads:** statically typed sources only — Java, C++
  > - **Produces:** 🟡 True/False execution edges on the existing graph
  > - **Enables:** 🔴
  > - **Done when:** 🔴
  > - **Note:** a layer on `B-SENS-02`'s single graph, never a second store (`ADR-006` decision 4)

* **`B-SENS-05` 🔮: Static Dataflow Solver**
  > - **Purpose:** 🟡 Know where a value is defined and where it is used, so changes to data can be traced
  > - **Trigger:** 🔴
  > - **Precondition:** `B-SENS-02` · 🟡 likely `B-SENS-04`
  > - **Reads:** statically typed sources only
  > - **Produces:** 🟡 def-use chains, via Kildall's framework
  > - **Enables:** 🔴
  > - **Done when:** 🔴
  > - **Note:** a layer on the single graph, same as `B-SENS-04`. Highly experimental

* **`B-SENS-06` 🔜: OSV Vulnerability Feed Ingestion**
  > - **Purpose:** Answer "do we actually call the vulnerable function", not just "is the package present" — which is what a plain dependency scanner cannot do
  > - **Trigger:** 🟡 When the OSV feed is ingested or the workspace is scanned
  > - **Precondition:** `TECH-068` → `CALLS` edges, for the reachability half
  > - **Reads:** the OSV database · the workspace topology graph
  > - **Produces:** 🟡 CVE-to-node mappings with reachability
  > - **Enables:** fleet remediation (`US-26`)
  > - **Done when:** 🔴

* **`B-SENS-07` 🔜: Language-Agnostic Dependency Resolution**
  > - **Purpose:** Turn every language's import syntax into one canonical module identity, so a boundary question is one graph query instead of five external tools — two of which are stubs
  > - **Trigger:** When imports are resolved during a graph build
  > - **Precondition:** `B-SENS-02` → the ontology to resolve into
  > - **Reads:** import statements in every supported language
  > - **Produces:** canonical `MODULE` identities in the graph
  > - **Enables:** `INT-US-20` P-5 · the brownfield journeys in `US-11`, `US-12`, `US-26`
  > - **Done when:** a time-boxed dual-run against `tach` ends in `tach`'s removal
  > - **Note:** supersedes the Python special case rather than joining it

* **`B-SENS-08` 🔜: Framework-Semantic Graph Edges**
  > - **Purpose:** Dependency injection, routes and listeners produce no call site, so a call graph over framework code lies. Turn the framework's own annotations into real edges
  > - **Trigger:** When a file using a known framework is parsed
  > - **Precondition:** `B-SENS-02` → the builder · the five delivered framework schemas
  > - **Reads:** framework annotations — Spring Boot, Quarkus, NestJS, FastAPI, Actix-web
  > - **Produces:** typed edges — injection, routes, listeners (`CONSUMES`, `FULFILLS`, `PUBLISHES`, `SUBSCRIBES`)
  > - **Enables:** `B-SENS-09` · `B-VAL-07` · blast radius · `A-SENS-04`'s cross-service edges
  > - **Done when:** 🔴
  > - **Note:** `ADR-006` calls this a precondition for every reader, not an enhancement. JVM first (`US-12`)

* **`B-SENS-09` 🔜: Deterministic Context Packing**
  > - **Purpose:** Given the symbol a task will change, put exactly its callers, callees and type contracts in the prompt — selection, not compression
  > - **Trigger:** When a prompt is assembled for a task with a known target symbol
  > - **Precondition:** `B-SENS-02` → the graph · `TECH-068` → real edges · `B-FLOW-04` → candidate symbols
  > - **Reads:** the knowledge graph
  > - **Produces:** prompt → a packed subgraph closure, 1–2 hops
  > - **Enables:** `sw draft` · `sw implement` · `sw review`
  > - **Done when:** 🔴
  > - **Note:** the only graph reader on a user path. Receives candidates from `B-FLOW-04`, never the reverse

## DAL-A: Mission-Critical

* **`A-SENS-01` ✅: Deep Semantic Hashing** (Legacy: 3.32)
  > - **Purpose:** Know a file changed when anything it imports changed, so the topology stays in sync without crawling the whole project
  > - **Trigger:** When a hash is read
  > - **Precondition:** `D-SENS-01` → the topology graph
  > - **Reads:** source files and their import graph
  > - **Produces:** db → Merkle-tree dependency hashes
  > - **Enables:** incremental pipeline bypassing · `A-SENS-03`
  > - **Done when:** a change to an imported module changes the importer's hash

* **`A-SENS-02` 🔜: Postgres pgvector Sidecar** (Legacy: 3.33 / 5.1)
  > - **Purpose:** Run graph and vectors in one transactional backend at scale, instead of two local stores
  > - **Trigger:** 🟡 When the project is switched from local mode to sidecar mode
  > - **Precondition:** `B-SENS-02` → graph content · `B-SENS-03` → chunks to embed
  > - **Reads:** the local SQLite graph and chunk store
  > - **Produces:** db → PostgreSQL with Apache AGE and pgvector
  > - **Enables:** cross-service GraphRAG · `A-SENS-04`
  > - **Done when:** 🟡 the same queries answer identically in local and sidecar mode

* **`A-SENS-03` 🔜: Event Trigger for Semantic-Hash Sync** (Legacy: 5.2)
  > - **Purpose:** Invoke `A-SENS-01`'s incremental sync on a file or commit event, once something needs a live graph rather than a read-time one
  > - **Trigger:** When a file changes or a commit lands
  > - **Precondition:** `A-SENS-01` → the sync it invokes · a daemon-mode consumer — none exists
  > - **Reads:** file and commit events
  > - **Produces:** a sync call — not an independent update path
  > - **Enables:** 🟡 `sw serve` live graph · `E-UI-03` watcher
  > - **Done when:** 🔴

* **`A-SENS-04` 🔮: Federated Microservice System Graph**
  > - **Purpose:** See how services connect through their external interfaces alone — REST, Kafka, queues — without dragging every service's internals into context
  > - **Trigger:** 🔴
  > - **Precondition:** `B-SENS-08` → the cross-service edges · `B-SENS-02` → per-service graphs with ID prefixes
  > - **Reads:** per-service graphs, prefixed (`srv:billing`)
  > - **Produces:** 🟡 a system-level graph linking services by interface only
  > - **Enables:** 🔴
  > - **Done when:** 🔴
  > - **Note:** federates `B-SENS-08`'s edges; it does not extract its own

* **`A-SENS-05` 🔜: APM Telemetry Ingestion (Sentry/Datadog)**
  > - **Purpose:** Point a production stack trace at the exact node in the graph, so a failure lands on code rather than on a log line
  > - **Trigger:** When a stack trace arrives from APM
  > - **Precondition:** `B-SENS-02` → nodes to resolve against · `TECH-068` → real edges
  > - **Reads:** production stack traces
  > - **Produces:** 🟡 trace frame → graph node resolutions
  > - **Enables:** the self-healing loop (`US-27`)
  > - **Done when:** 🔴
