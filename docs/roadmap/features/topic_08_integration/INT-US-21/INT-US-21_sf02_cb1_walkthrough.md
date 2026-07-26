# Walkthrough: INT-US-21 SF-02 CB-1 — Decomposition Artifact Persistence (FR-5, FR-7 data)

- **Feature**: INT-US-21 — Autonomous Feature Decomposition (base integration contract)
- **Sub-feature**: SF-02 — Decomposition Artifacts & Frozen Seams
- **Commit boundary**: 1 of 3
- **Implementation plan**: `INT-US-21_sf02_implementation_plan.md` §Work Breakdown → CB-1
- **Date**: 2026-07-26

## What changed and why

`DecomposeFeatureHandler` returned `plan.model_dump()` into the step record and nothing else.
`D-INTL-02` §6.2 had promised a durable `<name>_decomposition.yaml`; it was never shipped, so the
reviewed plan lived only inside a SQLite step record. CB-1 delivers the artifact.

| Change | File | Why |
|---|---|---|
| `_feature_name_from_spec()` | `handlers/decompose.py:27-29` | The bundled pipeline passes no params, so every real run was named `"unknown_feature"` |
| `_persist_decomposition()` | `handlers/decompose.py:32-76` | Derive path → extract-or-generate uuid → tag → write, `PlanSpecHandler`'s *sequence* |
| `_log_decomposition_lineage()` | `handlers/decompose.py:79-110` | `generated_decomposition` lineage event |
| `model_dump(mode="json")` | `handlers/decompose.py:172` | **D1.** `proposed_dal: DALLevel` is required on every component and ruamel raises `RepresenterError` on an enum — python-mode dump fails on 100% of real plans |
| Nested output + `DECOMPOSITION_PLAN_KEY` | `decompose.py:11,~183`, `engine/hydration.py:33-40` | The handler must report `decomposition_path` without that key leaking into the AD-4-frozen `context.decomposition` |

`mode="json"` also makes the on-disk artifact byte-identical to the hydrated
`context.decomposition`, so both halves of the frozen seam agree by construction rather than by
coincidence.

## Test results

| Tier | File | Count |
|---|---|---|
| Integration | `tests/integration/core/flow/handlers/test_decomposition_artifacts_integration.py` | 14 |
| Unit | `tests/unit/core/flow/handlers/test_decompose_artifact.py` | 21 |
| Unit (updated) | `tests/unit/core/flow/handlers/test_decompose.py` | 17 |

**Tier correction.** CB-1 was planned unit-only and built unit-only first — 16 unit tests, zero
integration. That is what triggered `TECH-017`. The integration file is not decoration: the unit
tests construct the handler by hand and mock `context.db`, so they cannot see the real registry row,
the real runner hydration hook, real SQLite, or a real filesystem failure. CB-2's plan line was
corrected the same day to avoid repeating it.

**Both suites proven non-vacuous by probe**, not assumed:

| Probe | Result |
|---|---|
| `mode="json"` → `model_dump()` | 8 of 11 integration tests fail |
| `output={"plan": …}` → flattened | exactly the 3 seam-agreement tests fail |

## Quality gates

`ruff check src/ tests/` clean · `mypy` clean · `tach check` *All modules validated* · C901 clean ·
`check_file_sizes` 0 errors · `check_roadmap_sync` green · `check_fr_coverage.py INT-US-21` blocks
only on FR-9, whose test is CB-3 work.

## What the pre-commit gate uncovered

The gate was run in full at the user's request rather than being waved through on green checks. It
found one live defect and one fragile seam — both in code CB-1 itself introduced.

### T1 — a telemetry failure discarded the decomposition (fixed)

`_log_decomposition_lineage` was awaited **outside** D6's `try/except OSError`, and `execute`'s
outer `except Exception` returns `ERROR` with **no `output`**. So an unusable lineage DB threw away
an LLM-paid decomposition that was already durably on disk — the exact loss D6 exists to prevent.
D6 had been implemented for the artifact write and not for the telemetry call immediately after it.

Reproduced with a `Database` pointing at a never-bootstrapped file (`flow_artifact_events` missing):
the run failed and `context.decomposition` was `None`. Fixed by making the lineage helper
non-raising, logging at exception level so it stays loud in logs while the run continues.

### A1 — the frozen seam was two string literals (fixed)

`"plan"` was written in `decompose.py` and read in `hydration.py` as bare literals, with nothing
forcing them to agree. AD-4 calls this a frozen seam; it was frozen by duplication. Now
`DECOMPOSITION_PLAN_KEY`, defined in `engine/hydration.py` (which imports no handlers, so the
direction stays handlers → engine) and imported by both sides. A test asserts the writer's output
key and hydration's read key are that one symbol.

### Coverage gaps closed (behaviour was already correct, just unverified)

`_feature_name_from_spec` for a spec without the `_feature_spec` suffix and for the pathological
`_feature_spec.md` (strips to `""` → the `or` guard); an existing artifact whose lineage tag was
stripped by hand (a fresh uuid is minted); an invalid `render_profile`; a missing spec file.

### Red/Blue (Phase 7.5)

| # | Attack | Verdict |
|---|---|---|
| 1 | Path traversal via the artifact path | **Safe** — `spec_path.with_name()` cannot leave the parent directory, and the path never derives from LLM output. LLM-derived component names are CB-2's concern (NFR-5) |
| 2 | Newline injection through a hand-crafted uuid into the tag comment | **Safe, verified** — `_UUID_PATTERN` (`lineage.py:11`) is a strict hex-and-dash UUID regex, so a newline cannot survive extraction |
| 3 | Malicious YAML in LLM plan content | **Safe** — ruamel quotes on dump; content never re-enters an executable path |
| 4 | Symlink at the artifact path is followed by `write_text` | **Pre-existing class**, identical in `PlanSpecHandler`. Belongs to `TECH-016`'s unified writer, not here |
| 5 | Two concurrent runs decomposing one spec → last-write-wins, uuid divergence | **Noted** — `TECH-014` (fan-out shares one `RunContext`) is the ticket that owns concurrent sub-runs |

## Findings deliberately NOT acted on

| Finding | Why not here |
|---|---|
| `decompose.py` is 453 lines (YELLOW > 450; 0 errors) | CB-2 adds stub-spec code to this same file and will push it materially past the threshold, so the extraction belongs there. Doing it now would also collide with `TECH-016`, which owns the shared artifact writer and mandates its own commits |
| 6th hand-rolled copy of derive→uuid→tag→write→lineage | `TECH-016`, exactly as the design predicted ("SF-02 adds a sixth") |
| New inline imports at `decompose.py:42-47,92` | Mirror `generation.py:360-365` byte-for-byte; covered by the existing **DEFERRED** "Inline Imports (Monolith Purge)" row, which already names `core/flow/handlers/*`. No new violation class, so no new row |
| `if tag_str:` (`decompose.py:66`) is unreachable | `wrap_artifact_tag` returns `None` only for empty/unsupported languages and `"yaml"` is hardcoded. Harmless defensive branch; removing it would diverge from `PlanSpecHandler` ahead of `TECH-016` |
| Pre-commit skill Phase 1 §1.1/§1.8 point at `docs/architecture/architecture_reference.md`, deleted by TECH-008; §1.9 and §2.8 give contradictory output-format orders | Process defects in the skill itself, not in this feature. Worth a ticket |

## What CB-1 does NOT do

No stub component specs (FR-6 → CB-2). No plan-bridge seam pin or park rendering (FR-9(b)/FR-7
summary → CB-3). No CLI journey or e2e proof (FR-8/FR-10 → SF-03). FR-9(a)'s fan-out pin was
descoped on 2026-07-26 — `C-FLOW-12` does not exist yet.
