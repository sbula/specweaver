# SpecWeaver — Origins & Acknowledgements

## Project Origin

SpecWeaver evolved from the **FlowManager** project, a configuration-driven workflow orchestration engine for AI-assisted software development.

- **Original repository**: [github.com/sbula/flowManager](https://github.com/sbula/flowManager)
- **Evolution**: FlowManager → SpecWeaver (March 2026)
- **What changed**: FlowManager focused on JSON workflow execution. SpecWeaver refocuses on the full specification-driven development lifecycle: spec drafting, validation, review, code generation, and quality assurance.
- **What was preserved**: The methodology framework (10-test battery, fractal decomposition, lifecycle layers), architectural analysis, and design decisions were carried forward. Valuable implementation knowledge was extracted into [flowmanager_legacy_reference.md](analysis/flowmanager_legacy_reference.md) before the old codebase was retired.

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

### PasteMax — Token Budgeting & Prompt Formatting

[PasteMax](https://github.com/kleneway/pastemax) by **kleneway** is an open-source desktop tool for selecting repository files and preparing them as LLM context, with per-file token counting and model context limit awareness.

Ideas adopted into SpecWeaver's roadmap (Step 9, Phase 3):
- **Token budget awareness** (Step 9a) — estimating tokens before LLM calls using `tiktoken` with `len(text) // 4` fallback; warning when approaching model context limits
- **Structured prompt formatting** (Step 9b) — XML-tagged prompt assembly (`<file_map>`, `<file_contents>`, `<user_instructions>`) with per-file language detection; `PromptBuilder` pattern
- **Tiered file exclusion** (Phase 3.9) — 3-tier system: binary extensions, default patterns (`.git`, `__pycache__`), per-project overrides + `.specweaverignore`
- **File watcher** (Phase 3.10) — auto-re-validate specs on disk change

### Aider — AI Pair Programming Architecture

[Aider](https://github.com/Aider-AI/aider) by **Paul Gauthier** is the leading open-source AI pair programming tool. Analyzed in March 2026 for prompt engineering, context management, and resilience patterns.

Patterns adopted or planned for SpecWeaver:
- **RepoMap with PageRank ranking** → Adaptation for spec topology context selection (9c): rank which specs are most relevant to the current context using dependency graph analysis, similar to Aider's symbol-based file ranking
- **Tiered context with trust signals** → PromptBuilder's `<file>` tags will include trust/role annotations (e.g., "reference-only" vs. "target for review"), inspired by Aider's `files_content_prefix` patterns
- **System reminder at end** → `.add_reminder()` method to re-state critical output format rules at the bottom of prompts, mitigating "lost in the middle" attention decay
- **Dynamic budget scaling** → When context is light, allocate more token budget to topology/context; when many files present, compress context — inspired by Aider's `map_mul_no_files` multiplier
- **Lint-fix reflection loop** → Step 12 (audit/quality gates): after code generation, run linter/tests → feed errors back to LLM for auto-fix → re-validate, with `max_reflections` cap. Directly from Aider's `reflected_message` + linter integration
- **Context overflow recovery** → Graceful handling when prompt exceeds model context window — auto-truncate and retry rather than failing. Inspired by Aider's `ContextWindowExceededError` handling
- **Auto spec-mention detection** → Scan LLM responses for spec/file names mentioned, auto-pull into context for follow-up calls. Inspired by Aider's `check_for_file_mentions()` (Phase 3.5)
- **Project metadata injection** → Inject project name, archetype, language target, date into system prompts. Inspired by Aider's `get_platform_info()` (Phase 3.7)
- **Conversation summarization** → Compress old multi-turn messages when context fills up, keeping recent turns + summary. Inspired by Aider's `summarize_end()` (Phase 4.6)

For current technology choices, see the [Tech Stack](../README.md#tech-stack) section in the README.

### agent-system — Independent Verification & Wave Parallelism

[agent-system](https://github.com/joshuarubin/agent-system) is an open-source multi-agent coding framework that enforces strict role separation: Coordinator (plans), Implementor (writes code), and Verifier (checks work with evidence).

Patterns adopted for SpecWeaver:
- **"The agent that writes code never verifies it"** → Core principle of SpecWeaver's scenario testing architecture (Phase 3.13). The coding agent and scenario agent are information-isolated — neither can see the other's output.
- **Evidence-based verification** → Scenario tests produce concrete pass/fail evidence (not LLM opinions). Verdicts are based on test output, not self-assessment. (Phase 3.13)
- **Wave-based parallelism** → Coordinator splits work into non-overlapping waves; implementors work in parallel per wave. Adopted as the model for parallel pipeline execution with JOIN gates. (Phase 3.13)

### NVIDIA HEPH & BDD Renaissance — Spec-Traceable Scenario Testing

NVIDIA's HEPH framework automates test generation from documentation and interface specs using LLM agents at every step from document traceability to test correctness verification.

The BDD renaissance (2024–2026) — AI eliminates the traditional "glue code" problem that made BDD impractical. Given/When/Then is now the ideal format for both LLM scenario generation and mechanical test conversion.

Patterns adopted for SpecWeaver:
- **Requirement traceability** → Every generated scenario test links back to a specific spec clause via `spec_clause` field. (Phase 3.13)
- **Structured YAML over Gherkin** → LLMs produce and consume structured YAML scenarios more reliably than natural-language Gherkin. Human-readable rendering for review only. (Phase 3.13)
- **Contract-first scenarios** → API contracts (Python Protocols) generated from specs before coding or scenario generation begins. (Phase 3.13)
- **Eval-driven development** (Anthropic) → Build evaluations (scenarios) _before_ the agent is complete. Scenario pipeline runs parallel to, not after, coding. (Phase 3.13)

### agentwise — Agent Claim Verification

[agentwise](https://github.com/agentwise) provides multi-agent orchestration with an Agent Claim Verification System — evidence-based verification of agent claims.

Patterns adopted for SpecWeaver:
- **Arbiter Agent pattern** → When scenario tests fail, a third agent determines fault attribution (code bug vs. scenario error vs. spec ambiguity) using evidence, producing filtered feedback to each pipeline without cross-contamination. (Phase 3.13)

