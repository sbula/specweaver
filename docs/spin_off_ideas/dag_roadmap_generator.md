# Idea: Mathematical DAG Roadmap Generator

## The Problem
Traditional roadmaps (like linear Markdown checklists or Jira backlogs) fail for complex software projects because they prioritize linear time over structural dependencies. They force developers to read flat lists to figure out what to build next, obscuring "God Features" (bottlenecks) and making it difficult to propagate changing business priorities down the dependency chain.

## The Concept
A standalone project management tool that treats roadmaps as a **Directed Acyclic Graph (DAG)** rather than a checklist.

1. **The Data Layer:** Roadmaps are defined in a structured format (e.g., `roadmap.yaml`) outlining features, their dependencies (`depends_on`), and any hard business priorities/deadlines.
2. **The Calculation Engine:** A script parses the YAML and calculates:
   - **Degree Centrality (God Features):** Identifies nodes with the highest outbound edges (features that unlock the most downstream work).
   - **Inherited Priority:** Mathematically back-propagates priority. If Feature C (High Priority) depends on Feature A (Low Priority), Feature A inherits High Priority automatically.
3. **The Presentation Layer:** Generates human-readable artifacts:
   - **Visual DAG:** An auto-generated Mermaid graph (`flowchart TD`) color-coded by readiness, bottleneck status, and priority.
   - **Next Best Action Table:** A strictly filtered "Ready for Dev" list. It only displays features whose dependencies are 100% complete, sorted by their inherited priority.

## Why it's a Separate Product
Building this into a coding agent like SpecWeaver is severe scope creep. SpecWeaver's domain is reading ASTs and generating code. Project management, graph centrality calculations, and business priority tracking belong in an entirely separate tool (e.g., a CLI tool or GitHub Action) that can integrate with *any* repository, not just SpecWeaver projects.
