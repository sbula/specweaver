# D-VAL-01 — QA Runner Tool

**Status**: COMPLETED · **Phase**: 1 · **Feature ID**: D-VAL-01

## What it does

The Code Validation engine: runs deterministic code rules against generated source code. It
implements `sw check code` via the unified rules interface.

## Functional Requirements

| # | FR | Actor | Action | Outcome |
|---|-----|-------|--------|---------|
| FR-1 | Code QA Evaluation | Developer | Execute `sw check code` | System runs all deterministic C-series (C01-C08) rules against target files. |

## Progress Tracker

| SF | Name | Depends On | Design | Impl Plan | Dev | Pre-Commit | Committed |
|----|------|-----------|--------|-----------|-----|------------|-----------|
| SF-01 | QA Runner Implementation | — | ✅ | ✅ | ✅ | ✅ | ✅ |
