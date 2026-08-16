# Implementation Plan: 24 Tests Look Like Coverage and Never Run

- **Feature ID**: TECH-051
- **Design Document**: docs/roadmap/features/topic_07_technical_debt/TECH-051/TECH-051_design.md
- **Implementation Plan**: docs/roadmap/features/topic_07_technical_debt/TECH-051/TECH-051_implementation_plan.md
- **Status**: APPROVED (2026-08-16)

**FRs owned: FR-1, FR-2, FR-3, FR-4, FR-5, FR-6, FR-7** — one feature, three boundaries.

> **Written after the fact, and that is a finding rather than a shortcut.** The design was approved
> and CB-1 started without a plan, so `check_fr_coverage.py TECH-051` reported all seven FRs as
> *carried by no implementation plan* at closure — the same gap this ticket found in `A-VAL-01`'s
> four plans, committed the same day by the agent fixing it. The ownership below is mapped from
> what each boundary actually delivered, not assigned to make the ledger green.

## Boundary ownership

| Boundary | FRs | Delivered | Commit |
|---|---|---|---|
| **CB-1** | FR-4, FR-5 | three classes renamed so their 24 tests run; the misplaced gRPC test moved into the file named after the code it covers | `2d8582f0` |
| **CB-2** | FR-6, FR-7 | the nine empty stubs filled; the new tests cited to `A-VAL-01`, and its four plans given the FR ownership they never declared | `5aeac638` |
| **CB-3** | FR-1, FR-2, FR-3 | `check_test_collection.py`, registered from `quick` upward, with its static rule pinned against a real `--collect-only` pass | this commit |

## Why the order was fill-first, gate-last

The alternative — land the gate first and carry the nine stubs as a temporary exception — was
rejected in design and stayed rejected. An escape hatch introduced to make a gate land is the
mechanism that calcifies, and this ticket exists because something calcified.

The cost is that the gate arrives green, having never found a real defect in flight. That is bought
back two ways: its own tests are synthetic (one file per cause), and it was run against a worktree
at `2d8582f0^`, where it reports exactly the twelve files that were wrong with the right cause for
each. See the design's *Delivery evidence*.

## Proof, per FR

| FR | Proven by | Tier |
|---|---|---|
| FR-1 | `tests/integration/scripts/test_collection_gate_seam.py` — the real script, real exit codes | integration |
| FR-2 | `test_check_test_collection.py::TestCompareWithPytest` — the static rule against a live collection pass | unit |
| FR-3 | `TestContributedTestsWithMarkers` + the seam test | unit + integration |
| FR-4 | `test_runner_telemetry.py`, `test_runner_events.py`, `test_kind_presets.py` — 24 tests that now run | unit + integration |
| FR-5 | `tests/unit/sandbox/protocol/core/protocol/test_grpc_parser.py` | unit |
| FR-6 | the eight other files under `tests/unit/sandbox/protocol/` | unit |
| FR-7 | `test_collection_gate_seam.py::TestProtocolCoverageStaysAttributed` — the ledger itself, asserted | integration |

**No e2e, deliberately.** The repo's e2e tier is `sw` command journeys; `quality.py` is a developer
gate and the two are separate tracks. An e2e here would be the same subprocess call from a different
directory, and `check_proof_tier.py` counts tiers so that padding is visible rather than rewarded.

## Out of scope

- The 13 `live`-marked files. Excluded on purpose and correctly.
- Widening `R6` to judge collectability as well as naming. The collection check answers that
  question directly and catches the two causes `R6` cannot see.
- Re-testing `sandbox/protocol` beyond what `A-VAL-01` declares. Its five FRs are the contract.
