# Database Migrations: Alembic Branching

In alignment with our Bounded Contexts architecture, SpecWeaver does not use a single monolithic metadata registry for SQLAlchemy. Each domain manages its own tables and state independently.

## Decentralized Metadata
How Alembic handles isolated domain metadata without a monolithic registry:

```mermaid
graph TD
    subgraph Alembic Environment
        Env(alembic/env.py)
    end

    subgraph Domain Models
        M1(infrastructure/llm/models.py<br>@declared_attr prefix)
        M2(core/flow/models.py<br>@declared_attr prefix)
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
