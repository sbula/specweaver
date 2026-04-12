# FlowManager Legacy Reference — Extracted Insights for SpecWeaver

> **Status**: REFERENCE — Excerpts from flowManager docs that are useful context, not full copies.
> **Date**: 2026-03-08
> **Source**: [github.com/sbula/flowManager](https://github.com/sbula/flowManager) (feat/status-parser branch)

---

## 1. Bad Ideas and Traps to Avoid

*Source: `docs/analysis/bad_ideas_and_traps_to_avoid.md`*

Key anti-patterns identified during flowManager development:

- **Spec bloat**: 01_08 Flows spec grew to 107KB — un-reviewable, un-implementable. **Lesson**: Max 25KB per Component Spec.
- **Premature abstractions**: Building a full workflow composition system (inheritance, mixins, templates) before a single flow had ever executed end-to-end.
- **Specs ahead of implementation**: 350KB of specs, zero working flows. **Lesson**: Every step must produce something *runnable*.
- **Over-engineering state machines**: Complex state transition logic when simple sequential execution sufficed for V1.

---

## 2. Language Strategy Decision

*Source: `docs/analysis/language_strategy_python_vs_rust.md`*

**Decision**: Python for SpecWeaver V1.

| Factor | Python | Rust |
|--------|--------|------|
| Spec/test parsing | Excellent (`ast`, `re`, `pathlib`) | Overkill for text processing |
| LLM integration | Best SDK support (Google, OpenAI) | Lagging SDK ecosystem |
| CLI tooling | Typer (modern, auto-docs) | Clap (good, but slower iteration) |
| Target audience | Python devs (primary market) | Niche |
| Development speed | Fast iteration with AI assistance | Slower, but safer |
| Future option | Rewrite hot paths to Rust later | — |

**Conclusion**: Python with strict type hints. Consider Rust for compute-heavy validation if performance becomes an issue.

---

## 3. Scenarios vs Testing Analysis

*Source: `docs/analysis/scenarios_vs_testing.md`*

Key insight relevant to SpecWeaver's Test-First test (S07):

- **Scenario-driven specs** are more implementable than **requirement-driven specs**
- A spec with `Given/When/Then` scenarios can be mechanically converted to pytest
- Weasel words ("should handle errors appropriately") survive requirements review but fail scenario review
- **Implication for SpecWeaver**: The Test-First validation rule (S07) should check for scenario-style examples, not just code blocks

---

## 4. FlowManager Re-evaluation Key Findings

*Source: `docs/analysis/flowmanager_reevaluation.md`*

Root cause analysis that led to the SpecWeaver pivot:

1. **Vision-implementation gap**: Ambitious multi-agent orchestration vision, but the engine couldn't execute a single flow
2. **Spec-first vs Build-first tension**: Writing specs without implementation feedback created specs that didn't match reality
3. **Lesson for SpecWeaver**: Start with F1 (CLI) + F3 (Spec Validation) — the simplest features that produce real value. Add LLM features (F2, F4, F5, F7) incrementally.

---

## 5. External Strategy Review — Key Decisions

*Source: `docs/proposals/external_strategy_review.md`*

Validated decisions for SpecWeaver:

- **Gemini API**: User has a subscription; use the latest available model
- **Typer for CLI**: Modern, type-hint-based, FastAPI of CLIs, 38%+ adoption in new CLI projects
- **Deployment isolation**: SpecWeaver MUST NOT live inside the target project
- **Static-first validation**: Run free structural checks before spending LLM tokens

---

## 6. Flow Synthesis — Industry Patterns

*Source: `docs/analysis/flow_synthesis.md`*

Key patterns from industry research that inform SpecWeaver design:

### DMZ Ecosystem (TheMorpheus407/the-dmz)
- 5-layer governance: `SOUL.md` → `AGENTS.md` → `MEMORY.md` → Design Docs → Issues
- Read-only reviewer agents prevent implement/review conflation
- 15-point review checklist is the gold standard for code review

### GitHub Spec Kit
- `sw check` concept validates against the spec methodology
- Spec-first workflow enforces quality before implementation

### Cline Memory Bank
- Persistent context across sessions via structured memory files
- Relevant for SpecWeaver's future context provider system

### PAR Pattern (Plan-Act-Reflect)
- Every agent session follows: read context → plan → act → reflect → persist
- Maps to SpecWeaver's draft → validate → review → implement loop

---

## 7. Documents NOT Migrated (and Why)

| Document | Reason for Exclusion |
|----------|---------------------|
| `docs/specs/01_02` through `01_11` | FlowManager-specific component specs — different system |
| `docs/architecture/engine_architecture.md` | FlowManager engine internals — not applicable |
| `docs/architecture/fractal_patterns.md` | Workflow composition for flowManager — concepts absorbed into lifecycle_layers |
| `docs/architecture/rag_architecture.md` | Post-MVP — key ideas extracted to [future_capabilities_reference.md](future_capabilities_reference.md) |
| `docs/architecture/00_system_map.md` | FlowManager-specific system map |
| `docs/analysis/agent_isolation.md` | Post-MVP — key ideas extracted to [future_capabilities_reference.md](future_capabilities_reference.md) |
| `docs/analysis/legacy_extraction.md` | FlowManager code extraction plan — not applicable |
| `docs/analysis/rag_analysis.md` | Post-MVP — key ideas extracted to [future_capabilities_reference.md](future_capabilities_reference.md) |
| `docs/analysis/fractal_readiness_walkthrough.md` | ✅ Migrated — uses FM examples but methodology is universal. See [fractal_readiness_walkthrough.md](fractal_readiness_walkthrough.md) |
| `docs/analysis/methodology_open_research.md` | ✅ Migrated — see [methodology_open_research.md](methodology_open_research.md). Key ideas also in [future_capabilities_reference.md](future_capabilities_reference.md) |
| `docs/proposals/some_conversations.md` | Raw conversation logs (175KB) — not useful as docs |
| `docs/roadmap_2026.md` | FlowManager-era roadmap, superseded by specweaver_roadmap |
| `docs/proposals/validation_gate_proposal.md` | Post-MVP — key ideas extracted to [future_capabilities_reference.md](future_capabilities_reference.md) |
| `docs/proposals/verification_gates_backlog.md` | Post-MVP — key ideas extracted to [future_capabilities_reference.md](future_capabilities_reference.md) |
| `docs/proposals/v_next_architecture_proposal.md` | Post-MVP — key ideas extracted to [future_capabilities_reference.md](future_capabilities_reference.md) |
| `docs/proposals/verifiable_agentic_orchestration.md` | Post-MVP — key ideas extracted to [future_capabilities_reference.md](future_capabilities_reference.md) |
| `docs/proposals/current_sprint.md` | FlowManager sprint plan — obsolete |
| `docs/proposals/STATUS.md` | FlowManager status — obsolete |
| `docs/proposals/external_strategy_review.md` | Key decisions extracted above (§5) |
