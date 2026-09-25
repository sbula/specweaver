# E-UI-01 — CLI Scaffold

**Status**: COMPLETED · **Phase**: 1 · **Feature ID**: E-UI-01

## What it does

The `sw` CLI entry point, built on Typer. Routes the core commands: scaffold a project, draft a
spec, validate and review specs, generate an implementation, validate and review code.

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

**Since changed** (checked 2026-09-25): the commands are now `sw init <name> --path <dir>`,
`sw check --level=component|feature|code <file>` and `sw review <file> [--spec <spec.md>]`.

## Progress Tracker

| SF | Name | Depends On | Design | Impl Plan | Dev | Pre-Commit | Committed |
|----|------|-----------|--------|-----------|-----|------------|-----------|
| SF-01 | Project Scaffold + CLI Shell | — | ✅ | ✅ | ✅ | ✅ | ✅ |
