# Lifecycle Layers — Implementation Guides

**Status**: DRAFT — first draft, requires discussion and refinement. **Date**: 2026-03-08.
**Scope**: Universal — what happens at each layer of the software development lifecycle when using
SpecWeaver.

| Related | |
|---|---|
| [Methodology Index](../04_pipelines_and_methodology/methodology_index.md) | consolidated overview |
| [Spec Methodology](../04_pipelines_and_methodology/spec_methodology.md) | the test battery that gates every layer transition |
| [DMZ Repository](https://github.com/TheMorpheus407/the-dmz) | reference implementation for L4-L5 (Code + Review) |

This draft names the battery the **10-test battery** (T1–T10). The battery has 12 spec rules today
(S01–S12); T1–T10 map to S01–S10.

## Overview

SpecWeaver spans the lifecycle from business idea to deployed software. Each layer takes input from
the layer above, applies the 10-test battery at its fractal level, and hands output to the layer
below.

```
L1: Business Engineering   → Feature Spec
L2: Architecture/Design    → Component Decomposition
L3: Specification          → Component Specs (implementable)
L4: Implementation         → Code + Tests
L5: Review/Verification    → Reviewed, validated code
L6: Integration/Deploy     → Released software
```

**Key principle**: every layer transition is gated by the 10-test battery. A Feature Spec must pass
structure + completeness tests before it flows to L2. A Component Spec must pass before it flows to
L4. Code must pass before it flows to L5.

```
L1 Business    ──Feature Spec──►  L2 Architecture  ──Decomposition──►  L3 Specification
                                                                            │
                                                                    Component Specs
                                                                            │
L6 Deploy  ◄──Released──  L5 Review  ◄──Code──  L4 Implementation  ◄────────┘
```

Each arrow is gated by the 10-test battery at the appropriate fractal level.

---

## L1: Business Engineering

> *"We need feature X"* → Feature Spec

| | |
|---|---|
| Primary actors | Product Owner (PO), Business Analyst, Customer |
| Agent role | Assistive — structures requirements, asks clarifying questions, finds ambiguities. Does NOT invent requirements. |
| HITL gate | PO approves the Feature Spec before it flows to L2 |
| Input | Customer request, user story, market need, bug report; existing project docs (SOUL.md / Constitution equivalent) |
| Output | Feature Spec (≤10KB): Intent, Blast Radius, Change Map, Integration Seams, Sequence — approved by HITL |

### Process

1. HITL describes the feature in natural language.
2. Agent structures it into Feature Spec format (Intent, Blast Radius, Change Map, Integration Seams,
   Sequence).
3. Agent runs Completeness Tests 6-10 on the draft:
   - T6: "You haven't included a concrete user scenario — what does Alice see when she uses this?"
   - T8: "Your description says 'should handle errors appropriately' — what specifically happens on
     error?"
4. HITL and agent iterate until the Feature Spec passes all completeness tests.
5. Agent runs Structure Tests 1-5 to verify the feature isn't too broad.
6. HITL approves.

### Quality gate (Feature Spec level)

- Structure Tests 1-5 at L1 thresholds (allow ≤2 conjunctions, ≤3 test setups)
- Completeness Tests 6-10 at L1 thresholds (allow ≤3 weasel words, need ≥1 user scenario)

### Open questions

- How much can an agent help with requirement discovery, without hallucinating requirements the PO
  didn't ask for?
- Feature Spec template — standardized, or flexible per project?

---

## L2: Architecture / Design

> Feature Spec → Component Decomposition

| | |
|---|---|
| Primary actors | Senior Developer / Architect |
| Agent role | Propositive — suggests decomposition by component boundaries, identifies integration seams. HITL decides. |
| HITL gate | Architect approves the decomposition before component specs are written |
| Input | Approved Feature Spec (L1); existing Component Specs (which are affected); Component Hierarchy Map (dependency direction) |
| Output | Component Spec list to create or modify; Integration Seam definitions (shared contracts); build sequence (what depends on what) |

### Process

1. Agent reads the Feature Spec and identifies affected components (Change Map section).
2. Agent proposes a decomposition: "component A gets change X, component B gets change Y".
3. For each component change, agent runs readiness tests:
   - "Is this change one responsibility?" (T1)
   - "Can it be tested in one setup?" (T2)
   - "Does it depend only downward?" (T4)
4. If any test fails, agent proposes further splitting.
5. Architect reviews and approves.

### Quality gate

- Each component change passes Structure Tests 1-5 at L2 thresholds
- The decomposition covers 100% of the Feature Spec's Change Map (no gaps)
- Integration Seams are explicitly defined (no implicit coupling)

### Reference: DMZ `auto-create-issues.sh`

The DMZ repository's `auto-create-issues.sh` ([source](https://github.com/TheMorpheus407/the-dmz))
does a version of this: an agent reads all documentation and creates GitHub issues from it. Patterns
to adopt:

- Agent reads ALL project context before proposing decomposition
- One issue (component change) at a time — not batch
- Deduplication against existing work
- Acceptance criteria checklist per issue

### Open questions

- How to handle decomposition disagreements between agent and architect?
- Can decomposition be validated automatically? (Compare the decomposition's blast radius against
  the Feature Spec's Change Map — any uncovered areas?)

---

## L3: Specification

> Component Decomposition → Implementable Component Specs

| | |
|---|---|
| Primary actors | Developer (senior developer for complex components) |
| Agent role | Co-author — agent drafts spec sections, developer reviews and refines; both iterate |
| HITL gate | Developer signs off that the spec is implementable |
| Input | Component changes from L2; existing Component Spec (if updating); 5-Section Template (Purpose / Contract / Protocol / Policy / Boundaries) |
| Output | Component Spec (≤25KB) following the 5-section template, approved by developer |

### Process

1. Agent creates or updates the Component Spec using the 5-section template.
2. Agent fills each section from the Feature Spec's requirements for this component.
3. Full 10-test battery runs on the spec:
   - Structure Tests 1-5 at L2 thresholds
   - Completeness Tests 6-10 at L2 thresholds
4. On failure, agent and developer iterate:
   - Structure failure → split or restructure
   - Completeness failure → add missing detail (examples, error paths, done definition)
5. Static analysis gate (free, instant) catches obvious problems.
6. LLM Spec Review Pipeline (PO → Architect → Junior Dev) runs on specs that pass the static gate.

### Quality gate

- All 10 tests pass at L2 (module) thresholds
- Spec is within 25KB budget
- Every public interface has ≥1 concrete example
- Every error path is defined
- Done Definition references specific, runnable tests

### Tools

- `sw check --level=component spec.md` — static test battery (levels: `feature`, `component`, `code`)
- Spec Review Pipeline ([`spec_review_pipeline.md`](../04_pipelines_and_methodology/spec_review_pipeline.md))
  — LLM semantic review

---

## L4: Implementation

> Component Spec → Code + Tests

| | |
|---|---|
| Primary actors | Developer or Implementation Agent |
| Agent role | Primary implementer — writes code from the spec; developer reviews |
| HITL gate | Code review before merge |
| Input | Approved Component Spec (L3); existing codebase |
| Output | Implementation (source files + tests), ready for review |

### Process

1. Agent reads the entire Component Spec.
2. Agent researches the existing codebase (imports, interfaces, patterns).
3. Agent implements in small, testable increments.
4. For each increment: write code → write test → run test → commit.
5. Agent runs readiness tests on the resulting code:
   - T1 (One-Sentence): does each class/function do one thing?
   - T2 (Single Test Setup): does each test file use one fixture?
   - T4 (Dependency Direction): do imports flow downward?

### Quality gate

- All tests pass
- Code coverage ≥ 70% (per user rule)
- Readiness tests at L3 (class) and L4 (function) thresholds pass
- No weasel patterns in code (TODO without issue link, bare except, etc.)

### Reference: DMZ `auto-develop.sh`

The DMZ repository ([github.com/TheMorpheus407/the-dmz](https://github.com/TheMorpheus407/the-dmz))
runs this layer in production. Its 4-phase implementation loop:

```
Research → Implement → Review A → Review B → Finalize
    │          │           │            │          │
 Read docs   Write code   Agent 1     Agent 2    Commit
 Read issues  Run tests   checks      checks     Push
 Read memory              15-point    15-point   Close issue
                          checklist   checklist
                              │
                          DENIED → loop back to Implement
```

Patterns to adopt:

1. **Research before implementing**: agent reads ALL relevant docs (SOUL.md, MEMORY.md, Design Docs)
   before writing code. Prevents hallucinated architecture.
2. **Small, testable increments**: AGENTS.md mandates "implement in small, testable increments."
3. **Tests before commit**: "Never commit without passing tests."
4. **MEMORY.md updates**: agent updates living memory after significant work, keeping project state
   across sessions.
5. **Log artifacts**: all research, implementation and review artifacts go to `logs/issues/{N}/` for
   traceability.

Patterns NOT to adopt:

- `--dangerously-skip-permissions` / `--yolo` — agents run with full dev permissions. SpecWeaver must
  keep deployment isolation.
- Infinite retry loop — DMZ's implement→review loop can cycle forever. SpecWeaver needs a
  max-iteration bound.

---

## L5: Review / Verification

> Code → Reviewed, validated code

| | |
|---|---|
| Primary actors | Reviewer Agent (read-only) + HITL final approval |
| Agent role | Adversarial critic — searches for bugs, spec violations, security issues. **Cannot edit code.** |
| HITL gate | Human approves merge after agent review |
| Input | Implementation (L4); the Component Spec it was built from; project-specific Review Checklist ([Review Checklists](../04_pipelines_and_methodology/review_checklists.md)) |
| Output | Review verdict (ACCEPTED/DENIED with findings); approved code ready for integration |

### Process

1. Reviewer agent reads the code changes.
2. Reviewer agent reads the corresponding Component Spec.
3. Reviewer agent runs the project-specific review checklist, item by item.
4. Reviewer agent runs tests (`pytest`, or project-equivalent).
5. Reviewer agent produces a structured verdict: ACCEPTED or DENIED with specific findings.
6. DENIED → back to L4 with specific, actionable feedback.
7. ACCEPTED → HITL reviews the agent's assessment, approves or requests changes.

### Quality gate

- All review checklist items pass
- All tests pass
- Code matches spec (every Contract item implemented, every Protocol followed, every Policy
  configurable)
- No new warnings or regressions

### Reference: DMZ `reviewer.md`

The DMZ repository's reviewer agent ([github.com/TheMorpheus407/the-dmz](https://github.com/TheMorpheus407/the-dmz)).
Patterns to adopt:

1. **Read-only permissions**: the reviewer cannot edit or write code — only read and run tests.
   Separates implement from review.
2. **15-point domain-specific checklist**: issue fit, correctness, security (OWASP), error handling,
   module boundaries, tests, performance, standards, etc.
3. **Binary verdict**: ACCEPTED or DENIED — no "maybe". Forces a decision.
4. **Dual review**: two reviewer agents independently, then merge. Reduces single-reviewer blind
   spots.

---

## L6: Integration / Deployment

> Reviewed code → Released software

| | |
|---|---|
| Primary actors | DevOps / CI pipeline |
| Agent role | Minimal — agents configure pipelines, don't run them in production |
| HITL gate | Deploy approval for production |
| Input | Reviewed and approved code (L5); CI/CD configuration |
| Output | Deployed software; release notes |

### Process

1. Automated CI pipeline runs on merge/PR:
   - Lint + format check
   - Type check (if applicable)
   - Unit tests + coverage threshold
   - Integration tests
   - Security scan (SAST, dependency audit)
   - Build verification
2. Staging deployment (if applicable).
3. HITL approves production deployment.

### Quality gate

- All CI jobs pass
- No security findings above threshold
- Coverage ≥ 70%
- Build succeeds

### Reference: DMZ CI pipeline

The DMZ repository's CI configuration ([github.com/TheMorpheus407/the-dmz](https://github.com/TheMorpheus407/the-dmz)):

| Gate | Mechanism | When |
|------|-----------|------|
| Secret detection | `secretlint` pre-commit hook | Every commit |
| Lint on staged files | `lint-staged` pre-commit hook | Every commit |
| Commit message format | `commitlint` commit-msg hook | Every commit |
| TypeScript strict check | `pnpm typecheck` pre-push hook | Every push |
| Full lint + typecheck | CI job 1 | Every PR |
| Unit tests with coverage | CI job 2 (Vitest) | Every PR |
| E2E tests | CI job 3 (Playwright) | Every PR |
| Production build | CI job 4 | Every PR |
| DB migration smoke test | CI job 5 | Every PR |
