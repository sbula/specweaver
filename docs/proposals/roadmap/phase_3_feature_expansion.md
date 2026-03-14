# Phase 3: Feature Isolation & Incremental Expansion

> **Status**: Pending (blocked on Phase 2 completion)
> **Goal**: Take each major capability from the architecture docs, isolate it as a self-contained feature, and implement it one by one. Each feature is proposed → approved → implemented → tested → merged.

Order will be based on value and dependencies. Likely sequence:

| Priority | Feature | Source Doc | Why This Order |
|:---|:---|:---|:---|
| **3.1** | Feature Spec layer (L2 decomposition) | `lifecycle_layers.md` | Enables multi-layer workflows |
| **3.2** | Domain profiles for threshold calibration | `future_capabilities_reference.md` §19 | Quick win — just config |
| **3.3** | Custom rule paths (project-specific validators) | _(deferred from Step 8b)_ | `custom_rule_paths` table + dynamic loader; enables domain-specific rules (D01+) without core changes |
| **3.4** | Additional context providers (FileSearch, WebSearch) | `mvp_feature_definition.md` | Enhances drafting and review quality |
| **3.5** | Auto spec-mention detection _(inspired by Aider)_ | _(new)_ | Scan LLM responses for spec/file names → auto-pull into context for follow-up calls; reduces manual context management |
| **3.6** | Multi-model LLM support (dynamic routing) | `future_capabilities_reference.md` §9, §15 | Route prompts to best model per task by result/cost ratio (Gemini, Claude, Qwen, Mistral, OpenAI); interface already abstracted |
| **3.6a** | LLM cost & token tracking per task | _(new)_ | Track token counts (input/output) and compute costs per model per task type (draft/review/implement/check). Aggregate into cost reports. Enables data-driven model selection in 3.6 — find the best result/cost ratio per task. Uses existing `TokenBudget` + `LLMResponse` metadata. |
| **3.7** | Project metadata injection _(inspired by Aider)_ | _(new)_ | Inject project name, archetype, language target, date, active config into system prompt; similar to Aider's `get_platform_info()` |
| **3.8** | Spec-to-code traceability | `future_capabilities_reference.md` §17 | Bidirectional linking |
| **3.9** | Automated spec decomposition | `future_capabilities_reference.md` §18 | Agent proposes, HITL approves |
| **3.10** | Constitution enforcement | `constitution_template.md` | Project-wide constraint checking |
| **3.11** | Smart scan exclusions (tiered) | _(inspired by PasteMax)_ | 3-tier file exclusion: binary exts, default patterns (.git, __pycache__), per-project overrides + `.specweaverignore` |
| **3.12** | File watcher (`sw watch`) | _(inspired by PasteMax)_ | Auto-re-validate specs on disk change; DX polish for iterative authoring |

## Process for Each Feature

1. Write an isolation proposal (what, inputs, outputs, interfaces, scope)
2. HITL approves the proposal
3. Implement with tests
4. Dogfood on SpecWeaver itself
5. Validate
6. Merge
