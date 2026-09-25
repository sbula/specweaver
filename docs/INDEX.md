# SpecWeaver Documentation

Use when: you need to find a document. For an overview of features and CLI usage, start with the
[README](../README.md).

**Status legend**: ✅ Current | 📋 Proposal | 📜 Historical | ❓ Draft (needs discussion)

## Getting Started

| Document | Status | Description |
|----------|:------:|-------------|
| [What the project is](../.agents/PROJECT.md) | ✅ | **Start here if you are an agent** — scope, layout, testing, expected documentation |
| [How we work](../.agents/PRINCIPLES.md) | ✅ | The non-negotiables, and why each one exists |
| [Where the project is](../.agents/STATE.md) | ✅ | Delivered, set back, missing. Updated at commit boundaries |
| [Installation & Setup](user_guides/1_installation_and_setup.md) | ✅ | Install from source, credentials, `sw init` |
| [Developer Guide](dev_guides/developer_guide.html) | ✅ | Architecture overview, diagrams, onboarding (open in browser) |
| [Working in This Repo](dev_guides/working_in_this_repo.md) | ✅ | **Read before your first change** — the operational traps that have cost sessions |
| [The Development Framework](dev_guides/development_framework.md) | ✅ | **What checks you, and when** — the four gate runners, the ratchet pattern, where the rules live |

## User Guides

| Document | Description |
|----------|-------------|
| [1 Installation & Setup](user_guides/1_installation_and_setup.md) | Install from source, credentials, `sw init` |
| [2 Drafting Effective Specs](user_guides/2_drafting_effective_specs.md) | Spec structure, `sw draft`, `sw check` |
| [3 Managing Constitutions](user_guides/3_managing_constitutions.md) | Constitutions and coding standards |
| [4 Interactive HITL Gates](user_guides/4_interactive_hitl_gates.md) | HITL gates, dictator overrides, resuming |
| [5 Framework Archetypes](user_guides/5_framework_archetypes.md) | Archetypes, plugins, tool hiding, contract drift |
| [6 AST Surgical Editing](user_guides/6_ast_surgical_editing.md) | Symbol-level reads and edits |
| [7 Model Context Protocol](user_guides/7_model_context_protocol.md) | Pre-fetching MCP resources |
| [8 Prompt Render Profiles](user_guides/8_prompt_render_profiles.md) | Choosing what context a step sends |

## Architecture & Methodology

Hub: [architecture/README.md](architecture/README.md).

| Document | Status | Description |
|----------|:------:|-------------|
| [Methodology Index](architecture/04_pipelines_and_methodology/methodology_index.md) | ✅ | **Start here** — entry point to all methodology docs |
| [Spec Methodology](architecture/04_pipelines_and_methodology/spec_methodology.md) | ❓ | Core framework: 5-section template, fractal decomposition |
| [Completeness Tests](architecture/04_pipelines_and_methodology/completeness_tests.md) | ❓ | 10-test battery (5 structure + 5 completeness) |
| [Context YAML Spec](architecture/03_system_topology/context_yaml_spec.md) | ✅ | `context.yaml` boundary manifest specification |
| [Spec Review Pipeline](architecture/04_pipelines_and_methodology/spec_review_pipeline.md) | ❓ | Multi-stage LLM review process |
| [Lifecycle Layers](architecture/01_foundational_principles/lifecycle_layers.md) | ❓ | Layer-specific implementation guides (L1–L6) |
| [Constitution Template](architecture/04_pipelines_and_methodology/constitution_template.md) | ❓ | Project constitution template |
| [Review Checklists](architecture/04_pipelines_and_methodology/review_checklists.md) | ❓ | Configurable review checklist template |

## Roadmap

| Document | Status | Description |
|----------|:------:|-------------|
| [Master Story Roadmap](roadmap/master_story_roadmap.md) | 📋 | User stories from current state to full product |
| [E-UI-01: CLI Scaffold](roadmap/features/topic_01_ui_glass/E-UI-01/E-UI-01_design.md) | 📜 | Legacy Step 1 MVP |
| [E-VAL-01: Validation Engine](roadmap/features/topic_05_validation/E-VAL-01/E-VAL-01_design.md) | 📜 | Legacy Step 2 MVP |
| [E-INTL-01: LLM Adapter](roadmap/features/topic_04_intelligence/E-INTL-01/E-INTL-01_design.md) | 📜 | Legacy Step 3 MVP |
| [E-INTL-02: Spec Drafting](roadmap/features/topic_04_intelligence/E-INTL-02/E-INTL-02_design.md) | 📜 | Legacy Step 4 MVP |
| [D-INTL-01: Code Gen](roadmap/features/topic_04_intelligence/D-INTL-01/D-INTL-01_design.md) | 📜 | Legacy Step 5 MVP |
| [D-VAL-01: QA Runner](roadmap/features/topic_05_validation/D-VAL-01/D-VAL-01_design.md) | 📜 | Legacy Step 5 MVP |
| [E-SENS-01: Loom FS Tools](roadmap/features/topic_02_sensors/E-SENS-01/E-SENS-01_implementation_plan.md) | 📜 | Legacy Step 1b MVP |
| [Domain Brain / Hybrid RAG](analysis/domain_brain_hybrid_rag.md) | 📋 | Future: domain knowledge + RAG integration |

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

[ORIGINS.md](ORIGINS.md): evolution from FlowManager, acknowledgements, and design influences (DMZ,
CCS, PasteMax, Aider).
