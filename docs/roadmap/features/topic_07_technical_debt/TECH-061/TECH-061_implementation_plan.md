# Implementation Plan: TECH-061

- **Feature ID**: TECH-061
- **Status**: DELIVERED 2026-08-19
- **Commit boundaries**: one

## CB-1 — one source of truth for what is collectable

| Task | FR | Change |
|---|---|---|
| T1 | FR-1 | `_parseable_suffixes`: derive from `get_default_parsers()` rather than restating `.py` |
| T2 | FR-1 | `collect_files` uses it for both the single-file and the directory branch |
| T3 | FR-1 | Remove the discharged `xfail(strict=True)`, which turned XPASS on the first run |
| T4 | FR-2 | Cover the directory walk, which no test drove — the single-file test leaves it dead |

**T4 exists because a mutant survived.** Reverting the walk to `*.py` kept every test green, which
means the branch the real CLI takes was untested. Finding that took mutating the fix rather than
trusting it.
