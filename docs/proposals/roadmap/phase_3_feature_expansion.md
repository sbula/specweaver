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
| **3.13** | **Scenario Testing — Independent Verification** | _(inspired by agent-system, NVIDIA HEPH, BDD renaissance)_ | Dual-pipeline architecture: coding + scenario pipelines run in parallel, meet at JOIN gate. Contract-first (Python Protocols), structured YAML scenarios, arbiter agent for error attribution. See [proposal](scenario_testing_proposal.md) and [ORIGINS.md](../../ORIGINS.md). |

## Process for Each Feature

1. Write an isolation proposal (what, inputs, outputs, interfaces, scope)
2. HITL approves the proposal
3. Implement with tests
4. Dogfood on SpecWeaver itself
5. Validate
6. Merge

---

## 3.13 Scenario Testing — Implementation Steps

> **Depends on**: Phase 2 Steps 11–12 (flow engine runner + gates), Phase 3.8 (spec-to-code traceability).
> **Full proposal**: [scenario_testing_proposal.md](scenario_testing_proposal.md)

| Sub-step | Component | Description |
|:---------|:----------|:------------|
| **3.13a** | Spec template enforcement | Require `## Scenarios` section in specs with structured inputs (preconditions, inputs, expected outputs) in YAML code blocks. Enhance S07 to validate. |
| **3.13b** | API contract generation | New handler: `generate+contract` — extract Python Protocol/ABC from spec Contract section. Output: `api_contract.py`. |
| **3.13c** | Scenario generation atom | New atom: spec + API contract → structured YAML scenarios (LLM). Multiple scenarios per public method: happy path, error paths, boundary, state transitions. |
| **3.13d** | Scenario → pytest conversion | New atom: structured YAML scenarios → executable parametrized pytest files. Mechanical conversion, no LLM needed. |
| **3.13e** | `scenario_agent` role | New role in loom/tools: sees `specs/` + `scenarios/` only. `FileSystemTool` path allowlist per role. |
| **3.13f** | `scenario_validation.yaml` | New pipeline definition: generate_contract → generate_scenarios → convert_to_pytest → signal READY. |
| **3.13g** | JOIN gate type | New `GateType.JOIN` in `models.py` — waits for two pipelines to both signal READY before proceeding. |
| **3.13h** | Pipeline orchestrator | Runs coding + scenario pipelines in parallel. Synchronizes at JOIN gate. |
| **3.13i** | Arbiter agent | Third agent with full read access. On scenario test failure: determines fault (code/scenario/spec), produces filtered feedback to each pipeline. |
| **3.13j** | Feedback loop & retry | Coding agent gets stack traces + spec references. Scenario agent gets expected vs actual + spec references. Neither sees other's code. Loop back if fixable, HITL escalation if spec ambiguity. |

