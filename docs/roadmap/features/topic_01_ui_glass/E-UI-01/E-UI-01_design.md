# Design: CLI Scaffold

- **Feature ID**: E-UI-01
- **Phase**: 1
- **Status**: COMPLETED
- **Design Doc**: docs/roadmap/features/topic_01_ui_glass/E-UI-01/E-UI-01_design.md

## Feature Overview

Feature E-UI-01 establishes the foundational CLI Entry Point (`sw`) using Typer. It sets up the core routing for scaffolding projects, drafting specs, validating/reviewing specs, and generating implementations.

## Functional Requirements

| # | FR | Actor | Action | Outcome |
|---|-----|-------|--------|---------|
| FR-1 | Project Scaffold | Developer | Run `sw init --project <path>` | Sets up target project and initializes configuration. |
| FR-2 | Collaborative Drafting | Developer | Run `sw draft <name>` | Starts collaborative spec writing via LLM. |
| FR-3 | Spec QA Validation | Developer | Run `sw check spec <spec.md>` | Runs deterministic spec validation rules. |
| FR-4 | Spec QA Review | Developer | Run `sw review spec <spec.md>` | Runs semantic spec review via LLM. |
| FR-5 | Implementation Generation | Developer | Run `sw implement <spec.md>` | Generates code and tests from the spec. |
| FR-6 | Code QA Validation | Developer | Run `sw check code <file>` | Runs deterministic code validation rules. |
| FR-7 | Code QA Review | Developer | Run `sw review code <file>` | Runs semantic code review via LLM. |

## Progress Tracker

| SF | Name | Depends On | Design | Impl Plan | Dev | Pre-Commit | Committed |
|----|------|-----------|--------|-----------|-----|------------|-----------|
| SF-1 | Project Scaffold + CLI Shell | — | ✅ | ✅ | ✅ | ✅ | ✅ |

## Session Handoff

**Current status**: Feature E-UI-01 is **COMPLETED**.
