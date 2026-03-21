# specweaver — Constitution

> **Status**: ACTIVE
> **Owner**: TODO
> **Rule**: This file is READ-ONLY for agents. Only the owner may modify it.
> **Last Updated**: TODO

---

## 1. Identity

**Project**: specweaver
**One-Line Purpose**: TODO: What this project does, in one sentence.
**Domain**: TODO: Industry/domain
**Target Users**: TODO: Who uses this

## 2. Tech Stack

| Layer | Technology | Version | Rationale |
|-------|-----------|---------|-----------|
| Language | TODO | TODO | TODO |
| Framework | TODO | TODO | TODO |
| Database | TODO | TODO | TODO |
| Testing | TODO | TODO | TODO |

**Rule**: Agents MUST NOT introduce technologies not listed here without HITL approval.

## 3. Architecture Principles (Non-Negotiable)

1. TODO: First principle
2. TODO: Second principle

## 4. Coding Standards

- TODO: Naming conventions
- TODO: Error handling patterns
- TODO: Documentation requirements

**Rule**: These standards apply to ALL code, whether written by a human or an agent.

## 5. Security Invariants

- TODO: Input validation rules
- TODO: Secret management rules

## 6. Prohibited Actions

### Filesystem
- Never modify this Constitution without HITL instruction
- Never write secrets to tracked files

### Git
- Never `git push --force` to main/master

### Project-Specific
- TODO: Add project-specific prohibitions

## 7. Key Documents Index

| Document | Purpose | Path |
|----------|---------|------|
| Constitution | This file — non-negotiable rules | `CONSTITUTION.md` |
| TODO | TODO | TODO |

## 8. Agent Instructions

**Before starting ANY work, every agent MUST:**
1. Read this Constitution in full
2. Read the relevant Component Spec(s)
3. Verify that the planned work does not violate any section above

**If an agent encounters a conflict between a spec and this Constitution, the Constitution wins.**
