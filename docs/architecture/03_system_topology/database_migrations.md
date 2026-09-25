# Database Migrations: Alembic Branching

**What:** each SpecWeaver domain owns its tables and its SQLAlchemy metadata. There is no single monolithic
metadata registry.

**Why:** follows the Bounded Contexts architecture — a domain changes its schema without touching
another domain's models.

## Decentralized Metadata

The design: `alembic/env.py` collects each domain's metadata and generates one independent migration
branch per domain.

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

## As built (checked 2026-09-25)

- Metadata is decentralized: `env.py` sets `target_metadata` to three `Base.metadata` objects —
  `infrastructure/llm/store.py`, `workspace/store.py`, `core/flow/store.py` — and imports
  `workspace/memory/store.py`. Models live in `store.py`, not `models.py`.
- Migrations are **not** branched: one linear timeline in `alembic/versions/` (3 revisions, no
  `branch_labels`, no `llm/` or `flow/` sub-folders).
