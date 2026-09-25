# Project Constitution Template

**Status**: DRAFT, 2026-03-08. **Scope**: universal template — each project using SpecWeaver creates
its own constitution from it.

| | |
|---|---|
| Overview | [Methodology Index](../04_pipelines_and_methodology/methodology_index.md) |
| Reference | [DMZ Repository — SOUL.md](https://github.com/TheMorpheus407/the-dmz) (the DMZ project's `SOUL.md` is its constitution) |

## Purpose

A Constitution is a **read-only, human-authored document** with a project's non-negotiable rules.
Every agent, persona and flow reads it first. Agents cannot modify it — only the HITL, by explicit,
deliberate action.

It answers: *"What is always true about this project, regardless of which feature we're building?"*

### Why a Constitution Exists

Without one:
- Agents invent architecture decisions that contradict the project's intent
- Different sessions produce inconsistent code (one uses SQLite, another uses PostgreSQL)
- Security invariants get silently violated when an agent "optimizes"
- Technical standards drift as agents pick whatever works at the moment

With one:
- Every agent starts from the same non-negotiable constraints
- Architectural consistency is enforced by document, not by memory
- Security invariants are explicitly stated and checkable

### Reference: DMZ's SOUL.md
The DMZ repository ([github.com/TheMorpheus407/the-dmz](https://github.com/TheMorpheus407/the-dmz))
uses `SOUL.md`: project identity, tech stack table, 7 architecture principles, coding standards,
security principles, key documents index. Every DMZ agent reads `SOUL.md` first.

## Template

Each section carries guidance on what to include. Replace every `[...]` placeholder.

```markdown
# [Project Name] — Constitution

> **Status**: ACTIVE
> **Owner**: [HITL name/role]
> **Rule**: This file is READ-ONLY for agents. Only [Owner] may modify it.
> **Last Updated**: [date]

---

## 1. Identity

**Project**: [Name]
**One-Line Purpose**: [What this project does, in one sentence]
**Domain**: [Industry/domain — e.g., fintech, healthcare, developer tools]
**Target Users**: [Who uses this]

## 2. Tech Stack

| Layer | Technology | Version | Rationale |
|-------|-----------|---------|-----------|
| Language | [e.g., Python] | [e.g., 3.12+] | [Why this choice] |
| Framework | [e.g., FastAPI] | [e.g., 0.109+] | |
| Database | [e.g., SQLite → PostgreSQL] | | |
| Testing | [e.g., pytest] | | |
| CI/CD | [e.g., GitHub Actions] | | |
| Containerization | [e.g., Docker] | | |

**Rule**: Agents MUST NOT introduce technologies not listed here without HITL approval.

## 3. Architecture Principles (Non-Negotiable)

List the rules that NEVER change regardless of feature being built.
Each principle must be:
- Specific (not "write good code")
- Testable (you can verify compliance)
- Permanent (won't change with next feature)

Example principles:
1. **Deployment Isolation**: SpecWeaver must NOT reside within the target project's directory tree.
2. **Spec-First**: No implementation without a spec that passes the 10-test battery.
3. **Deterministic over Stochastic**: Prefer AST-based validation over LLM-based review for correctness checks.
4. **JSON State V1**: State persistence uses JSON files until SQLite migration is explicitly started.
5. **Test Coverage ≥ 70%**: No PR merges below this threshold.

## 4. Coding Standards

Define project-specific code style rules:
- Naming conventions
- Import ordering
- Error handling patterns (standard exceptions, error codes)
- Logging format
- Documentation requirements (docstrings, type hints)

**Rule**: These standards apply to ALL code, whether written by a human or an agent.

## 5. Security Invariants

List security rules that must never be violated:
- Input validation boundaries
- Authentication/authorization model
- Secret management rules (no secrets in code, no .env committed)
- Sandboxing/isolation requirements
- OWASP considerations relevant to this project

## 6. Prohibited Actions

Explicit list of things agents must NEVER do.

### Filesystem
- [ ] Never read/write outside [project root]
- [ ] Never delete top-level directories
- [ ] Never modify this Constitution without HITL instruction
- [ ] Never write secrets to tracked files

### Git
- [ ] Never `git push --force` to main/master
- [ ] Never `git reset --hard` without HITL instruction
- [ ] Never skip hooks (`--no-verify`)

### System
- [ ] Never install system-level packages
- [ ] Never start persistent background services
- [ ] Never download remote binaries

### Project-Specific
- [Add project-specific prohibitions here]

## 7. Key Documents Index

| Document | Purpose | Path |
|----------|---------|------|
| Constitution | This file — non-negotiable rules | `CONSTITUTION.md` |
| Methodology | Spec writing and validation rules | `docs/architecture/spec_methodology.md` |
| Roadmap | Current project plan | `docs/roadmap/specweaver_roadmap.md` |
| [Add more as needed] | | |

## 8. Agent Instructions

**Before starting ANY work, every agent MUST:**
1. Read this Constitution in full
2. Read the relevant Component Spec(s)
3. Check the living memory / project state for current context
4. Verify that the planned work does not violate any section above

**If an agent encounters a conflict between a spec and this Constitution, the Constitution wins.**
```

## Guidance Notes

### What Belongs in a Constitution vs. a Spec

| If it's about... | It belongs in... |
|-------------------|-----------------|
| What technologies we use | Constitution §2 |
| How a specific component works | Component Spec |
| What agents are never allowed to do | Constitution §6 |
| How errors are handled in the Flow Engine | Component Spec (Policy section) |
| Our minimum test coverage threshold | Constitution §3 |
| The JSON schema for a flow definition | Component Spec (Contract section) |

**Rule of thumb**: applies to the WHOLE project regardless of feature → Constitution. Applies to ONE
component → Spec.

### Size Budget

**≤ 5KB**. Larger means component-level detail that belongs in specs. DMZ's `SOUL.md` is ~3KB — a
good target.

### Maintenance

- Modified RARELY — only when a fundamental project decision changes
- Every change needs HITL review and explicit approval
- Log changes (date + rationale) for the audit trail
- Agents flag a potential Constitution violation instead of silently working around it
