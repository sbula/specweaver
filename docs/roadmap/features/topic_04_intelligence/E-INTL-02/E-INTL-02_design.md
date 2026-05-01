# Design: Spec Drafting & Review

- **Feature ID**: E-INTL-02
- **Phase**: 1
- **Status**: COMPLETED
- **Design Doc**: docs/roadmap/features/topic_04_intelligence/E-INTL-02/E-INTL-02_design.md

## Feature Overview

Feature E-INTL-02 introduces the interactive Human-In-The-Loop Spec Drafting orchestrator, enabling collaborative component specification authoring. It also implements the semantic LLM evaluation engine required for the `sw review` commands.

## Functional Requirements

| # | FR | Actor | Action | Outcome |
|---|-----|-------|--------|---------|
| FR-1 | Interactive Drafting | Developer | Execute `sw draft` | Starts a conversational LLM session prompting for missing sections. |
| FR-2 | Human-In-The-Loop | Developer | Prompt interaction | HITL can accept, modify, or reject agent suggestions. |
| FR-3 | Spec Review Validation | Developer | Execute `sw review spec` | LLM evaluates the final spec semantically. |

## Progress Tracker

| SF | Name | Depends On | Design | Impl Plan | Dev | Pre-Commit | Committed |
|----|------|-----------|--------|-----------|-----|------------|-----------|
| SF-1 | Spec Drafting & Spec Review | — | ✅ | ✅ | ✅ | ✅ | ✅ |

## Session Handoff

**Current status**: Feature E-INTL-02 is **COMPLETED**.
