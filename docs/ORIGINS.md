# SpecWeaver — Origins & Acknowledgements

## Project Origin

SpecWeaver evolved from the **FlowManager** project, a configuration-driven workflow orchestration engine for AI-assisted software development.

- **Original repository**: [github.com/sbula/flowManager](https://github.com/sbula/flowManager)
- **Evolution**: FlowManager → SpecWeaver (March 2026)
- **What changed**: FlowManager focused on JSON workflow execution. SpecWeaver refocuses on the full specification-driven development lifecycle: spec drafting, validation, review, code generation, and quality assurance.
- **What was preserved**: The methodology framework (10-test battery, fractal decomposition, lifecycle layers), architectural analysis, and design decisions were carried forward. Valuable implementation knowledge was extracted into `docs/analysis/legacy_extraction.md` before the old codebase was retired.

## Acknowledgements

### Cedric Mössner (TheMorpheus407)

Special thanks to **Cedric Mössner** ([TheMorpheus407](https://github.com/TheMorpheus407)) for sharing his work on the [DMZ ecosystem](https://github.com/TheMorpheus407/the-dmz) — a production-proven multi-agent development framework.

Key patterns adopted from DMZ into SpecWeaver's methodology:
- **SOUL.md** as a project constitution → SpecWeaver's Constitution Template
- **Read-only reviewer agents** with domain-specific checklists → SpecWeaver's Review system (F4/F7)
- **Automated issue creation from docs** (`auto-create-issues.sh`) → Influenced L2 Decomposition design
- **AGENTS.md / MEMORY.md** for agent governance → Influenced SpecWeaver's context management approach
- **15-point review checklist** → Basis for SpecWeaver's configurable review checklists

### Agentic Insights — Codebase Context Specification (CCS)

The [Codebase Context Specification](https://github.com/Agentic-Insights/codebase-context-spec) (v1.1.0-RFC) by **Agentic Insights** established a community standard for embedding AI-readable metadata in codebases using `.context` directories with structured YAML/Markdown files.

SpecWeaver's `context.yaml` boundary manifest builds on CCS's foundation:
- **Adopted**: Hierarchical context files, `module-name`/`description`/`related-modules`/`architecture` fields, tool-agnostic philosophy
- **Extended**: Added enforcement fields (`archetype`, `consumes`, `forbids`, `exposes`, `constraints`) for algorithmic pre-code and post-code validation — turning passive documentation into active boundary enforcement

See [context_yaml_spec.md](architecture/context_yaml_spec.md) for the full specification.

### Technology Decisions

| Component | Choice | Rationale |
|-----------|--------|-----------|
| **Language** | Python 3.11+ | AI integration, ecosystem, rapid iteration |
| **CLI** | Typer | Modern, type-hint-based, built on Click, "FastAPI of CLIs" |
| **LLM** | Google Gemini API | User's existing subscription, strong Python SDK |
| **Generated Code** | Python (MVP) | Same ecosystem, simplifies testing |
