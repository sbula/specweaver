# Design: No CI Runs the Tests

- **Feature ID**: TECH-094
- **Epic**: Topic 07 (Technical Debt)
- **Status**: STUB — not yet run through the `specweaver-design` skill
- **Kind**: `tooling`
- **Origin**: 2026-11-06, after `TECH-079`; the user's order puts CI first (before RAG). Only
  `.github/workflows/container.yml` exists, and it builds the container image on a version tag.
  Nothing on GitHub runs a test, so a push that breaks the suite or the gates is seen only locally.

## Problem Statement

The suite (unit, integration, e2e; 12,669 tests on 2026-11-06) and the commit gate
(`scripts/quality.py cb`) run only on the developer's machine, through `scripts/commit_gated.py`.
GitHub shows no proof that `main` passes. The README promises Python 3.11+, but every run is on
3.14.

## Candidate Approaches (not yet designed)

Agreed with the user 2026-11-06 ("A, go on"):
- A GitHub Actions workflow on push and pull request runs the default suite (`-m 'not live and not
  toolchain'`: unit, integration, e2e) and `quality.py cb` `[agreed 2026-11-06]`.
- On Python 3.11 and 3.14; what breaks on 3.11 is fixed here `[agreed 2026-11-06]`.
- mypy stays the only type check; no pyright `[agreed 2026-11-06]`.
- CI never calls a real model: no provider keys in CI, and an attempted model call fails loudly
  `[agreed 2026-11-06]` (the user, twice).

## Non-Goals (proposed, pending design)

- The `live` tier (real models) and the `toolchain` tier (real Maven, Gradle, npm, cargo): they stay
  in the local nightly run (`TECH-049` AD-8).
- The nightly mutation corpus.

## Next Step

`specweaver-feature TECH-094`.
