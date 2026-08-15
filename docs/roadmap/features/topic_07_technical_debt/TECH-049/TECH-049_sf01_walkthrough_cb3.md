# Walkthrough: TECH-049 SF-01 CB-3 — refresh, retire, maintenance CLI

- **Boundary**: 3 of 3 (SF-01 complete)
- **Date**: 2026-08-15
- **Changed**: `scripts/_corpus.py`, `scripts/_mutate.py`, `tests/unit/scripts/test_corpus.py`,
  `tests/integration/scripts/test_corpus_real_source.py` (new),
  `tests/e2e/scripts/test_corpus_cli.py` (new), `docs/dev_guides/writing_mutation_campaigns.md`
  (new), `docs/architecture/06_lessons_and_future/anti_patterns.md`

## What changed and why

`refresh()` re-pins one mutant's `symbol_sha` after its claim has been re-verified; `retire()`
marks a campaign whose requirement was descoped; `main()` exposes both. Together they are the
answer to *"what do I do when the corpus says `STALE`?"* — without them, drift detection reports a
problem with no way to resolve it, and the first refactor would leave every mutant permanently
stale.

Two deliberate absences:

- **No bulk refresh.** `--refresh-all` would clear every `STALE` in one keystroke with nobody
  re-reading a single claim. The one-line diff a refresh leaves in the committed corpus *is* the
  review, which is why the hash lives in the file rather than a cache.
- **Retire marks, never deletes.** A deleted campaign destroys the only record that the
  requirement was ever measured.

## Test results

| Tier | Passed |
|---|---|
| unit | 6,206 |
| integration | 607 |
| e2e | 203 |
| **Full suite** | **7,016 passed, 11 skipped, 0 failed** (61 s, `-n auto`) |

`tests.py cb TECH-049 --kind tooling --all` — unit, integration and e2e all `ok`.

> **Caveat, ticketed as `TECH-050`.** Those runs set `env -u FORCE_COLOR`. With `FORCE_COLOR` set —
> how an agent normally runs — 28 unrelated tests fail on ANSI escapes in CLI-output assertions.
> Pre-existing; verified identical at `72b82df8^`.

## Quality checks

| Check | Result |
|---|---|
| `quality.py cb` | 12 passed, 1 skipped, **0 failed** |
| `quality.py doc` | 9 passed, 0 failed |
| `mypy src/` | Success, 337 files |
| `ruff` | clean |
| `tach` | ok |
| `check_fr_coverage.py TECH-049` | **BLOCKED — correctly.** FR-1, FR-2, FR-13 cited `[Proves:]`; FR-3…FR-12 are unbuilt sub-features |

File sizes: `_corpus.py` **450** against the 451 YELLOW — the user chose to leave it rather than
split the CLI out (plan R-5 trigger, deliberately not taken).

## Mutation evidence

All five CB-3 claims KILLED: refresh refusing a vanished symbol (3 killers), write-back not
reformatting (2), retire marking rather than deleting (2), unknown derived id (1), `--retire`
requiring `--reason` (1).

## HITL gates

| Gate | Found | Decision |
|---|---|---|
| **Phase 2** (architecture + test gap) | 3 architecture findings, 9 test gaps — worst being `main()`'s retire branch with **zero coverage** | User: *"all of them, fix A-1 and A-2"* |
| **Phase 3** (implemented tests) | 9 stories written; story 4 went red and forced a source fix | User approved; chose to leave `_corpus.py` at 450 lines rather than split |

**No gate was skipped or auto-approved in this boundary.**

> **Retroactive review flagged.** CB-1 and CB-2 were committed **without running this skill at
> all** — only the gates it wraps (`tests.py cb`, `quality.py cb`, format, full suite, mutation).
> The Phase 2/3 test-gap analysis never ran for them. Given what one pass found here — an entire
> untested CLI branch and a silently nullified citation — those two boundaries are worth the same
> treatment.

## Findings this gate produced

1. **`main()`'s retire branch had zero coverage.** Four CLI tests existed; every one exited at
   `ap.error` or inside the refresh branch. The function was tested, the path to it was not.
2. **`_rewrite` leaked a bare `OSError`.** Every other fault in the module raises `CorpusError`;
   this one made the caller know the module touches a filesystem. Story 4 went red and fixed it.
3. **Two inline-import anti-patterns fixed** — `import argparse` in `_corpus.main()` (new) and
   `import os` in `_mutate._run()` (pre-existing).
4. **Tier by marker does not work.** Stories 8 and 9 were written `@pytest.mark.integration` /
   `e2e` inside `tests/unit/`. This repo selects tiers by **directory**, so they ran as unit tests
   and would never have been selected by the tier they claimed. Both relocated. Recorded in
   `anti_patterns.md`.
5. **`# fr-coverage: fixture-data` silently nullified a real citation.** The marker is a
   *file-level* exemption, so `Proves: TECH-049 FR-1, FR-1a` counted for nothing and the ledger
   reported the FRs unproven while the tests proving them passed. Its own docstring names this
   failure mode. Fixed by giving fixtures requirement ids the design does not declare (`FR-98`),
   after which the marker is unnecessary. Recorded in `anti_patterns.md`.

Findings 4 and 5 were both **self-inflicted in this boundary** and both would have shipped silently.
