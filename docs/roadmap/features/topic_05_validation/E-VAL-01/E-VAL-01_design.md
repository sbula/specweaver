# E-VAL-01 — Core Validation Engine

**Status**: COMPLETED · **Phase**: 1 · **Feature ID**: E-VAL-01

## What it does

The core validation engine and the deterministic `S-Series` rule interface, behind
`sw check spec`.

## Functional Requirements

| # | FR | Actor | Action | Outcome |
|---|-----|-------|--------|---------|
| FR-1 | Spec QA Evaluation | Developer | Execute `sw check spec` | System runs all deterministic S-series rules against target spec files. |
| FR-2 | Extensible Rule Interface | System | Execute rule | Engine uses a common rule abstraction, so rules are injected the standard way. |

## Progress Tracker

| SF | Name | Depends On | Design | Impl Plan | Dev | Pre-Commit | Committed |
|----|------|-----------|--------|-----------|-----|------------|-----------|
| SF-01 | Validation Engine & Static Rules | — | ✅ | ✅ | ✅ | ✅ | ✅ |
