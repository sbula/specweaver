# File Structure Impact: Before vs. After (TECH-001)

TECH-001 moved the source tree from **package by layer** to **package by feature** (DDD bounded
contexts).

> [!IMPORTANT]
> - **Before (Outdated):** "Package by Layer" (Monolith) — the system prior to May 2026.
>   **Deprecated and invalid.**
> - **After (Current & Valid):** "Package by Feature" (Bounded Contexts) — the system from May 2026
>   onwards. The **source of truth** for all new development.

## Before: package by layer

Code for one feature was spread over 4 root folders by *technical layer*. To understand the "LLM"
feature you had to search `infrastructure/llm`, `core/config`, and `interfaces/cli`.

```text
src/specweaver/
├── core/
│   ├── config/                     ← [MONOLITH] All databases tangled here
│   │   ├── _db_llm_mixin.py        ← (LLM data)
│   │   ├── _db_telemetry_mixin.py  ← (Telemetry data)
│   │   └── database.py             
│   └── loom/                       ← [MONOLITH] All sandboxes tangled here
│       ├── atoms/
│       │   ├── code_structure/     ← (AST feature)
│       │   └── git/                ← (Git feature)
│       └── tools/
│           ├── code_structure/     ← (AST feature)
│           └── git/                ← (Git feature)
├── infrastructure/
│   └── llm/                        ← (LLM logic)
│       └── adapter.py
└── interfaces/
    └── cli/                        ← [MONOLITH] All CLI commands tangled here
        ├── config.py
        ├── main.py
        ├── lineage.py              ← (Graph feature)
        ├── review.py               ← (Review feature)
        └── usage_commands.py       ← (LLM feature)
```

## After: package by feature

Everything for one feature lives in **one folder** (the bounded context). The monoliths are gone.

```text
src/specweaver/
├── core/
│   └── config/
│       └── database.py             ← [RESCUE] Only handles the CQRS Queue now.
│
├── interfaces/
│   └── cli/
│       └── main.py                 ← [RESCUE] Only handles the Rescue Core routing.
│
├── llm/                            ← [NEW DOMAIN] Everything LLM is here!
│   ├── adapter.py                  ← Logic
│   ├── cli.py                      ← CLI command (moved from interfaces/cli)
│   └── store.py                    ← Database models (moved from core/config)
│
├── graph/                          ← [NEW DOMAIN] Everything Graph is here!
│   ├── engine.py                   ← Logic
│   └── cli.py                      ← CLI command (moved from interfaces/cli)
│
├── sandbox_git/                    ← [NEW DOMAIN] Everything Git is here!
│   ├── tools/                      ← Git tools (moved from sandbox)
│   └── atoms/                      ← Git atoms (moved from sandbox)
│
└── sandbox_ast/                    ← [NEW DOMAIN] Everything AST is here!
    ├── tools/                      ← AST tools (moved from sandbox)
    └── atoms/                      ← AST atoms (moved from sandbox)
```

**Since moved (checked 2026-09-25):** the tree above is the TECH-001 shape, not today's paths. LLM
lives in `src/specweaver/infrastructure/llm/` (with its own `store.py` and `interfaces/`), Git in
`src/specweaver/sandbox/git/` (`core/`, `interfaces/`), the graph CLI in
`src/specweaver/graph/interfaces/cli.py`. Current map:
[module_dependency_graph.md](../03_system_topology/module_dependency_graph.md).

## Why

1. **One place to look.** A bug in the Git sandbox means opening `src/specweaver/sandbox_git/`
   and nothing else. Tools, atoms and configuration sit together.
2. **Separable domains.** `llm/` holds its own `cli.py` and its own database `store.py`. The
   `src/specweaver/llm` folder could be cut out and run as an independent service.
3. **Isolation.** The `sandbox_git` domain is a separate package. The core `graph` engine cannot
   accidentally import a dangerous `GitTool`.
