# Project-Specific Review Checklists

**Status**: DRAFT, 2026-03-08. **Scope**: universal pattern — each project builds its own
checklist from this guide.

| | |
|---|---|
| Used in | [Lifecycle Layers — L5 Review](../01_foundational_principles/lifecycle_layers.md) |
| Extends | [Completeness Tests — T10 Done Definition](../04_pipelines_and_methodology/completeness_tests.md) |
| Reference | [DMZ Repository — reviewer.md](https://github.com/TheMorpheus407/the-dmz) (15-point checklist) |

## Purpose

The 10-test battery ([Spec Methodology](../04_pipelines_and_methodology/spec_methodology.md)) is
**universal**. Every project also has **domain-specific** quality concerns it doesn't cover.

A Review Checklist is a **project-specific extension** of Test 10 (Done Definition): "is completion
verifiable?" becomes "does this code meet OUR project's quality bar?"

## Anatomy of a Review Checklist

### Structure

A numbered list of review items. Each item has:

| Field | Purpose | Example |
|-------|---------|---------|
| **Category** | Groups related items | "Security", "Testing", "Standards" |
| **Check** | What to verify (specific, binary — yes/no) | "All user input is validated with a schema before processing" |
| **How** | How to verify it (concrete action) | "Search for request handlers without schema validation" |
| **Severity** | What happens if this check fails | BLOCK (cannot merge) or WARN (note for author) |

### Required vs. Optional Items

- **BLOCK items**: Code CANNOT be merged if these fail. These are non-negotiable.
- **WARN items**: Code CAN be merged, but the finding is reported to the HITL for awareness.

## Template

```markdown
# [Project Name] — Review Checklist

> **Applies to**: All code changes reviewed by agent or human.
> **Verdict**: ACCEPTED (all BLOCK items pass) or DENIED (any BLOCK item fails).

## 1. Spec Compliance
- [ ] **[BLOCK]** Every public function/class maps to a requirement in the Component Spec
- [ ] **[BLOCK]** No functionality exists that isn't described in the spec (no gold-plating)
- [ ] **[WARN]** Spec was updated if implementation deviated from original design

## 2. Correctness
- [ ] **[BLOCK]** Happy path works as specified
- [ ] **[BLOCK]** All error paths from the spec are implemented
- [ ] **[WARN]** Edge cases beyond spec are handled or explicitly noted as out-of-scope

## 3. Testing
- [ ] **[BLOCK]** Tests exist for every public method
- [ ] **[BLOCK]** Tests pass (`pytest` / project equivalent)
- [ ] **[BLOCK]** Coverage ≥ [project threshold]%
- [ ] **[WARN]** Error path tests exist (not just happy path)

## 4. Security
- [ ] **[BLOCK]** No secrets in code (API keys, passwords, tokens)
- [ ] **[BLOCK]** All user/agent input validated before use
- [ ] **[BLOCK]** File operations use safe path validation
- [ ] **[WARN]** OWASP Top 10 considerations relevant to this change

## 5. Standards
- [ ] **[BLOCK]** Code follows project coding standards (naming, imports, error handling)
- [ ] **[BLOCK]** Type hints present on all public interfaces
- [ ] **[WARN]** Docstrings on public classes and functions
- [ ] **[WARN]** No TODO/FIXME without an issue reference

## 6. Architecture
- [ ] **[BLOCK]** No imports from peer or upper-level modules (dependency direction)
- [ ] **[BLOCK]** No violation of Constitution principles
- [ ] **[WARN]** Module boundaries respected (no reaching into another module's internals)

## 7. [Domain-Specific Category]
- [ ] **[BLOCK/WARN]** [Project-specific checks go here]
```

## Reference: DMZ's 15-Point Checklist

The DMZ repository ([github.com/TheMorpheus407/the-dmz](https://github.com/TheMorpheus407/the-dmz))
has a 15-point reviewer checklist in `reviewer.md` — the most complete working example found:

| # | DMZ Check | Universal Category | Our Equivalent |
|---|-----------|-------------------|---------------|
| 1 | Issue fit | Spec Compliance | §1 — maps to spec |
| 2 | Correctness | Correctness | §2 — happy + error paths |
| 3 | Security (OWASP) | Security | §4 — OWASP, secrets, input validation |
| 4 | Error handling | Correctness | §2 — error path coverage |
| 5 | Tenant isolation | Domain-Specific | §7 — project-specific (multi-tenancy) |
| 6 | Event sourcing | Domain-Specific | §7 — project-specific (CQRS/ES) |
| 7 | TypeScript & Svelte | Standards | §5 — coding standards |
| 8 | Module boundaries | Architecture | §6 — dependency direction |
| 9 | Accessibility | Domain-Specific | §7 — project-specific (WCAG) |
| 10 | Tests | Testing | §3 — tests exist, pass, coverage |
| 11 | Performance | Domain-Specific | §7 — N+1, unbounded loops, leaks |
| 12 | Standards | Standards | §5 — named exports, DRY, logging |
| 13 | Database | Domain-Specific | §7 — project-specific (migrations) |
| 14 | Environment config | Security | §4 — no .env committed, Zod validation |
| 15 | Prohibited actions | Architecture | §6 — cross-reference AGENTS.md prohibitions |

Items 1-4, 7-8, 10-12, 14-15 are **universal**. Items 5-6, 9, 13 are **domain-specific** (DMZ's
cybersecurity game). Hence the template: universal categories (§1-§6) + a domain-specific slot (§7).

## Guidelines for Creating a Project Checklist

1. **Start with the template** (§1-§6) — works for any project.
2. **Add domain-specific items** in §7: "What quality concerns are specific to THIS project's domain?"
3. **Mark severity honestly**: BLOCK = "will cause bugs or security issues." WARN = "code quality concern."
4. **Keep it under 20 items total** — beyond 20 the reviewer (human or agent) skims.
5. **Each check is binary** (yes/no): not "code quality is good" but "all public methods have type hints".
6. **Update as the project evolves**: new security concern → add an item; obsolete framework concern → remove it.

## Reviewer Agent Permissions

DMZ pattern: the reviewer agent is **read-only for code**.

| Permission | Reviewer Agent | Implementation Agent |
|------------|---------------|---------------------|
| Read code | ✅ | ✅ |
| Edit code | ❌ | ✅ |
| Write files | ❌ | ✅ |
| Run tests | ✅ (via shell) | ✅ |
| Search/grep | ✅ | ✅ |

**Why**: a reviewer that fixes code bypasses the implement → review separation and hides that the
implementation was wrong. It reports problems; it does not fix them.
