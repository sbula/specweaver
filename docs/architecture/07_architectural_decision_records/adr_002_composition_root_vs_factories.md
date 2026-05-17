# ADR 002: Composition Root vs. Domain Factories for Context Hydration

**Status:** Accepted
**Date:** May 16, 2026
**Context:** TECH-05 Refactoring of Context Loading Pipeline

## Context and Problem Statement

The `RunContext` God Object within `core/flow/handlers/base.py` required refactoring. During the `sw review` and `sw draft` CLI lifecycles, the Delivery Mechanism (`interfaces/cli.py` and `interfaces/api/`) was performing heavy lifting: fetching the `CONSTITUTION.md` from the Workspace domain and compiling rules from the Standards domain, before bundling them into the `RunContext`.

This appeared to violate DRY principles ("Spider Web" cross-interface imports) and felt like a leaky abstraction where the CLI was doing Domain-level orchestration. 

We needed to decide where System Invariants (Constitution, Standards) should be loaded:
1. **At the Entry Point (CLI/API)**: As a pure Composition Root.
2. **Inside the Flow Engine (`core/flow`)**: Using Factory Injection.
3. **Inside an Atom/Tool**: Using the `sandbox` execution engine.

## Considered Options

### Option 1: The Context Hydrator (Factory Injection)
Move the hydration logic directly into the Engine (`core/flow/handlers/base._build_base_prompt`).
* **Pros:** DRY code. The CLI becomes incredibly thin, passing only file paths.
* **Cons (Fatal):** Violates **Dependency Inversion**. The generic `Pipeline Engine` (a universal CD player) becomes permanently hard-coded to expect SpecWeaver-specific domain concepts (the Constitution CD). It couples the `flow` module downwards to the `workspace` and `standards` modules, ruining its pure-logic generic orchestration nature.

### Option 2: The Atom/Tool Fetcher
Use the `FileSystemAtom` inside the Engine to fetch the files dynamically during execution.
* **Pros:** Leverages existing sandbox architecture.
* **Cons (Fatal):** 
  1. **Event Loop Blocking**: The Atom executes blocking File I/O mid-pipeline.
  2. **Invariant Drift (Loss of Snapshot Isolation)**: If a user edits `CONSTITUTION.md` while the pipeline is running Step 2, Step 3 will load the *new* rules. The LLM changes behavior mid-run, breaking determinism and causing infinite loopbacks. System Invariants must be loaded *before* the engine starts.

### Option 3: The Entry Point as Composition Root (Chosen)
Keep the hydration logic at the highest edge of the system: the Delivery Mechanism (`interfaces/cli.py` and `interfaces/api/`).

* **Pros:** Preserves perfect **Dependency Inversion**. The Engine receives a pre-hydrated `RunContext` box and remains completely ignorant of where the rules came from. System Invariants are frozen *before* the Engine starts, guaranteeing Snapshot Isolation.
* **Cons:** Appears to be a DRY violation because both the CLI and the REST API must duplicate the fetching logic. The CLI feels "too fat" for a Typer router.

## Decision Outcome

**We chose Option 3.**

In Hexagonal Architecture, the outermost layer (the Delivery Mechanism) is legally required to act as the **Composition Root**. It is the only layer permitted to have "direct access to the sources" (Filesystem, DB) without polluting the generic core domains. 

The Engine must remain a universal orchestrator. We will not weld the specific "SpecWeaver Rules" into the universal "CD Player."

### Mitigation of the "Fat CLI" Anti-Pattern
To resolve the DRY violation without breaking the Composition Root pattern, we will execute **TECH-05**:
1. We will NOT move the hydration into the Engine.
2. Instead, we will replace the 20-line private helper functions (`_load_constitution_content`, `_load_standards_content`) in the CLI with clean, 1-line public Domain APIs (`find_constitution` and `load_standards_content_async`).
3. This slims the CLI down to a pure declarative injector, maintaining Dependency Inversion while resolving the code smell.

## Future Adaptations (TECH-08 — CANCELLED)
This section originally proposed extracting an explicit `ApplicationService` layer (TECH-08). After two rounds of adversarial Red Team / Blue Team analysis, this was proven to be an empty indirection wrapper with zero ROI. The constraints required (no typer, no db, no file I/O, no if/else, must be async) stripped it down to a single-line delegation to `PipelineRunner`. The real fix is TECH-05: expose the misplaced private CLI helpers as public Domain APIs.
