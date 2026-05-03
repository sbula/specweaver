# SpecWeaver DDD Architecture (TECH-01)

This document visualizes the complete architectural overhaul defined in `TECH-01`. It maps out the boundaries, the modules, and the commonly used resources to restore the big picture after the Red/Blue Team sparring.

> [!IMPORTANT]
> **Timeline & Validity Context:** 
> - **Effective Date:** May 2026
> - **Status:** This document represents the **current, valid architecture**. All legacy patterns (global config pools, monolithic CLI routing) are now **deprecated and invalid**. Any new development MUST adhere to the bounded contexts defined below.

## 1. System Overview: The New Bounded Contexts

The system transitions from "Package by Layer" (Monoliths) to "Package by Feature" (Bounded Contexts).

```mermaid
graph TD
    %% Core Infrastructure (Shared Resources)
    subgraph Core_Infrastructure [Core Infrastructure / Shared]
        A[interfaces/cli/main.py<br>The Rescue Core]
        B[core/config/database.py<br>CQRS Queue & session_scope]
        C[(specweaver.db<br>SQLite WAL)]
        D[BaseTool Meta-Class<br>Auto-Registry]
    end

    %% Bounded Contexts (Microservice-Ready Domains)
    subgraph Domain_Graph [Domain: Knowledge Graph]
        G_CLI(graph/cli.py)
        G_API(graph/api.py)
        G_Core(graph/engine.py)
    end

    subgraph Domain_LLM [Domain: LLM & Telemetry]
        L_CLI(llm/cli.py)
        L_Store(llm/store.py<br>Models & Repo)
        L_Core(llm/adapter.py)
    end

    subgraph Domain_Flow [Domain: Flow Orchestration]
        F_CLI(flow/cli.py)
        F_Store(flow/store.py<br>Models & Repo)
        F_Engine(flow/runner.py)
    end

    subgraph Sandbox_Git [Sandbox Domain: Git]
        S_Tools(sandbox_git/tools/)
        S_Atoms(sandbox_git/atoms/)
        S_Exec(sandbox_git/executor.py)
    end

    %% Relationships
    A -.->|Dynamically Loads| G_CLI
    A -.->|Dynamically Loads| L_CLI
    A -.->|Dynamically Loads| F_CLI
    
    B ===|Write Queue & DI| L_Store
    B ===|Write Queue & DI| F_Store
    
    L_Store -.->|Commits to| C
    F_Store -.->|Commits to| C
    
    D -.->|Auto-Registers| S_Tools
```

## 2. The Unassailable Defenses Visualized

Here is how the 4 major defenses from the Red/Blue Team battle actually map to the physical architecture.

### Defense A: Native Healer & Rescue Core
If a plugin crashes, the CLI still boots so the agent can heal it.

```mermaid
graph LR
    User([Developer / Agent]) --> CLI[interfaces/cli/main.py]
    
    CLI -->|Hardcoded Boot| Core[Rescue Core Commands<br>sw run / sw implement]
    CLI -->|Hardcoded Boot| FST[FileSystemTool<br>ALWAYS ONLINE]
    
    CLI -.->|Try/Except Load| Plug1[llm/cli.py]
    CLI -.->|Try/Except Load| Plug2[sandbox_git/cli.py<br>💥 SyntaxError]
    
    Core -.->|Uses FST to fix| Plug2
```

### Defense B: CQRS & SQLite WAL (Database Concurrency)
How we safely write to SQLite from heavily concurrent tasks without locking.

```mermaid
sequenceDiagram
    participant T1 as Task 1 (Atom)
    participant T2 as Task 2 (Atom)
    participant SQ as core/config/database<br>Async Write Queue
    participant DB as specweaver.db (WAL)

    T1->>DB: Read Query (session_scope)
    T2->>DB: Read Query (session_scope)
    Note over T1,DB: Unlimited parallel reads (WAL Mode)
    
    T1->>SQ: Emit WriteCommand(Telemetry)
    T2->>SQ: Emit WriteCommand(FlowState)
    Note over SQ,DB: Single Write Worker processes queue sequentially
    
    SQ->>DB: Execute Write (Telemetry)
    SQ->>DB: Execute Write (FlowState)
```

### Defense C: Alembic Branching (Microservice Readiness)
How Alembic handles isolated domain metadata without a monolithic registry.

```mermaid
graph TD
    subgraph Alembic Environment
        Env(alembic/env.py)
    end

    subgraph Domain Models
        M1(llm/models.py<br>@declared_attr prefix)
        M2(flow/models.py<br>@declared_attr prefix)
    end

    subgraph Migration Timelines
        V1[alembic/versions/llm/]
        V2[alembic/versions/flow/]
    end

    M1 -->|Target Metadata| Env
    M2 -->|Target Metadata| Env

    Env -->|Generates independent branch| V1
    Env -->|Generates independent branch| V2
```

## 3. The Rules of the New Borders

To maintain this architecture, developers must follow three strict border rules enforced by `tach` (context.yaml):

1. **The Monolith Rule**: Domains (e.g., `llm/`, `graph/`) must NEVER import from each other. They can only communicate via the shared `core/` infrastructure or formal REST APIs/Event Buses.
2. **The Lazy Rule**: Domain `cli.py` files must NEVER import heavy logic at the top level. Imports must be inside the `def command():` block.
3. **The BaseTool Rule**: Sandbox domains MUST inherit from `BaseTool`. They do not need to register themselves anywhere; the Meta-class handles it automatically.
