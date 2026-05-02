# Technical Story: TECH-03

- **Feature ID**: TECH-03
- **Phase**: Backlog
- **Status**: PENDING
- **Topic**: Technical Debt / Architecture

## Title
Architectural Analysis & Refactoring of `sw graph build` CLI

## The Case / Problem Statement

Currently, the Knowledge Graph ingestion process is exposed as a standalone CLI command (`sw graph build`). Inside `src/specweaver/interfaces/cli/graph.py`, the CLI acts as the orchestrator, manually wiring together the `GraphBuilder`, `InMemoryGraphEngine`, `TopologyGraph`, and `SqliteGraphRepository`.

This creates several architectural violations and open questions:
1. **Leaky Abstraction**: SpecWeaver is an autonomous agentic framework built on Atoms and Tools. The human developer should ideally not need to manually manage the internal structural memory (Knowledge Graph) of the AI via a CLI.
2. **Duplicated Orchestration**: If a future autonomous workflow needs to rebuild the graph, the orchestration logic is currently trapped inside the CLI layer, making it inaccessible to headless `Atoms` without code duplication.
3. **Usecase Ambiguity**: We have not thoroughly analyzed if a dedicated CLI is genuinely required. While a CLI is useful for CI/CD pipelines and manual debugging/overrides, standard developer operations (like initializing a new project) could arguably be better served by a generic `spinUp` or `sw init` workflow that triggers graph ingestion silently in the background.

## Action Items

1. **Analyze the Use Cases**: Determine whether the CI/CD and Manual Debugging use cases justify maintaining a dedicated CLI command, or if it should be completely deprecated in favor of autonomous workflows.
2. **Refactor the Orchestrator**: If the CLI is kept (e.g., as an admin command), strip all business/orchestration logic out of `cli/graph.py`. Move the graph initialization logic into a unified `GraphBuildAtom` inside `src/specweaver/core/loom/atoms/graph/`.
3. **Interface Adherence**: Ensure the CLI acts *strictly* as a thin I/O facade that simply invokes the `GraphBuildAtom` with the appropriate context arguments.
