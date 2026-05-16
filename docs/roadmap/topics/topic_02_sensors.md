# Topic 02: Context & Sensors (Perception)

This document tracks all capabilities related to the AST, knowledge graphs, and workspace understanding.

## DAL-E: Prototyping
* **`E-SENS-01` ✅: Loom FS Tools** (Legacy: Step 1b)<br>
  > _(new)_ | Agents and Engine have secure, role-gated filesystem access. Agents see only whitelisted boundaries.
* **`E-SENS-02` ✅: Agentic Research Tools** (Legacy: 3.10)<br>
  > `_(new)_` | LLM function-calling via provider-agnostic abstraction. 6 tools (4 filesystem + 2 web) in `sandbox/research/`. `WorkspaceBoundary` enforcement, `ToolExecutor`, `generate_with_tools()` on adapter. Wired into Reviewer + Planner. **Complete**: boundaries, executor, tool definitions, adapter integration, 3353 tests. See [implementation plan](features/topic_02_sensors/E-SENS-02/E-SENS-02_implementation_plan.md).
* **`E-SENS-03` 🔜: Context Ledgers & Workspace Boundaries**
  > _(new)_ | Security boundaries restricting agent filesystem visibility exclusively to the scope of their assigned task.

## DAL-D: Internal Tooling
* **`D-SENS-01` ✅: Topology Graph** (Legacy: Step 7)<br>
  > _(new)_ | In-memory dependency graph from `context.yaml` files. Foundation for impact analysis and context-enriched prompts. Language-agnostic code analysis framework for auto-generating missing `context.yaml`.
* **`D-SENS-02` ✅: Polyglot AST Extractor** (Legacy: 3.22)<br>
  > _(new)_ | _Pivoted from Context Ledger (304 Caching) to prevent LLM memory hallucination._ Provides read_skeleton, read_symbol, and AST mutation capabilities via Tree-Sitter. Target expansion to 25 languages mapping native graph relationships. **Complete**: SF-01 (Read) and SF-02 (Write) across 5 languages fully completed and bound to Engine with 90%+ coverage.
* **`D-SENS-03` ✅: Polyglot Expansion (C++, Go)** (Legacy: 3.32e)<br>
  > _(new)_ | Targeted expansion of Tree-sitter grammars focusing strictly on high-value enterprise domains: **Markdown** (mandatory for Spec.md traceability bounds), **C/C++** (Systems/Legacy), **Go** (Cloud-Native infrastructure), and **Standard SQL** (baseline ANSI schemas to empower the DB Context Harness), avoiding dialect nightmare traps. **Complete:** Markdown, C/C++, Go, and SQL parsers are completed with Dot-Notation and capability filtering.
* **`D-SENS-04` 🔜: Parallel AST Extraction Engine**
  > _(new)_ | Leverages Rust's Rayon library via PyO3 to parse and extract Tree-Sitter ASTs across millions of lines of code concurrently.
* **`D-SENS-05` 🔜: Markdown AST Mutators**
  > _(new)_ | High-assurance AST mutators specifically for injecting and extracting structured data from Spec.md documents.

## DAL-C: Enterprise Standard
* **`C-SENS-01` ✅: Spec-Mention Detection** (Legacy: 3.11)<br>
  > _(new)_ | Scan LLM responses for spec/file names → auto-pull into context for follow-up calls. Pure-logic `llm/mention_scanner/` module + resolver with workspace boundary enforcement. Follow-up injection wired through `Reviewer.mentioned_files` param. **Complete**: scanner, resolver, PromptBuilder integration, follow-up injection, 3353 tests. See [implementation plan](features/topic_02_sensors/C-SENS-01/C-SENS-01_implementation_plan.md).
* **`C-SENS-02` ✅: Smart Scan Exclusions** (Legacy: 3.32b)<br>
  > _(inspired by PasteMax)_ | 3-tier file exclusion: binary exts, default patterns (.git, __pycache__), per-project overrides + `.specweaverignore`. **Complete:** SF-01, SF-02, SF-03 (Polyglot Hashing), SF-04 (Analyzer DI), and SF-05 (DI Remediation).
* **`C-SENS-03` 🔜: Symbol Index Gates** (Legacy: 4.1)<br>
  > `future_capabilities_reference.md` §11 | Symbol index + anti-hallucination gate
* **`C-SENS-04` 🔜: Infrastructure-as-Code Extraction (HCL2)**<br>
  > _(new)_ | Expansion of the Tree-Sitter Polyglot engine to specifically parse HashiCorp Configuration Language (Terraform/OpenTofu). Allows the agent to understand infrastructure topology, map cloud resource dependencies, and validate IAC spec drift.
* **`C-SENS-05` 🔮: Embedded SQL Extraction**<br>
  > _(new)_ | Extracts embedded SQL strings from host languages (e.g., Python, Java) and parses them using the SQL Tree-Sitter grammar to map cross-domain dependencies between code and database schemas. Deferred from B-SENS-02 to prevent scope creep.
* **`C-SENS-06` 🔮: Event-Sourced 4D Graph**<br>
  > _(new)_ | Upgrades the SQLite Knowledge Graph to be event-sourced (valid_from/valid_to tracking). Allows semantic `git bisect` and point-in-time architectural queries without executing git checkouts.
* **`C-SENS-07` 🔜: Polyglot Expansion (TypeSpec)**<br>
  > _(new)_ | Targeted expansion of Tree-sitter grammars to parse TypeSpec (https://typespec.io/), using the community parser (https://github.com/happenslol/tree-sitter-typespec). This is crucial for securely mapping cross-platform API contracts and enabling deterministic semantic truth engines.

## DAL-B: High-Assurance
* **`B-SENS-01` ✅: Artifact Lineage Graph** (Legacy: 3.17)<br>
  > `future_capabilities_reference.md` §17 | Core database-backed lineage tracking and #sw-artifact tagging. Enables exact LLM provenance attribution and cost-per-feature analysis while remaining orthogonal to AST dependencies. **Complete**: 3591 tests.
* **`B-SENS-02` ✅: Knowledge Graph Builder** (Legacy: 3.32f)<br>
  > _(new)_ | Constructs a deep class/function-level semantic Knowledge Graph from the AST. Persists the nodes and edges directly to specweaver.db (SQLite) to ensure cross-session persistence (no rebuilding from scratch on boot). Wraps local query operations in NetworkX purely for fast in-memory execution over the persistent SQL data. **-> NOTE: Once implemented, use the graph to extract active workspace languages and dynamically inject them into CodeStructureAtom to perfectly prune unsupported tool schemas.**
* **`B-SENS-03` 🔜: AST Semantic Chunking** (Legacy: 4.2)<br>
  > `future_capabilities_reference.md` §3 | AST-based semantic chunking (RAG foundation). _(See also: [CrewAI Knowledge](https://docs.crewai.com/concepts/knowledge) for RAG source patterns, embedder config, query rewriting — ORIGINS.md § CrewAI)_
* **`B-SENS-04` 🔮: Static Control Flow Graph (CFG)**<br>
  > _(extracted from B-SENS-02)_ | Maps execution branches (True/False edges). Restricted strictly to statically typed languages (Java, C++) to avoid dynamic scoping tar pits.
* **`B-SENS-05` 🔮: Static Dataflow Solver**<br>
  > _(extracted from B-SENS-02)_ | Computes Def-Use chains using Kildall's framework. Highly experimental. Restricted to statically typed languages.
* **`B-SENS-06` 🔜: OSV Vulnerability Feed Ingestion**
  > _(new)_ | Automatically maps known CVEs from the OSV database against the active workspace topology graph.

## DAL-A: Mission-Critical
* **`A-SENS-01` ✅: Deep Semantic Hashing** (Legacy: 3.32)<br>
  > _(new)_ | Replaces shallow file hashing with "Dependency Hashing" (hash changes if imported modules change). Uses Merkle-trees to keep the Topology Graph explicitly in sync without full project crawls. **Complete:** SF-01, SF-02, SF-03, and SF-04 (Incremental Pipeline Bypassing).
* **`A-SENS-02` 🔜: Postgres pgvector Sidecar** (Legacy: 3.33 / 5.1)<br>
  > _(new)_ | Toggle between local SQLite/BM25 (Bicycle mode) and a unified **PostgreSQL (Apache AGE + pgvector)** sidecar (Rocket mode) to map cross-service GraphRAG topologies and vectors in a single transactional backend. Phase D.1 → D.2
* **`A-SENS-03` 🔜: Event-Driven Knowledge Graph** (Legacy: 5.2)<br>
  > Phase D | Event-driven knowledge graph (EDKG) — file/commit triggers update nodes/edges
* **`A-SENS-04` 🔮: Federated Microservice System Graph**<br>
  > _(new)_ | A high-level system architecture graph that links all microservices together *exclusively* via their external interfaces (REST APIs, Kafka, RabbitMQ, shared file systems). It strictly obscures internal microservice logic, creating a pure Enterprise-level GraphRAG layer. Relies on strict ID prefixes (e.g., `srv:billing`) generated by local B-SENS-02 engines to dynamically fuse API contracts without context bloat.
* **`A-SENS-05` 🔜: APM Telemetry Ingestion (Sentry/Datadog)**
  > _(new)_ | Feeds production stack traces directly into the Knowledge Graph to pinpoint failing AST nodes.
