# SpecWeaver Architecture Hub

> **Consult this documentation before planning, writing specs, or implementing anything in the SpecWeaver codebase.**

This is the central hub for the SpecWeaver Domain-Driven Design (DDD) architecture.

## System Overview

SpecWeaver is a specification-driven development lifecycle tool. It enforces spec quality through a 12-test battery and manages AI agents via role-restricted tool interfaces.

```text
specweaver/                       ← level: system, archetype: orchestrator
├── cli/                          ← Typer CLI (`sw` command)
├── api/                          ← FastAPI REST server
├── config/                       ← Pydantic settings + SQLite DB
├── context/                      ← HITL context providers
├── drafting/                     ← LLM-assisted spec drafting
├── flow/                         ← Pipeline engine (models, runners, gates, handlers)
├── graph/                        ← In-Memory Knowledge Graph Engine, Builder, & Topology
├── implementation/               ← Code generation from specs
├── llm/                          ← LLM provider abstraction
│   ├── adapters/                 ← Concrete adapters (Gemini)
│   ├── mention_scanner/          ← Auto-detect spec/file mentions in LLM output
│   ├── collector.py              ← TelemetryCollector decorator (3.12)
│   ├── telemetry.py              ← Cost estimation + UsageRecord (3.12)
│   └── factory.py                ← Adapter creation with optional telemetry wrapping
├── sandbox/                         ← Execution engine (tools, atoms, commons)
│   ├── tools/                    ← Agent-facing capability providers
│   │   ├── filesystem/           ← FileSystemTool + role interfaces
│   │   ├── git/                  ← GitTool + role interfaces
│   │   ├── qa_runner/            ← QARunnerTool + role interfaces
│   │   ├── code_structure/       ← CodeStructureTool (Polyglot AST Extraction)
│   │   └── web/                  ← WebTool + role interfaces
│   ├── atoms/                    ← Engine-internal workflow ops
│   │   ├── filesystem/
│   │   ├── git/
│   │   ├── mcp/
│   │   ├── qa_runner/
│   │   └── code_structure/
│   └── commons/                  ← Shared executors + helpers
│       ├── filesystem/           ← FileExecutor, search helpers
│       ├── git/                  ← GitExecutor
│       ├── language/             ← Polyglot AST Extractor (tree-sitter bindings)
│       ├── mcp/                  ← MCP JSON-RPC Stdio Bridge
│       ├── protocol/             ← Protocol & Schema Parsers (native OpenAPI/proto)
│       └── qa_runner/            ← QARunnerExecutor
├── pipelines/                    ← YAML pipeline definitions (data only)
├── planning/                     ← Implementation plan generation
├── project/                      ← Project discovery + scaffolding
├── review/                       ← LLM-based spec/code review
├── standards/                    ← Codebase standards auto-discovery
└── validation/                   ← 12-test spec quality battery
    └── rules/                    ← Rule implementations (spec + code)
```
