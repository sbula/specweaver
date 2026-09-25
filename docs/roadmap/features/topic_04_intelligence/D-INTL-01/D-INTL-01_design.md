# D-INTL-01 — Implementation Generator

**Status**: COMPLETED · **Phase**: 1 · **Feature ID**: D-INTL-01

## What it does

Generates application code and unit tests from a validated spec, inside the pipeline, and reviews
the generated code with an LLM against the spec.

## Functional Requirements

| # | FR | Actor | Action | Outcome |
|---|-----|-------|--------|---------|
| FR-1 | Code Generation | Developer | Execute `sw implement` | LLM generates implementation artifacts based on the Spec. |
| FR-2 | Test Generation | Developer | Execute test generation phase | LLM generates `test_<name>.py` mapping to spec scenarios. |
| FR-3 | Code Review | Developer | Execute `sw review code` | LLM evaluates the target implementation strictly against the Spec constraints, returning `ACCEPTED` or `DENIED`. |

## Sub-features

| SF | Does | FRs | Plan |
|----|------|-----|------|
| SF-01 | Generation engine + code review | FR-1, FR-2, FR-3 | [sf01](D-INTL-01_sf01_implementation_plan.md) |

## Progress Tracker

| SF | Name | Depends On | Design | Impl Plan | Dev | Pre-Commit | Committed |
|----|------|-----------|--------|-----------|-----|------------|-----------|
| SF-01 | Generation Engine & Review | — | ✅ | ✅ | ✅ | ✅ | ✅ |
