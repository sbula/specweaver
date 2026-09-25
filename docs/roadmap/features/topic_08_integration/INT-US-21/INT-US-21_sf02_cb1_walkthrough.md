# INT-US-21 SF-02 CB-1 — Walkthrough: Decomposition Artifact Persistence (FR-5, FR-7 data)

**Commit boundary:** 1 of 3 (`4a42b87a`) · **Date:** 2026-07-26 · Plan:
[sf02](INT-US-21_sf02_implementation_plan.md) §Changes → CB-1

## Delivered

The reviewed plan is a durable `<name>_decomposition.yaml` next to the spec — `D-INTL-02` §6.2's
unshipped promise. Before, it lived only inside a SQLite step record.

| Change | File | Why |
|---|---|---|
| `_feature_name_from_spec()` | `handlers/decompose.py:27-29` | The bundled pipeline passes no params, so every real run was named `"unknown_feature"` |
| `_persist_decomposition()` | `handlers/decompose.py:32-76` | Derive path → extract-or-generate uuid → tag → write, `PlanSpecHandler`'s *sequence* |
| `_log_decomposition_lineage()` | `handlers/decompose.py:79-110` | `generated_decomposition` lineage event |
| `model_dump(mode="json")` | `handlers/decompose.py:172` | **D1.** `proposed_dal: DALLevel` is required on every component and ruamel raises `RepresenterError` on an enum — python-mode dump fails on 100% of real plans |
| Nested output + `DECOMPOSITION_PLAN_KEY` | `decompose.py:11,~183`, `engine/hydration.py:33-40` | The handler reports `decomposition_path` without that key leaking into the AD-4-frozen `context.decomposition` |

- `mode="json"` makes the on-disk artifact byte-identical to the hydrated `context.decomposition`.
- **A lineage failure keeps the decomposition.** `_log_decomposition_lineage` is non-raising (logs
  at exception level). It had been awaited outside D6's `try/except OSError`, so an unusable lineage
  DB (a `Database` on a never-bootstrapped file, `flow_artifact_events` missing) hit `execute`'s outer
  `except Exception`, which returns `ERROR` with no `output` and
  `context.decomposition` `None` — discarding an LLM-paid plan already on disk.
- **One key, not two literals.** `DECOMPOSITION_PLAN_KEY` lives in `engine/hydration.py` (which
  imports no handlers — direction stays handlers → engine) and replaces a `"plan"` literal written in
  `decompose.py` and read in `hydration.py`. A test asserts both sides use that symbol.

## Proof

| Tier | File | Count |
|---|---|---|
| Integration | `tests/integration/core/flow/handlers/test_decomposition_artifacts_integration.py` | 14 |
| Unit | `tests/unit/core/flow/handlers/test_decompose_artifact.py` | 21 |
| Unit (updated) | `tests/unit/core/flow/handlers/test_decompose.py` | 17 |

Integration tier added after the first build was unit-only (16 unit, zero integration — the
`TECH-017` trigger): unit tests build the handler by hand and mock `context.db`, so they cannot see
the real registry row, hydration hook, SQLite, or filesystem failure.

| Non-vacuity probe | Result |
|---|---|
| `mode="json"` → `model_dump()` | 8 of 11 integration tests fail |
| `output={"plan": …}` (`output["plan"]`) → flattened | exactly the 3 seam-agreement tests fail |

Also covered: `_feature_name_from_spec` without the `_feature_spec` suffix and for
`_feature_spec.md` (strips to `""` → the `or` guard); an artifact whose lineage tag was stripped by
hand (fresh uuid); an invalid `render_profile`; a missing spec file.

`ruff check src/ tests/` clean · `mypy` clean · `tach check` *All modules validated* · C901 clean ·
`check_file_sizes` 0 errors · `check_roadmap_sync` green · `check_fr_coverage.py INT-US-21` blocked
only on FR-9 until CB-3.

Red/Blue (Phase 7.5):

| # | Attack | Verdict |
|---|---|---|
| 1 | Path traversal via the artifact path | **Safe** — `spec_path.with_name()` cannot leave the parent directory; the path never derives from LLM output |
| 2 | Newline injection through a hand-crafted uuid into the tag comment | **Safe, verified** — `_UUID_PATTERN` (`lineage.py:11`) is a strict hex-and-dash UUID regex |
| 3 | Malicious YAML in LLM plan content | **Safe** — ruamel quotes on dump; content never re-enters an executable path |
| 4 | Symlink at the artifact path followed by `write_text` | **Pre-existing class**, same in `PlanSpecHandler` → `TECH-016` |
| 5 | Two concurrent runs on one spec → last-write-wins, uuid divergence | **Noted** → `TECH-014` |

## Findings still open

| Finding | Why not here |
|---|---|
| `decompose.py` 453 lines (YELLOW > 450) | Extracted in CB-2, which adds to the same file |
| 6th hand-rolled derive→uuid→tag→write→lineage | `TECH-016` |
| New inline imports at `decompose.py:42-47,92` | Mirror `generation.py:360-365`; covered by the DEFERRED "Inline Imports (Monolith Purge)" row for `core/flow/handlers/*` — no new row |
| `if tag_str:` (`decompose.py:66`) unreachable | `wrap_artifact_tag` returns `None` only for empty/unsupported languages; `"yaml"` is hardcoded. Kept to match `PlanSpecHandler` ahead of `TECH-016` |
| Pre-commit skill Phase 1 §1.1/§1.8 point at `docs/architecture/architecture_reference.md` (deleted by TECH-008); §1.9 and §2.8 give contradictory output-format orders | Skill process defects — worth a ticket |
