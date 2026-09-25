# SpecWeaver Architecture Hub

> **Consult this documentation before planning, writing specs, or implementing anything in the SpecWeaver codebase.**

Use when: you need the structure of SpecWeaver's Domain-Driven Design (DDD) architecture, or the
doc that explains one part of it.

## System overview

SpecWeaver is a specification-driven development lifecycle tool. It enforces spec quality through
a 12-test battery and runs AI agents behind role-restricted tool interfaces.

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

**Since moved (2026-09-25):** the tree above predates the domain restructure. The top-level
packages of `src/specweaver/` are now `assurance/`, `commons/`, `core/`, `graph/`,
`infrastructure/`, `interfaces/`, `sandbox/`, `workflows/`, `workspace/`. Module boundaries:
[Context YAML Spec](03_system_topology/context_yaml_spec.md).

## Where the detail lives

| Folder | Holds |
|---|---|
| `01_foundational_principles/` | Lifecycle layers, security guardrails, atoms vs tools, CQRS and database, archetypes |
| `02_bounded_contexts/` | Flow engine, LLM and telemetry, legacy feature map |
| `03_system_topology/` | `context.yaml` spec, dependency rules and graph, migrations, topology evolution |
| `04_pipelines_and_methodology/` | Spec methodology, completeness tests, review pipeline, templates |
| `05_delivery_mechanisms/` | CLI and MCP delivery |
| `06_lessons_and_future/` | Anti-patterns, known boundary violations, future adaptations |
| `07_architectural_decision_records/` | ADRs |
