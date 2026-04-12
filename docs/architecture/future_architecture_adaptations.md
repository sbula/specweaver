# Future Architecture Adaptations (Phase 3 Extensions)

> **Status**: DRAFT (Captured Ideas)
> **Goal**: Preserve the detailed context and technical reasoning for 6 new features proposed for the later stages of Phase 3, targeting both greenfield microservices (FinTech) and legacy brownfield (monoliths).

## Greenfield / Polyglot Targets

### 1. Protocol & Schema Analyzers
- **Problem**: In a 20-microservice cluster communicating via gRPC and Kafka, checking source code alone is insufficient. The most common bug is **Contract Drift**.
- **Solution**: Extend the parser (`LanguageAnalyzer`) to read `.proto` and `openapi.yaml` files. SpecWeaver must use these interface definitions to immediately flag downstream clients as "Out of Spec" if the producer's contract changes.

### 2. Archetype-Based Rule Sets
- **Problem**: Writing `CONSTITUTION.md` rules manually for 20 distinct services (Rust, Kotlin, Python) slows down bootstrapping.
- **Solution**: Use pipeline inheritance to create core Archetypes (`quarkus-service`, `rust-worker`). If a project uses `archetype: rust-worker`, SpecWeaver inherently validates memory safety and crate versions without manual rule definition.

### 3. Topology Provider Abstraction: "Bicycle vs Rocket"
- **Problem**: Forcing heavy graph databases (FalkorDB/Neo4j) on every SpecWeaver instance creates massive friction. 
- **Solution**: Implement an `AbstractKnowledgeProvider` pattern.
  - **Bicycle Mode (Default)**: Uses purely local `SQLite` and `BM25`. Fast, container-friendly, zero external infra.
  - **Rocket Mode (Upgrade)**: A `sw bootstrap --upgrade` command that spins up sidecars (Docker Compose) for a Vector DB and FalkorDB, allowing deep "Global Impact Analysis" across a huge topology.

### 4. Symbolic Math Validation Gates
- **Problem**: General LLMs fail or hallucinate when performing complex mathematical logic (FinBERT, trading algos).
- **Solution**: Implement a dedicated `MathVerification` validation gate. It extracts formulas from the `Spec.md` and uses an automated symbolic math checker (or highly targeted mathematical LLM chains) to brutally verify the correctness of the generated financial implementation.

## Brownfield / Legacy Targets

### 5. Reverse-Weaving via `sw capture`
- **Problem**: Enforcing "Spec-First" on 1500 man-years of undocumented legacy Java is impossible. The code is the unwritten spec.
- **Solution**: Build an "Archaeology Tool". Executing `sw capture <file>` performs an AST **Skeleton Extraction** (method signatures, types, Javadocs—stripping the body to preserve LLM context). The LLM processes the skeleton to draft a new baseline `Spec.md`, enabling immediate Spec-Driven development without manual writing.

### 6. Pluggable External Context Providers
- **Problem**: A legacy system is governed by external truths (e.g., a 900-table database generating Java code, or Control-M batch jobs). Teaching SpecWeaver to natively parse Control-M XMLs or SQL schemas is fatal scope creep.
- **Solution**: Expand the `context/providers.py` layer to accept arbitrary terminal scripts. 
  - Instead of SpecWeaver talking to the DB natively, a custom script `dump_legacy_ddl.py` is invoked during the pipeline. 
  - SpecWeaver pipes the `stdout` (the formatted schema) into the Prompt Builder. 
  - SpecWeaver remains pure but benefits from complete environmental truth.
