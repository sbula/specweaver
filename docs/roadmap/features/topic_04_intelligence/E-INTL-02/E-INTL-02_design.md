# E-INTL-02 — Spec Drafting & Review

**Status**: COMPLETED · **Phase**: 1 · **Feature ID**: E-INTL-02

## What it does

- `sw draft` — the interactive Human-In-The-Loop spec drafting orchestrator: collaborative
  component spec authoring.
- `sw review` — the semantic LLM evaluation engine behind it.

## Functional Requirements

| # | FR | Actor | Action | Outcome |
|---|-----|-------|--------|---------|
| FR-1 | Interactive Drafting | Developer | Execute `sw draft` | Starts a conversational LLM session prompting for missing sections. |
| FR-2 | Human-In-The-Loop | Developer | Prompt interaction | HITL can accept, modify, or reject agent suggestions. |
| FR-3 | Spec Review Validation | Developer | Execute `sw review spec` | LLM evaluates the final spec semantically. |

## Progress Tracker

| SF | Name | Depends On | Design | Impl Plan | Dev | Pre-Commit | Committed |
|----|------|-----------|--------|-----------|-----|------------|-----------|
| SF-01 | Spec Drafting & Spec Review | — | ✅ | ✅ | ✅ | ✅ | ✅ |
