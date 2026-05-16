# CQRS & SQLite WAL (Database Concurrency)

This document visualizes how we safely write to SQLite from heavily concurrent tasks without locking, using our internal CQRS (Command Query Responsibility Segregation) engine.

## The Async Write Queue
Because SpecWeaver agents operate in parallel and emit high-volume telemetry and state changes, we avoid `database is locked` deadlocks by isolating all write operations to a single worker queue, while allowing infinite concurrent reads via WAL.

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
