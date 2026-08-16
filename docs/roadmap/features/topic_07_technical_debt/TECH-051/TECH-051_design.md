# Design: 24 Tests Look Like Coverage and Never Run

- **Feature ID**: TECH-051
- **Epic**: Topic 07 (Technical Debt)
- **Status**: COMPLETE 2026-08-16 — scope extended to cover `A-VAL-01`. CB-1, CB-2 and CB-3 delivered.
- **Design Doc**: docs/roadmap/features/topic_07_technical_debt/TECH-051/TECH-051_design.md
- **Origin**: 2026-08-16, `INT-US-16` CB-1. Checking whether the runner's telemetry flush was
  already covered at unit tier before writing a duplicate test. It looked covered. It was not.

> **Proportionality.** It began as a tooling ticket — one check and three renamed classes. Probing
> the nine "empty stubs" turned it into a coverage ticket as well, because they are named after a
> **delivered DAL-A capability with almost no tests**. Scope extended deliberately by the user
> 2026-08-16: correct all of it here rather than filing a second ticket. What earns the space below
> is the measurement, since every number in the original stub changed meaning once it was probed.

## Feature Overview

`TECH-051` makes it impossible for a test file to exist in this repo and contribute nothing without
a gate saying so. It solves the case where a file reads as coverage in a directory listing, in
review, and to anyone deciding not to write a test because one appears to exist — while pytest never
collects a single node from it. It touches `scripts/` (one new check plus its registration) and the
three test files that carry the 24 hidden tests, and does **not** touch the `live`-marked files,
which are excluded on purpose and correctly. Key constraint: the check must agree with pytest's real
collection rules, and must be cheap enough to sit in a commit gate.

## Research Findings

### The census, re-taken 2026-08-16 (as the stub demanded)

| | |
|---|---|
| test files on disk | 570 |
| excluded only by the `live` marker — legitimate | 13 |
| **uncollectable at all** | **12** |
| ├ a class holding `test_*` methods, not named `Test*` | **3 files, 24 tests** |
| └ files defining nothing at all | **9** |

```
10  tests/integration/assurance/validation/test_kind_presets.py
 8  tests/unit/core/flow/engine/test_runner_events.py
 6  tests/unit/core/flow/engine/test_runner_telemetry.py
```

### The 24 pass immediately — and they are not vacuous

Renaming the three classes and running them: **24 passed, 0 failed.** So the content fix is three
lines, not a rescue.

The more important question is whether they *prove* anything, since a test that has never run has
never failed for the right reason. Mutation says yes, mostly:

| Mutant | Result |
|---|---|
| `flush_telemetry`: `llm.flush(db)` → `pass` | **KILLED — 3 tests objected** |
| `flush_telemetry`: `if not isinstance(llm, TelemetryCollector):` → `if False:` | **SURVIVED** |

The first recovers real, live protection for the claim `INT-US-16` needed and could not use. The
second is a genuine weakness now visible: `test_no_flush_when_llm_is_not_collector` passes because
the `AttributeError` it would provoke is swallowed by the surrounding `except Exception` — the
`isinstance` guard is redundant with the try/except, so removing it changes nothing observable. Two
guards for one property, the same shape `INT-US-16` NFR-1 turned out to have.

### The nine empty files are the right filenames, waiting for their contents

They are named exactly as the tests that need writing would be named:

```
core/protocol/    test_asyncapi_parser.py  test_grpc_parser.py     test_openapi_parser.py
                  test_protocol_atom.py    test_protocol_factory.py
                  test_atom_edge_cases.py  test_foundations.py
interfaces/       test_protocol_tool.py    test_protocol_tool_edge_cases.py
```

So the resolution is neither deletion nor an exception list: **fill them.** That closes the gate's
last finding and gives `A-VAL-01` the coverage it never had, in one move.

### They are NOT clutter, and this reverses the stub's own proposal

The stub called them a non-goal and suggested deleting them was "trivial and probably right".
**Git says otherwise.** All nine were created empty in `14d889f2` *(chore(quality): consolidated
quality and test gate runners)* — two lines each, a licence header and nothing else. They have never
held a test.

They are named after `src/specweaver/sandbox/protocol/`: **8 modules, 548 lines, and no real tests
anywhere in the repo.** Grepping the whole suite for that package finds three files that merely
mention it in passing.

So the nine are a **fig leaf over an untested 548-line package**. Deleting them would make this
gate pass and make the gap *more* invisible — which is the exact move this repo keeps punishing.

### What the double-check found: one real test, misplaced

Greps were not trusted; every one of the 11 public symbols was searched, then the code was mutated:

| Mutant | Result |
|---|---|
| `GRPCParser`: `raise ProtocolSchemaError(f"Failed to parse gRPC schema: {e}") from e` → `return []` | **KILLED — 1 test** |
| `OpenAPIParser`: `if "paths" not in parsed:` → `if False:` | **SURVIVED — 0 tests, whole suite** |

**One genuine test exists and is in the wrong file.**
`tests/integration/infrastructure/test_llm_logging_integration.py::test_malformed_protocol_payload_emits_error_log`
drives `GRPCParser.extract_endpoints` with broken proto and asserts `ProtocolSchemaError` plus the
log — a proper hostile-input test, living in a file about **LLM logging**, and the single protector
of that path.

**One "mention" is not coverage at all.** `test_check_class_health.py` names `GRPCParser` and
`AsyncAPIParser` only in a **comment** describing a synthetic fixture shape. Pure name collision,
and exactly the hazard the closure contract warns about — a file that *discusses* a thing read as
one that proves it. A grep-based audit counts it; a mutant does not.

**Seven of eleven symbols are named by no test anywhere**: `ProtocolAtom`, `ProtocolParserFactory`,
`ProtocolMessage`, `ProtocolSchemaSet`, `ProtocolSchemaInterface`, and `OpenAPIParser` /
`AsyncAPIParser` as code. Two of the three formats `A-VAL-01` promises have **zero** protection,
established by mutation rather than by absence of a string. `ProtocolTool` appears twice, both times
as registry wiring, and the contract-drift e2e imports a model and mocks past the parsers entirely.

So `A-VAL-01` is not "untested" — it is **one hostile path of one of three parsers, in the wrong
file**, and `check_fr_coverage.py A-VAL-01` reports 0 of 5 FRs carried by a plan or cited by a test
while the capability sits at `✅`, DAL-A.

### Why no existing rule catches this

- **`R6`** (`scripts/_test_class_naming.py`) requires a test class to name the symbol under test. It
  would have judged `QARunnerTelemetryFlush` on its **name** and has no opinion on whether the class
  is **collected** — the property that actually matters. Same blind spot `TECH-050` closed when `R6`
  could not see `tests/` helper modules.
- **`_silent_skips.py`** catches a test that skips itself. This is the tier below: never asked to
  run at all.
- **`check_proof_tier.py`** sweeps delivered contracts for proof that does not exist. A cited proof
  file that collects nothing satisfies it today.
- **`test_basenames`** checks file naming, not content.

### Reproducing the census

The command is part of the finding, because the first two attempts at it were wrong:

```bash
.venv/bin/python -m pytest --collect-only -q -p no:tach \
  --override-ini="addopts=--import-mode=importlib" | grep '::' | cut -d: -f1 | sort -u
```

`--override-ini` is load-bearing: the repo's `addopts` carries `-v`, which turns `--collect-only -q`
into a **tree** rather than node ids — a first attempt parsed the tree and reported all 570 files as
empty. And the marker filter must be dropped, or the 13 `live` files read as holes; a second attempt
counted 22.

## Functional Requirements

| # | FR | Actor | Action | Outcome |
|---|-----|-------|--------|---------|
| FR-1 | A file that contributes nothing is a failure | check | SHALL report every `tests/**/test_*.py` from which pytest would collect no test, naming the file and the reason (no `Test*` class, no module-level `test_*`, nothing at all) | The class of defect becomes impossible to reintroduce silently |
| FR-2 | The check agrees with pytest | check | SHALL be validated against a real `--collect-only` run in its own test, so a divergence between the static rule and pytest's behaviour fails rather than passing quietly | A static approximation of someone else's collection rules is worth exactly as much as its agreement with them |
| FR-3 | A marker is not a hole | check | SHALL NOT report a file excluded only by a marker such as `live` | 13 files are excluded on purpose; reporting them would train the reader to ignore the output |
| FR-4 | The known holes are closed | repo | The three classes SHALL be renamed so their 24 tests run, and `R6`'s naming rule SHALL still hold for the new names | The tests that exist start counting |
| FR-5 | The misplaced test goes home | repo | `test_malformed_protocol_payload_emits_error_log` SHALL move from the LLM-logging file into `test_grpc_parser.py`, citing the `A-VAL-01` FR it proves | The single protector of the gRPC error path stops being findable only by accident |
| FR-6 | The nine stubs are filled, not deleted | repo | Each SHALL hold real tests for the module it is named after — the three parsers, the atom, the factory, the models and the tool — covering happy path, malformed input and the error contract | The gate reaches zero findings by the capability gaining coverage, never by the evidence being removed |
| FR-7 | The coverage is attributed | repo | The new tests SHALL carry `Proves: A-VAL-01 FR-n` tags, and any FR that is genuinely out of scope SHALL be deleted from `A-VAL-01`'s FR table | `check_fr_coverage.py A-VAL-01` stops reporting 0 of 5 on a delivered DAL-A capability |

## Non-Functional Requirements

| # | NFR | Threshold / Constraint |
|---|-----|----------------------|
| NFR-1 | Cheap enough for a commit gate | Static AST analysis, no pytest collection pass at gate time. Sub-second on 570 files, so it can sit in `quality.py quick` rather than only at `doc` |
| NFR-2 | Honest about its own approximation | The check SHALL read `python_classes` / `python_files` / `python_functions` from `pyproject.toml` rather than assuming pytest's defaults; if a value is set that it cannot honour, it SHALL fail loudly rather than guess. **[proof: meta — rule about tests, docs or the diff]** unless a config is actually set, in which case it is behavioural |
| NFR-3 | Zero tolerance, not a ratchet | The backlog is 12 files and 3 are fixed here. A ratchet would freeze the remaining 9 as acceptable, which is the opposite of the point — their fate is a decision, not a baseline |

## Architectural Decisions

| # | Decision | Rationale | Architectural Switch? |
|---|----------|-----------|----------------------|
| AD-1 | Static AST check, not a collection pass | A `--collect-only` run costs ~15-20s on this suite; a static check is sub-second and can therefore run in `quick` where it is seen every loop rather than once at `doc`. FR-2 buys back the risk by pinning the approximation against ground truth in the check's own test | No |
| AD-2 | The three renames land with the check, not before it | They are the check's first finding. Landing them separately would leave the gate green on arrival with nothing demonstrating it fires | No |
| AD-3 | The check's own tests use synthetic files, never the repo's state | A test asserting "the repo is clean" passes for as long as nobody breaks it and proves nothing about the rule. Synthetic fixtures for each of the three causes, plus one conforming file | No |

## The question that was open, and how it was decided

**What happens to the nine empty stubs?** Three answers were on the table: write the tests, delete
and file a ticket, or delete and say nothing. Decided by the user 2026-08-16: **write them, here.**

That is the only one that improves anything. Deleting removes the sole visible trace that a
mission-critical capability shipped untested; a separate ticket defers it and, on this repo's own
evidence, deferral is how `A-VAL-01` reached `✅` with 0 of 5 FRs proven in the first place.

## Delivery evidence: the gate, run against the tree it was written for

**Asked at CB-3: if there is no e2e, is there any real value?** Fair question, and synthetic
fixtures were not a good enough answer to it. So the check was run against a worktree at
`2d8582f0^` — the repo as it stood the morning this ticket was written:

```
Test files that collect NOTHING (12):
  test_kind_presets.py      class QARunnerKindIntegration, QARunnerSettingsOverrideIntegration …
  test_runner_events.py     class QARunnerEventCallback holds test methods but is not named Test*
  test_runner_telemetry.py  class QARunnerTelemetryFlush holds test methods but is not named Test*
  test_asyncapi_parser.py   the file defines nothing at all
  …8 more
```

**Exactly the twelve that were wrong, each with the correct cause.** Not a fixture built to pass —
the real tree, the real defect, found by the real check. For a gate, that IS the journey: a repo in
the bad state → the gate → the finding.

**And there is no e2e on purpose.** The repo's e2e tier is `sw` command journeys; `quality.py` is a
developer gate, and the two are separate tracks. An e2e here would be the same subprocess call from
a different directory, which `check_proof_tier.py` counts tiers precisely to make visible.

**The limit, stated rather than glossed.** The unit tests prove the rule, the integration test
proves the gate runs it and fails on a finding, and the run above proves it would have caught the
real thing. **Nothing proves the counterfactual** — that the gate prevents the next one. That is the
same boundary the closure contract draws between attribution and strength, and no test closes it.

## Sub-Feature Breakdown

**Single feature — no decomposition.** 7 FRs but one capability area, one new script, and one
package to cover. Decomposition triggers: >5 FRs fires; modules touched and external integrations
do not. Split by **commit boundary** instead, which is what the extra FRs actually need.

## Execution Order

**Fill first, gate last.** The alternative — gate first, with the nine carried as a temporary
exception — was rejected: an escape hatch introduced to make a gate land is exactly the mechanism
that calcifies, and this ticket exists because something calcified.

| Boundary | Delivers | Falsified by |
|---|---|---|
| **CB-1** | FR-4 renames + FR-5 move. 24 tests start running; the misplaced gRPC test lands in `test_grpc_parser.py`, filling one of the nine | the mutants already run: `llm.flush(db)` → `pass` kills 3, and the gRPC error path kills 1 from its new home |
| **CB-2** | FR-6 + FR-7: the remaining eight stubs filled, tests cited to `A-VAL-01` FRs, out-of-scope FRs deleted from its table | `check_fr_coverage.py A-VAL-01` exits 0; a mutant per parser — starting with `OpenAPIParser`'s `if "paths" not in parsed:`, which survives the whole suite today |
| **CB-3** | FR-1–FR-3: the check, registered in `quality.py`, zero-tolerance | its own synthetic fixtures (one file per cause, one conforming) prove it fires; the live-repo test then asserts zero findings, which CB-1 and CB-2 earned |

Known weakness carried forward, not silently: `test_no_flush_when_llm_is_not_collector` survives its
mutant because the `isinstance` guard is redundant with the surrounding `except Exception`. It is
recorded in CB-1's walkthrough rather than fixed here — the guard is `INT-US-16`'s territory and
removing either half of a redundant pair is how a property loses its last protector.

## Progress Tracker

| SF | Name | Depends On | Design | Impl Plan | Dev | Pre-Commit | Committed |
|----|------|-----------|--------|-----------|-----|------------|-----------|
| — | Single feature (CB-1 → CB-3) | — | ✅ | ✅ | ✅ | ✅ | ✅ |

## Session Handoff

**Current status**: **COMPLETE.** CB-1 `2d8582f0`, CB-2 `5aeac638`, CB-3 this commit.

| | |
|---|---|
| hidden tests recovered | **24**, across 3 files |
| empty stubs filled | **9**, all named after `sandbox/protocol` |
| `sandbox/protocol` coverage | 0 real exercise → **100%** (8 modules, 248 statements) |
| `check_fr_coverage A-VAL-01` | 0 of 5 → **5 of 5**, exit 0 |
| uncollectable test files | 12 → **0**, and now gated at `quick` |

**Next step**: none. The gate is registered at `quick`, `cb`, `sf` and `feature`, and the repo is
clean against it.
