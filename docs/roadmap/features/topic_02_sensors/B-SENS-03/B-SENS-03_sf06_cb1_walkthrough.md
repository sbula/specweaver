# B-SENS-03 SF-06 CB-1 — Walkthrough

**Commit boundary:** CB-1 of 3 · **DAL-B** · 2026-08-26 · **Proves**: `FR-14` · Plan:
[sf06](B-SENS-03_sf06_implementation_plan.md)

## Delivered

`visibility`, `package` and `unit` on every chunk. The filter that matters is *"is this public **to
me**"*: a level and **two radii** — a helper shared inside one package is legitimately internal;
another service's internals are a different question at a different distance.

- `unit` is `""` when the caller supplies no markers `[agreed 2026-08-26]`, never a fallback to
  `package`.
- `chunk_source` stays pure: markers arrive as data; a test patches `builtins.open` and asserts
  nothing was opened.
- `_unit_of` iterates the marker paths **sorted** — frozenset order is hash-based and not stable
  across runs (`NFR-4`), and an order-dependent implementation cannot be pinned by a deterministic
  test.
- A merged chunk is **labelled** with the level its members share.

## Proof

| Test | Why it bites |
|---|---|
| `test_a_marker_outside_this_path_is_ignored`: `src/app` vs `src/application` | a marker outside the path is ignored only via the boundary check when the path is the **longer** of the two (`src/apple` vs `src/app/mod` fails a bare-prefix match anyway) |
| `test_the_nearest_marker_wins_not_the_first` with `src/app/build.gradle` | sorts **before** `src/app/mod/go.mod`, so first-match would be wrong (`src/app/pyproject.toml` sorts after and would not catch it) |
| `test_a_merged_chunk_carries_the_level_its_members_share` | `FR-9`'s guard proves two levels never merge, not the label; a member's level after the fact, or `unknown`, would pass every other test |

| Check | Result |
|---|---|
| Full suite | **8,947 passed, 11 skipped** |
| `quality.py cb` | 15/15 · `doc` 13/13 |
| ruff · ruff format · mypy · complexity · class health · duplication · conventions · tach | all clean |
| Corpus | **44 judged, 44 protected, 0 unprotected, 0 stale** |

Twelve anchors re-hashed and two re-pointed (the preamble call gained its scope arguments).
