# Topic 07: Technical Debt & Architecture (TECH)

This document tracks all massive refactoring efforts, technical debt removal, and underlying architectural epics required to ensure the platform remains stable, secure, and mathematically sound as it scales to enterprise levels. These stories do not add new user-facing features but are critical for long-term project viability.

## Domain-Driven Design (DDD)
* **`TECH-01` 🔜: Domain-Driven Design Unification**
  > [Description](../features/topic_07_technical_debt/TECH-01/TECH-01_ddd_refactor.md) | SpecWeaver's internal architecture is perfectly cohesive and microservice-ready, preventing "Dumping Ground" anti-patterns and circular dependencies as the team scales. The massive refactoring effort to align the legacy `config/`, `cli/`, and `loom/` layers with the pure Domain-Driven Design (Package by Feature) principles established by the B-SENS-02 Graph Triad.

## Architecture & Restructuring
* **`TECH-02` 🔴: Structural Refactoring of Workspace AST Module**
  > [Description](../features/topic_07_technical_debt/TECH-02/TECH-02_ast_restructuring.md) | To make the bounded context crystal clear, we want to introduce a dedicated `ast` boundary inside the workspace module. This separates mechanical Tree-Sitter extraction (`parsers`) from output mapping (`adapters`).
* **`TECH-03` 🔴: Architectural Analysis & Refactoring of `sw graph build` CLI**
  > [Description](../features/topic_07_technical_debt/TECH-03/TECH-03_graph_cli_analysis.md) | Analyzing whether a standalone CLI command for graph building is an architectural violation (leaky abstraction/duplicated orchestration). Proposes either migrating the orchestration logic into a centralized `GraphBuildAtom` or deprecating the CLI entirely in favor of an autonomous `spinUp` workflow.
