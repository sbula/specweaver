# Phase 6: External Validation & Benchmarking

> **Status**: Pending
> **Goal**: SpecWeaver is subjected to mathematical quantitative observation against standardized test suites, and deployed on real external projects.

> [!TIP]
> **Reference**: [Spec Kit](https://github.com/github/spec-kit)'s workflow (Specify → Plan → Tasks → Implement) is a useful model for structuring the external validation runs. See [ORIGINS.md](../../ORIGINS.md) § Spec Kit for blueprint references.

| Priority | Feature |
|:---|:---|
| **6.1** | **Standardized Benchmarking CI (`sw benchmark`)** — Adapt an internal pipeline designed specifically to ingest public `SWE-bench` tickets, generate code, and produce normalized dashboard validation of Attributed Lifecycle Scores regression. |
| **6.2** | **External Proprietary Validation** — Execute `sw init`, `draft`, and `check` workflows externally outside SpecWeaver's boundary (e.g., orchestrating an external 20-microservice proprietary trading system). |

- [ ] Run the full workflow manually on the Target external project.
- [ ] Record benchmark outputs against native DEV datasets.
- [ ] **Milestone**: SpecWeaver is **useful and algorithmically proven** on real-world projects.
