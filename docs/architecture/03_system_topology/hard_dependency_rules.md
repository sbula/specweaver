# Hard Dependency Rules

## Top-Level Modules

| Module | Archetype | Consumes | Forbids |
|--------|-----------|----------|---------|
| `cli` | orchestrator | config, validation, review, drafting, implementation, flow, graph, llm, project, standards, context | sandbox/* |
| `api` | adapter | config, validation, review, implementation, flow, graph, llm, project, standards | cli, sandbox/* |
| `config` | pure-logic | *(leaf)* | sandbox/* |
| `context` | contract | *(leaf)* | sandbox/* |
| `drafting` | orchestrator | llm, config, context | sandbox/* |
| `flow` | orchestrator | config, llm, review, implementation, planning, validation, sandbox/git, sandbox/qa_runner, sandbox/code_structure, sandbox/mcp, sandbox/execution, sandbox/dispatcher, sandbox/security, workspace/memory | sandbox/* (except git/qa_runner/code_structure/mcp/execution/dispatcher/security), drafting, context |
| `graph` | pure-logic | context | sandbox/*, llm, drafting, implementation |
| `implementation` | orchestrator | llm, config, validation | *(none)* |
| `llm` | adapter | config | sandbox/* |
| `llm/adapters` | adapter | llm | sandbox/*, validation, drafting |
| `pipelines` | data | *(leaf)* | *(none)* |
| `planning` | orchestrator | llm, config, context, sandbox/dispatcher (type-only) | sandbox/* (except dispatcher) |
| `project` | adapter | config | sandbox/*, llm |
| `review` | orchestrator | llm, config, sandbox/dispatcher (type-only) | sandbox/* (except dispatcher) |
| `standards` | orchestrator | config | sandbox/* |
| `validation` | pure-logic | config | sandbox/*, llm |

> [!CAUTION]
> **12 of 16 modules explicitly `forbid: sandbox/*`.** Only `flow/` is allowed to
> touch sandbox (via atoms only, NOT tools or commons). The sandbox layer is isolated.

## Loom Sub-Layers

| Layer | Consumes | Forbids |
|-------|----------|---------|
| `commons/` | *(leaf — nothing)* | `tools/*`, `atoms/*` |
| `tools/` | `commons/*` | `atoms/*` |
| `atoms/` | `commons/*` | `tools/*` |
| `sandbox/` (root) | `tools/*`, `atoms/*`, `commons/*` | — |

> [!CAUTION]
> **Dependency flows UPWARD only within sandbox.** Commons NEVER imports from
> tools or atoms. Tools NEVER import from atoms (and vice versa).
> Only `sandbox/` root level can import across sub-layers.
