# Future Architecture Adaptations (Phase 3 Extensions)

**Status**: DRAFT (Captured Ideas) · **Scope**: 6 proposed features for late Phase 3, for greenfield
microservices (FinTech) and brownfield monoliths — plus 3 rejected ones, kept so nobody re-proposes
them.

## Greenfield / polyglot targets

### 1. Protocol & Schema Analyzers

- **Problem**: in a 20-microservice cluster talking gRPC and Kafka, source code alone is not
  enough. The most common bug is **Contract Drift**.
- **Solution**: extend the parser (`LanguageAnalyzer`) to read `.proto` and `openapi.yaml` files.
  When a producer's contract changes, flag downstream clients as "Out of Spec".

### 2. Archetype-Based Rule Sets

- **Problem**: writing `CONSTITUTION.md` rules by hand for 20 distinct services (Rust, Kotlin,
  Python) slows bootstrapping.
- **Solution**: use pipeline inheritance to build core Archetypes (`quarkus-service`,
  `rust-worker`). A project with `archetype: rust-worker` gets memory-safety and crate-version
  checks without writing rules.

### 3. Topology Provider Abstraction: "Bicycle vs Rocket"

- **Problem**: requiring a graph database (FalkorDB/Neo4j) on every install is heavy friction.
- **Solution**: an `AbstractKnowledgeProvider` pattern.
  - **Bicycle Mode (Default)**: local `SQLite` and `BM25` only. Fast, container-friendly, no
    external infra.
  - **Rocket Mode (Upgrade)**: `sw bootstrap --upgrade` starts sidecars (Docker Compose) for a
    Vector DB and FalkorDB, for "Global Impact Analysis" across a large topology.

### 4. Symbolic Math Validation Gates

- **Problem**: general LLMs fail or hallucinate on complex mathematical logic (FinBERT, trading
  algos).
- **Solution**: a `MathVerification` validation gate. It extracts formulas from the `Spec.md` and
  checks the generated financial implementation with a symbolic math checker (or targeted
  mathematical LLM chains).

## Brownfield / legacy targets

### 5. Reverse-Weaving via `sw capture`

- **Problem**: "Spec-First" cannot be enforced on 1500 man-years of undocumented legacy Java. The
  code is the unwritten spec.
- **Solution**: an "Archaeology Tool". `sw capture <file>` does AST **Skeleton Extraction** (method
  signatures, types, Javadocs; bodies stripped to save LLM context). The LLM drafts a baseline
  `Spec.md` from the skeleton, so spec-driven work can start without writing one by hand.

### 6. Pluggable External Context Providers

- **Problem**: a legacy system is governed by external truths (e.g. a 900-table database that
  generates Java code, or Control-M batch jobs). Teaching SpecWeaver to parse Control-M XMLs or SQL
  schemas is fatal scope creep.
- **Solution**: let the `context/providers.py` layer run arbitrary terminal scripts.
  - A custom script such as `dump_legacy_ddl.py` runs during the pipeline, instead of SpecWeaver
    talking to the DB.
  - SpecWeaver pipes its `stdout` (the formatted schema) into the Prompt Builder.
  - SpecWeaver stays free of legacy parsers and still sees the environment.

## Rejected — do not implement

Evaluated after the Phase 3 functionality review; rejected for risk or architectural violations.

### 7. Universal Dispute Resolution (Arbiter for Git Conflicts)

- **Investigated**: using the multi-pipeline Arbiter agent to resolve git merge conflicts.
- **Rejected because**: a merge conflict is a human semantic collision. An LLM gate strips human
  intent and can silently drop valid business logic without failing compilation. Needs human HITL
  validation, always.

### 8. Speculative Auto-Refactoring

- **Investigated**: headless bots that pick complex modules, QA them repeatedly, and open PRs with
  improvements in the background.
- **Rejected because**: headless cycles mutate shared state caches (the `TopologyGraph` and
  `context.db`) unpredictably and cause lock failures for foreground users. Refactor loops that keep
  failing against the Arbiter burn the context-token budget fast.

### 9. Dynamic Ephemeral Mocking

- **Investigated**: passing remote OpenAPI schemas into the `QARunner` and spawning
  Mountebank/Docker containers that mimic the contract for unverified integration testing.
- **Rejected because**: sandbox escalation. Booting arbitrary containers from untrusted schemas
  opens agentic Remote Code Execution (RCE) vectors. Network isolation (`--network none`) cannot
  fully stop payload logic escaping the git worktree sandbox.
