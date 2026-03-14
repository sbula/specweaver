# SpecWeaver Documentation

Guide to the documentation structure. Start with the [README](../README.md) for an overview of features and CLI usage.

## Architecture & Methodology

| Document | Description |
|----------|-------------|
| [Methodology Index](architecture/methodology_index.md) | **Start here** — entry point to all methodology docs |
| [Spec Methodology](architecture/spec_methodology.md) | Core framework: 5-section template, fractal decomposition |
| [Completeness Tests](architecture/completeness_tests.md) | 10-test battery (5 structure + 5 completeness) |
| [Context YAML Spec](architecture/context_yaml_spec.md) | `context.yaml` boundary manifest specification |
| [Spec Review Pipeline](architecture/spec_review_pipeline.md) | Multi-stage LLM review process |
| [Lifecycle Layers](architecture/lifecycle_layers.md) | Layer-specific implementation guides (L1–L6) |
| [Constitution Template](architecture/constitution_template.md) | Project constitution template |
| [Review Checklists](architecture/review_checklists.md) | Configurable review checklist template |

## Proposals & Roadmap

| Document | Description |
|----------|-------------|
| [Roadmap](proposals/specweaver_roadmap.md) | Step-by-step plan from current state to full product |
| [MVP Feature Definition](proposals/mvp_feature_definition.md) | MVP scope and feature breakdown |
| [MVP Implementation Plan](proposals/mvp_implementation_plan.md) | Concrete implementation plan for MVP |
| [Domain Brain / Hybrid RAG](proposals/domain_brain_hybrid_rag.md) | Future: domain knowledge + RAG integration |

## Analysis & Research

| Document | Description |
|----------|-------------|
| [Flow Synthesis](analysis/flow_synthesis.md) | Industry research: DMZ, GitHub Spec Kit, Cline, PAR |
| [Static Spec Readiness](analysis/static_spec_readiness_analysis.md) | Per-test automation feasibility analysis |
| [Fractal Readiness Walkthrough](analysis/fractal_readiness_walkthrough.md) | 10-test battery applied at all 4 fractal levels |
| [FlowManager Re-Evaluation](analysis/flowmanager_reevaluation.md) | Root cause analysis of the original FlowManager gap |
| [FlowManager Legacy Reference](analysis/flowmanager_legacy_reference.md) | Preserved patterns from the original codebase |
| [Open Research](analysis/methodology_open_research.md) | 6 remaining research questions |
| [Future Capabilities](analysis/future_capabilities_reference.md) | Reference for planned capabilities |

## Project History

See [ORIGINS.md](ORIGINS.md) for the project's evolution from FlowManager, acknowledgements, and key design influences (DMZ, CCS, PasteMax, Aider).
