# File Structure Impact: Before vs. After (TECH-01)

To make the Domain-Driven Design (DDD) refactoring concrete, here is exactly what the file structure looks like **before** and **after** TECH-01.

> [!IMPORTANT]
> **Timeline & Validity Context:** 
> - **Before (Outdated):** The "Package by Layer" architecture (Monolith) represents the system state prior to May 2026. This architecture is now **deprecated and invalid**.
> - **After (Current & Valid):** The "Package by Feature" architecture (Bounded Contexts) represents the system state from May 2026 onwards. This is the **current, valid source of truth** for all new development.

## The Problem: "Package by Layer" (BEFORE)
Currently, code that belongs to the *same feature* is scattered across 4 different root folders based on its *technical layer*. If you want to understand the "LLM" feature, you have to hunt through `infrastructure/llm`, `core/config`, and `interfaces/cli`.

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

---

## The Solution: "Package by Feature" (AFTER)
After TECH-01, everything related to a specific feature is housed in **one single folder** (the Bounded Context). The monoliths are destroyed.

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
│   ├── tools/                      ← Git tools (moved from loom/tools)
│   └── atoms/                      ← Git atoms (moved from loom/atoms)
│
└── sandbox_ast/                    ← [NEW DOMAIN] Everything AST is here!
    ├── tools/                      ← AST tools (moved from loom/tools)
    └── atoms/                      ← AST atoms (moved from loom/atoms)
```

## Why this matters (The Impact):
1. **Developer Sanity:** If you are assigned to fix a bug in the Git Sandbox, you open `src/specweaver/sandbox_git/`. You don't need to look anywhere else. The Tools, Atoms, and configurations are all colocated.
2. **Microservices:** Notice how the `llm/` folder now contains its own `cli.py` and its own database `store.py`. You could literally cut the `src/specweaver/llm` folder out of the project, drop it onto a new server, and run it as an independent microservice tomorrow.
3. **Security:** The `sandbox_git` domain is strictly isolated. A bug in the core `graph` engine cannot accidentally import a dangerous `GitTool` because it's physically segregated into a distinct domain package.
