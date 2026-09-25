# SpecWeaver Methodology — Consolidated Index

**Status**: DRAFT, 2026-03-08 — all linked documents are drafts that need discussion. Start here:
single entry point to the methodology documents.

## The Problem

SpecWeaver's original specs (~350KB across 10 files) failed because they had no organizing
principle. They grew into monoliths mixing data definitions, runtime behavior, policies and future
ideas. Worst case: the 01_08 flows spec (107KB) — 7 concerns in one document, un-reviewable and
un-implementable.

The answer is one methodology for writing, sizing and validating specs, at every level of software
architecture and in any project domain.

## Documents

### Framework (how to think)

| Document | Type | What It Defines |
|----------|------|----------------|
| [Spec Methodology](../04_pipelines_and_methodology/spec_methodology.md) | Architecture | The core framework: two-level spec model (Feature Spec → Component Spec), 5-section template (Purpose/Contract/Protocol/Policy/Boundaries), 5 structure tests, fractal levels, size budgets, concern routing rules |
| [Completeness Tests](../04_pipelines_and_methodology/completeness_tests.md) | Architecture | The second axis: 5 completeness tests (Concrete Example, Test-First, Ambiguity, Error Path, Done Definition), two-axis model (structure × completeness), fractal comparison, static analysis sketches |
| [Lifecycle Layers](../01_foundational_principles/lifecycle_layers.md) | Architecture | **DRAFT** — Layer-specific implementation guides (L1 Business → L6 Deploy). DMZ patterns adopted for L4-L5. |
| [Constitution Template](../04_pipelines_and_methodology/constitution_template.md) | Architecture | **DRAFT** — Universal template for project constitutions. References DMZ's SOUL.md. |
| [Review Checklists](../04_pipelines_and_methodology/review_checklists.md) | Architecture | **DRAFT** — Project-specific review checklist template. Maps DMZ's 15-point checklist to universal categories. |

### Analysis (proof it works)

| Document | Type | What It Proves |
|----------|------|---------------|
| [Static Spec Readiness Analysis](../../analysis/static_spec_readiness_analysis.md) | Analysis | Per-test static automation feasibility. Tests 2 and 4 are ~85-90% automatable with zero LLM tokens. Gate model: static bouncer → LLM judge. ~80% token savings. |
| [Fractal Readiness Walkthrough](../../analysis/fractal_readiness_walkthrough.md) | Analysis | All 5 structure tests applied at all 4 levels (L1 Feature, L2 Module, L3 Class, L4 Function) on real SpecWeaver examples, with pass/fail reasoning. |
| [Open Research Items](../../analysis/methodology_open_research.md) | Analysis | **DRAFT** — First pass on 6 remaining research questions: automated decomposition, threshold calibration, too-small problem, traceability, over-specification, cross-domain calibration. |

### Context (earlier, still relevant)

| Document | Type | Relevance |
|----------|------|-----------|
| [FlowManager Re-Evaluation](../../analysis/flowmanager_reevaluation.md) | Analysis | Identified the vision-implementation gap and spec bloat. Root cause analysis for the methodology work. |
| [Flow Synthesis](../../analysis/flow_synthesis.md) | Analysis | Industry research: DMZ ecosystem, GitHub Spec Kit, Cline Memory Bank, PAR pattern. Contains the DMZ 5-layer analysis. |
| [Spec Review Pipeline](spec_review_pipeline.md) | Architecture | Multi-stage LLM review (PO → Architect → Junior Dev). The LLM layer that runs AFTER the static tests pass. |

Current plan: [master story roadmap](../../roadmap/master_story_roadmap.md). It replaced the old
step-by-step SpecWeaver Roadmap (Steps 1-12, formerly proposals/specweaver_roadmap.md), which no longer exists.

## The Big Picture

```
                          A spec is ready when BOTH axes pass
                          
                              TOO VAGUE
                             (no examples,
                              weasel words,
                              no error paths)
                                  ▲
                                  │
                     Completeness Tests 6-10
                                  │
  TOO BIG ◄── Structure Tests 1-5 ┼ ──────────► RIGHT SIZE
  (monolith,                      │              (focused,
   tangled,                       │               decoupled,
   coupled)                       │               one-day scope)
                                  │
                     Completeness Tests 6-10
                                  │
                                  ▼
                            IMPLEMENTABLE
                           (concrete examples,
                            testable, unambiguous,
                            failure defined)
```

### The 10-Test Battery (Universal, Fractal)

| # | Test | Axis | Universal Question | Static? |
|---|------|------|--------------------|---------|
| 1 | One-Sentence | Structure | Is it one responsibility? | ~70% |
| 2 | Single Test Setup | Structure | Is it cohesive? | ~85% |
| 3 | Stranger | Structure | Is it self-contained? | ~60% |
| 4 | Dependency Direction | Structure | Is it decoupled? | ~90% |
| 5 | Day Test | Structure | Is it right-sized? | ~65% |
| 6 | Concrete Example | Completeness | Does it show real I/O? | ~75% |
| 7 | Test-First | Completeness | Can you write a test? | ~50% |
| 8 | Ambiguity | Completeness | Are all decisions made? | ~95% |
| 9 | Error Path | Completeness | Is failure defined? | ~70% |
| 10 | Done Definition | Completeness | Is completion verifiable? | ~80% |

The tests apply at **every fractal level** (Feature → Module → Class → Function); thresholds tighten
as you go deeper. **A spec is ready to implement only when all pass.**

**As built (2026-09-25):** the code runs 12 spec rules, `S01`–`S12` in
`src/specweaver/assurance/validation/rules/spec/`. Added beyond this battery: `S11` Terminology
Consistency (inconsistent casing, undefined PascalCase terms; ~70% static) and `S12` Archetype Spec
Bounds (required headers per archetype skeleton).

### Lifecycle Integration

```
Author writes spec
      │
      ▼
Static Tests 1-10 (free, instant)  ← catches ~80% of problems
      │
  ┌───┼───┐
  │   │   │
PASS BORDER FAIL
  │   │     │
  │   │     └→ Author fixes before proceeding
  │   │
  │   └→ LLM judges borderline cases (minimal tokens)
  │
  ▼
LLM Spec Review Pipeline (2-3 stages)  ← semantic quality review
      │
      ▼
Feature Spec → Component Specs (decomposition)
      │
      ▼
Implementation (can borrow DMZ patterns here)
```

## Decided

1. **Two-level spec model**: Feature Spec (what goes where) → Component Spec (how it works)
2. **5-section template**: Purpose / Contract / Protocol / Policy / Boundaries
3. **10-test battery**: 5 structure + 5 completeness, applied fractally
4. **Static-first gate**: cheap checks before the LLM. ~80% token savings.
5. **Fractal application**: same tests at L1 (Feature) through L4 (Function)
6. **Structure and completeness are orthogonal**: fixing one doesn't fix the other

## Still Open

All 9 items have first drafts, marked DRAFT, needing discussion.

| # | Item | First Draft Location | Status |
|---|------|---------------------|--------|
| 1 | Layer-specific implementation guides (L1-L6) | [lifecycle_layers.md](../01_foundational_principles/lifecycle_layers.md) | DRAFT — needs discussion, especially L1-L3 |
| 2 | Constitution layer | [constitution_template.md](../04_pipelines_and_methodology/constitution_template.md) | DRAFT — template ready, needs SpecWeaver-specific instance |
| 3 | Automated decomposition | [methodology_open_research.md §1](../../analysis/methodology_open_research.md) | DRAFT — hypothesis + DMZ pattern documented |
| 4 | Project-specific review checklists | [review_checklists.md](../04_pipelines_and_methodology/review_checklists.md) | DRAFT — template + DMZ mapping done |
| 5 | Threshold calibration | [methodology_open_research.md §2](../../analysis/methodology_open_research.md) | DRAFT — calibration plan defined, execution pending |
| 6 | The "too small" problem | [methodology_open_research.md §3](../../analysis/methodology_open_research.md) | DRAFT — lower bound signals proposed |
| 7 | Spec-to-code traceability | [methodology_open_research.md §4](../../analysis/methodology_open_research.md) | DRAFT — bidirectional linking approach proposed |
| 8 | Completeness vs over-specification | [methodology_open_research.md §5](../../analysis/methodology_open_research.md) | DRAFT — what/how boundary rule proposed |
| 9 | Cross-domain calibration | [methodology_open_research.md §6](../../analysis/methodology_open_research.md) | DRAFT — domain profiles approach proposed |

## External References

- **DMZ Repository**: [github.com/TheMorpheus407/the-dmz](https://github.com/TheMorpheus407/the-dmz)
  — production reference for L4-L5 patterns (auto-develop.sh, reviewer.md, SOUL.md, AGENTS.md,
  MEMORY.md). Analyzed in [flow_synthesis.md](../../analysis/flow_synthesis.md) §2.1.
