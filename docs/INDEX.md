# SpecWeaver Documentation

Guide to the documentation structure. Start with the [README](../README.md) for an overview of features and CLI usage.

**Status legend**: ✅ Current | 📋 Proposal | 📜 Historical | ❓ Draft (needs discussion)

## Getting Started

| Document | Status | Description |
|----------|:------:|-------------|
| [Quick-Start Guide](quickstart.md) | ✅ | From `sw init` to a completed pipeline run in 5 minutes |
| [Developer Guide](developer_guide.html) | ✅ | Architecture overview, diagrams, onboarding (open in browser) |

## Architecture & Methodology

| Document | Status | Description |
|----------|:------:|-------------|
| [Methodology Index](architecture/methodology_index.md) | ✅ | **Start here** — entry point to all methodology docs |
| [Spec Methodology](architecture/spec_methodology.md) | ❓ | Core framework: 5-section template, fractal decomposition |
| [Completeness Tests](architecture/completeness_tests.md) | ❓ | 10-test battery (5 structure + 5 completeness) |
| [Context YAML Spec](architecture/context_yaml_spec.md) | ✅ | `context.yaml` boundary manifest specification |
| [Spec Review Pipeline](architecture/spec_review_pipeline.md) | ❓ | Multi-stage LLM review process |
| [Lifecycle Layers](architecture/lifecycle_layers.md) | ❓ | Layer-specific implementation guides (L1–L6) |
| [Constitution Template](architecture/constitution_template.md) | ❓ | Project constitution template |
| [Review Checklists](architecture/review_checklists.md) | ❓ | Configurable review checklist template |

## Proposals & Roadmap

| Document | Status | Description |
|----------|:------:|-------------|
| [Roadmap](proposals/specweaver_roadmap.md) | 📋 | Step-by-step plan from current state to full product |
| [E-UI-01: CLI Scaffold](roadmap/features/topic_01_ui_glass/E-UI-01/E-UI-01_feature_definition.md) | 📜 | Legacy Step 1 MVP |
| [E-VAL-01: Validation Engine](roadmap/features/topic_05_validation/E-VAL-01/E-VAL-01_feature_definition.md) | 📜 | Legacy Step 2 MVP |
| [E-INTL-01: LLM Adapter](roadmap/features/topic_04_intelligence/E-INTL-01/E-INTL-01_feature_definition.md) | 📜 | Legacy Step 3 MVP |
| [E-INTL-02: Spec Drafting](roadmap/features/topic_04_intelligence/E-INTL-02/E-INTL-02_feature_definition.md) | 📜 | Legacy Step 4 MVP |
| [D-INTL-01: Code Gen](roadmap/features/topic_04_intelligence/D-INTL-01/D-INTL-01_feature_definition.md) | 📜 | Legacy Step 5 MVP |
| [D-VAL-01: QA Runner](roadmap/features/topic_05_validation/D-VAL-01/D-VAL-01_feature_definition.md) | 📜 | Legacy Step 5 MVP |
| [E-SENS-01: Loom FS Tools](roadmap/features/topic_02_sensors/E-SENS-01/E-SENS-01_implementation_plan.md) | 📜 | Legacy Step 1b MVP |
| [Domain Brain / Hybrid RAG](proposals/domain_brain_hybrid_rag.md) | 📋 | Future: domain knowledge + RAG integration |

## Analysis & Research

| Document | Status | Description |
|----------|:------:|-------------|
| [Flow Synthesis](analysis/flow_synthesis.md) | 📜 | Industry research: DMZ, GitHub Spec Kit, Cline, PAR |
| [Static Spec Readiness](analysis/static_spec_readiness_analysis.md) | ❓ | Per-test automation feasibility analysis |
| [Fractal Readiness Walkthrough](analysis/fractal_readiness_walkthrough.md) | ❓ | 10-test battery applied at all 4 fractal levels |
| [FlowManager Re-Evaluation](analysis/flowmanager_reevaluation.md) | 📜 | Root cause analysis of the original FlowManager gap |
| [FlowManager Legacy Reference](analysis/flowmanager_legacy_reference.md) | 📜 | Preserved patterns from the original codebase |
| [Open Research](analysis/methodology_open_research.md) | ❓ | 6 remaining research questions |
| [Future Capabilities](analysis/future_capabilities_reference.md) | 📋 | Reference for planned capabilities |

## Project History

See [ORIGINS.md](ORIGINS.md) for the project's evolution from FlowManager, acknowledgements, and key design influences (DMZ, CCS, PasteMax, Aider).
