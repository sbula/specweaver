# Implementation Plan: US-16 Base Integration Contract — AI Operations & Cost Routing

- **Feature ID**: INT-US-16
- **Design Document**: docs/roadmap/features/topic_08_integration/INT-US-16/INT-US-16_design.md
- **Implementation Plan**: docs/roadmap/features/topic_08_integration/INT-US-16/INT-US-16_implementation_plan.md
- **Status**: APPROVED (2026-08-16)

**FRs owned: FR-1, FR-2, FR-3, FR-4** (all of them — single feature, no decomposition).
**CB-1 owns FR-1 and FR-3; CB-2 owns FR-2 and FR-4.**
Preconditions: `check_story_preconditions.py INT-US-16` exits 0. Design `APPROVED` 2026-08-16.

> **Proportionality.** One source module gains a guard and a warning; the rest is three tests. The
> rigour that matters here is **falsifiability**, not volume — see the Execution Order correction
> below, which is the single most important thing in this plan.

## Scope

Prove the US-16 journey once, end to end, and fix the one defect that journey exposes. Nothing
else in US-16 is touched: the four add-on groups (dynamic routing, friction analytics,
OpenTelemetry tracing, REST telemetry API) are unbuilt and stay unbuilt.

## Research Notes

Findings from Phase 0 that constrain the plan. Every one was read, not assumed.

**R-1 — The recipe for a real-factory e2e already exists and is proven.**
`tests/e2e/capabilities/infrastructure/test_telemetry_e2e.py:165-183` sets
`@patch.dict(os.environ, {"GEMINI_API_KEY": "e2e-key"})` and patches
`specweaver.infrastructure.llm.factory._get_adapter_class` to a local `FakeGeminiAdapter`
(`provider_name = "gemini"`, `api_key_env_var`, `available() -> True`). The **real**
`create_llm_adapter` then runs, including the `if telemetry_project:` branch, and the test asserts
`isinstance(adapter, TelemetryCollector)`. This is the patch point `AD-2` mandates.

**R-2 — `scripted_world` must not be used, and the reason is mechanical.**
`tests/scripted_llm.py:80-97` patches `create_llm_adapter` itself, returning
`(settings_mock(), llm, MagicMock())` where `llm` is a bare `ScriptedLLM`. `context.model.llm`
would then not be a `TelemetryCollector`, `flush_telemetry` would return at its `isinstance` guard,
and the test would pass having proven nothing.

**R-3 — The existing implement CLI tests run with NO active project, and get away with it.**
`tests/unit/workflows/implementation/interfaces/test_implementation_cli.py:73-150` invokes
`["implement", str(spec), "--project", str(project)]` with no `sw use`, asserting only
`result.exit_code == 0` plus file existence. They patch **both** `create_llm_adapter` *and*
`settings_loader.load_settings`, and it is the second patch that matters: without it the command
would exit 1 on `Project 'None' not found`. So FR-2's message change cannot reach them — but verify
rather than assume, and give the same look to `test_cli_implement_isolation.py`.

**R-4 — `_COLLECTABLE` is a known-passing generated pair.**
Same file, line 55: `def greet(): pass` plus a test that calls it. The implement pipeline's
`run_tests` step actually runs pytest on generated code, and on failure loops back to
`generate_code` (`max_retries=2`) leaving the run non-completed and exit 1. Scripting the fake
adapter to return this pair is how the journey e2e reaches a completed run.

**R-5 — House style for exactly this warning already exists.**
`sw usage` prints `[yellow]No active project.[/yellow] Use [bold]sw use <name>[/bold] or pass
[bold]--all[/bold].` (`infrastructure/llm/interfaces/cli.py:150-156`). FR-2's wording should match
this, not invent a second dialect for the same condition.

**R-6 — Two unrelated things are both called "telemetry".**
`docs/dev_guides/agent_memory_state_tracking.md:198-205` describes a "fail-safe telemetry sweep" —
that is **handover context** (`files_touched`, `error_message`, 8KB budget), not LLM usage. A fresh
agent will conflate them. This plan means LLM token/cost telemetry throughout.

**R-7 — There is no telemetry opt-out setting.** Grepped `core/config/settings.py` and all of
`src/`: no `telemetry_enabled` / `disable_telemetry` of any kind. The clause that once followed —
*"the no-active-project path is today's accidental opt-out"* — was **wrong and is withdrawn**: that
path does not run at all (`AD-5`). The grep result stands on its own: there is no supported way to
turn recording off, so FR-2's message should name the remedy and not imply a toggle.

## Execution Order — CORRECTED from the design

> [!CAUTION]
> **The design's Execution Order was wrong and is superseded here.** It proposed *"CB-1: tests
> written red; CB-2: the fix, turning them green"* — which plans a **red at a commit boundary**.
> `ADR-003` and the dev skill both forbid that: the test is authored before the wiring *within* its
> boundary and turned green *there*. A red carried across a commit is what gets silenced with a
> skip, which is the shape `check_proof_tier.py` exists to catch.

There is a second, subtler problem the correction has to solve.

**FR-1's e2e will pass the first time it is run.** Phase 0 found the machinery complete: with an
active project set, the collector is installed, the runner flushes in a `finally`, and
`get_usage_summary` reads it back. So the journey test cannot fail for the right reason by being
written first — there is nothing broken for it to catch.

That does not make it worthless; it makes **the mutant its exit condition rather than the red**.
This is `TECH-017`'s lesson exactly: a containment test that passed immediately proved nothing
because the function it covered returned `{}` for every caller, and only the mutant said so.

> [!CAUTION]
> **Redrawn again 2026-08-16, during CB-1's Phase 1 — and this time in the honest direction.**
> The premise above ("FR-1 will pass on first run") turned out to be **false**. FR-1 prices the run
> via `sw costs set` (`AD-6`), and **no command passes `cost_overrides` into `create_llm_adapter`**:
> `core/flow/interfaces/cli.py:96`, `workflows/implementation/…/cli.py:219`,
> `workflows/review/…/cli.py:195,293` all omit it, and the only reader of `get_cost_overrides()` in
> `src/` is `sw costs` itself, for display (`llm/interfaces/cli.py:43`). A user sets a price, `sw
> costs` echoes it, and every run prices from the built-in table — or **`0.0`** for a model absent
> from it, with the fact buried in a `logger.warning`.
>
> That is the same failure shape this contract exists to catch: a configured thing that appears to
> work and is never consumed. **So FR-1 goes red for the right reason after all**, and the boundary
> becomes an ordinary red → green rather than a mutant-only proof.

| Boundary | Delivers | How it is falsified |
|---|---|---|
| **CB-1** | **FR-1** token journey e2e + **FR-3** seam test and its siblings (no-project refusal, failed-run spend, hostile project name) | Expected to pass on first run — the wiring genuinely works. **Exit condition is killing M-1 and M-2** |
| **CB-2** | **FR-4** cost journey e2e, written **red**, then two fixes: `sw implement` passing `cost_overrides`, and **FR-2**'s message | Ordinary red → green inside the boundary, then M-3 |

CB-1 first because it pins the wiring that already works before CB-2 changes anything around it.

**The second fix is in scope by `AD-4`'s own principle** — this contract carries the defect its
journey exposes, rather than deferring it to a ticket that would leave FR-1 red across a boundary
it does not own. Approved by the user 2026-08-16.

## Commit boundary CB-1 — the wiring that already works, pinned

**Delivers** — one file, `tests/integration/workflows/implementation/test_implement_collector_wiring.py` [NEW]:

1. **FR-3** — drives the real `implement` command and captures the `RunContext` the command builds
   (spy on `PipelineRunner`), asserting `isinstance(context.model.llm, TelemetryCollector)`.
   Never construct a `RunContext` by hand (plan Q5).
2. **Boundary** — with **no** active project it is *not* a `TelemetryCollector`. This pins today's
   silent no-op before CB-2 changes anything around it, so CB-2's red is unambiguous.
3. **Degradation** — a run that ends **non-completed** still records what it spent, because
   `_flush_telemetry` sits in a `finally` (`runner.py:314`).
4. **Hostile** — a project name carrying SQL metacharacters round-trips through write and read
   without executing, pinning parameter binding at *our* boundary.

**Tests**: `python scripts/tests.py cb INT-US-16` — **no `--kind`, no `--all`**.

> [!NOTE]
> **Checked, because the obvious answer was wrong.** `tests.py matrix` carries an `INTEGRATION
> story (INT-US-NN)` profile whose `cb` column is already `integration: all` and `e2e: domain` —
> the two tiers this boundary writes. `--kind` belongs to TECH tickets only, and the `CLAUDE.md`
> lesson about `cb` selecting the unit tier alone is the **TECH** profile's behaviour, not this
> one. The same profile runs **no unit tier at all**, which is consistent with this plan writing no
> unit tests: all three FRs cross a module boundary, so none is a unit-tier claim.
>
> **`e2e: domain` makes the e2e's location load-bearing.** Confirm the run actually selects the new
> file — a tier reporting `selected NO tests` is a failure, not a pass. If the domain scoping misses
> it, move the file rather than reaching for `--all`, which would hide the mis-placement.

**Test naming** (`R6`/`R7`): classes name the symbol or behaviour under test —
`TestImplementRecordsUsage` for FR-1, `TestImplementInstallsTelemetryCollector` for FR-3,
`TestImplementWarnsWithoutActiveProject` for FR-2. Mark the e2e `@pytest.mark.e2e` per
`tests/CLAUDE.md`.

**Assertion hygiene** (NFR-5): `sw usage` prints several numeric columns, so a bare substring match
can pass on the wrong one. Give the fake a token count that cannot collide with a cost, a duration
or a call count — a distinctive value, not a round one — and assert through
`tests/rendering.py::shows()`.

**Test DB isolation — corrected, and the correction matters.** An earlier draft of this plan named
`test_cli_decentralized_e2e.py` as the reference. **Do not copy it.** That module carries its own
`autouse` fixture `_patch_config_path` (lines 32-49) which monkeypatches
`specweaver.interfaces.cli._core.get_db` to a hand-built `Database(tmp_path/"specweaver.db")` —
taking DB resolution *out* of the journey, which is precisely what an end-to-end test must leave in.

Use the global fixture instead: `tests/e2e/conftest.py::_isolate_env` is `autouse=True` for the
whole tier and sets `SPECWEAVER_DATA_DIR` (`core/config/paths.py:32-37`), so the command resolves
its own DB and it lands at `tmp_path/.specweaver-test/specweaver.db`. **Verified by probe, not by
reading**: under `_isolate_env` alone, the only `*.db` under `tmp_path` is that one, and a
hand-seeded `sqlite3` INSERT into `tmp_path/specweaver.db` fails with `no such table` — which is
why the older test needs its monkeypatch and why this one must not have it.

**Done when** M-2 is KILLED:

| Mutant | File | Neutralise | Must kill |
|---|---|---|---|
| M-2 | `infrastructure/llm/factory.py` | `if telemetry_project:` → `if False:` | FR-3's integration test |

These four tests are expected to pass on first run — the collector wiring genuinely works, which is
what Phase 0 established. So the mutant, not the red, is the exit condition: a green that survives
M-2 means the test asserts on something other than the seam, and the boundary is not done.
M-1 and M-3 belong to CB-2, where the code they neutralise is written.

## Commit boundary CB-2 — the journey, red first, then two fixes

**Delivers**

1. `tests/e2e/interfaces/test_implement_usage_journey_e2e.py` — **FR-4**, added to the file CB-1
   created. Sequence, as pseudocode:
   - `sw init --path tmp_path` + `sw use`, so an active project exists. DB isolation comes from the
     global `_isolate_env` only — see the corrected note below.
   - `sw costs set <fake-model> <in-rate> <out-rate>` (`AD-6`).
   - Patch `factory._get_adapter_class` → a fake returning `_COLLECTABLE`-shaped payloads (R-1,
     R-4) with a `TokenUsage` the assertion names exactly. **Never patch `create_llm_adapter`**
     (R-2), never `scripted_world`.
   - `sw implement <spec> --project <path>`, then `sw usage`.
   - Assert the fake model name, the exact token count, and a **non-zero** USD figure.
   - **It goes red on the cost**, because `sw costs set` reaches no run today.
2. `workflows/implementation/interfaces/cli.py` — **FR-2's message.** Ordered checks, not code:
   resolve the active project as today (line 216, unchanged); if it is falsy, print an error in the
   `sw usage` house style (R-5) naming the condition and the remedy `sw use <name>`, and exit 1 —
   which is what happens today anyway, only via `load_settings` raising `Project 'None' not found`.
   Exit code unchanged (NFR-3); the change is what the user reads.

   > [!CAUTION]
   > **Amended 2026-08-16 — the original FR-2 said "warn, then continue the run unchanged".**
   > There is no run to continue: `load_settings(db, None)` raises before `create_llm_adapter` is
   > reached (`settings_loader.py:179`), so no adapter is built and `PipelineRunner` is never
   > constructed. Established by running it in CB-1, not by reading. See `AD-5`.
3. `workflows/implementation/interfaces/cli.py` — **the cost-override pass-through.** Load the
   overrides the way `sw costs` already does (`LlmRepository.get_cost_overrides()`,
   `llm/interfaces/cli.py:43`) and hand them to `create_llm_adapter(..., cost_overrides=...)`, the
   keyword it has always accepted (`factory.py:43`) and no command has ever supplied.

**Tests**: FR-1's e2e above, plus an FR-2 integration test in CB-1's file — no active project → the
warning appears (through `tests/rendering.py::shows()` per NFR-4, because Rich soft-wraps at
`COLUMNS`) → exit code unchanged from today.

**Done when** M-1 and M-3 are KILLED:

| Mutant | File | Neutralise | Must kill |
|---|---|---|---|
| M-1 | `core/flow/engine/telemetry.py` | `llm.flush(db)` → `pass` | FR-1's e2e |
| M-3 | `workflows/implementation/interfaces/cli.py` | delete the warning branch | FR-2's integration test |

**Also in this boundary**:

- Confirm R-3's existing tests still pass unchanged. They assert only exit codes and file
  existence, so the new warning in their captured output should be inert — but that is a claim to
  verify, not to assume. `test_cli_implement_isolation.py` gets the same look. **If one does assert
  on full output, give that test an active project rather than softening the warning.**
- One line in `docs/user_guides/1_installation_and_setup.md` where `sw use` is introduced: LLM cost
  is recorded per active project, so a run without one is not recorded. This is the user-facing
  half of `AD-5` — there is no telemetry opt-out setting (R-7), so the only way a user turns
  recording off today is by forgetting `sw use`. Written during this boundary's pre-commit
  documentation phase.

## Risks

| # | Risk | Mitigation |
|---|---|---|
| R-1 | The journey e2e cannot reach a completed run because generated code fails its own test | Script the fake to return `_COLLECTABLE` (R-4). If the run still ends non-completed, assert on `sw usage` alone — the flush is in a `finally`, so telemetry is recorded either way. State which was used in the walkthrough |
| R-2 | `FakeGeminiAdapter` lives inside another test module, so reuse means a test-to-test import | **Decided (Q6): duplicate it locally, with a comment naming `test_telemetry_e2e.py:52` as the original.** A test-to-test import couples two e2e modules through an undeclared dependency; promotion to a shared helper is right the moment a **third** caller appears, and not before |
| R-3 | FR-3's `RunContext` spy couples the test to `PipelineRunner`'s construction | Accept: that coupling **is** the seam under test. A weaker assertion (that `create_llm_adapter` was called with a non-None project) proves the call and not the wiring, and Red/Blue already rejected one vacuous phrasing of FR-3 |
| R-4 | FR-2's warning becomes noise in the existing tests' output | R-3 says they assert exit codes only; verify in CB-2 rather than assume |

## The duplication baseline, and why it is a baseline

CB-2 extended FR-2 and FR-4 to `sw review`, which made the duplication gate object: the same block
stands in `sw implement` and twice in `sw review`. **Three homes for a shared helper were tried and
`tach` refused all three** — `interfaces/cli` may not depend on `infrastructure/llm`;
`infrastructure/llm` may not depend on `core.config.bootstrap`; `workflows/*/interfaces` may not
depend on `llm.interfaces`. Each would have needed new module edges, which is an architectural
switch and not something a duplication finding justifies.

What *could* move legally did: `factory.build_adapter_for_project` now holds the three lines that
carried the FR-4 defect, exposed in `tach.toml`. What remains repeated is the import block, the
`_require_active_project()` call and two `except` clauses turning errors into console text —
**presentation, which the boundaries deliberately keep per-command**. Baselined 2026-08-16 with the
count re-frozen at 122; the call sites carry comments saying why.

If a fourth caller appears, revisit — three is where the architecture and the detector disagree,
and four is where the disagreement is worth resolving with a module edge.

## Recorded so they are not re-asked (Phase 4, Q9)

- **Flush failure.** `NFR-1` says swallow-and-log. `TelemetryCollector.flush` already documents
  *"Never raises — telemetry failures are logged, not propagated"* (`collector.py:159-167`) and
  `tests/unit/infrastructure/llm/test_collector.py` covers it at unit tier. **Do not re-prove it.**
- **Import chains.** `FR-2` adds no import — `_core` is already imported at `cli.py:17`. No cycle is
  reachable from this change.
- **Two things are called "telemetry" in this repo** (R-6). The handover sweep in
  `agent_memory_state_tracking.md` is a different mechanism. Everything here means LLM token/cost.

## Out of scope

- Extracting FR-2's guard into a shared helper for `sw run` / `sw review` / drift. One caller is
  not a pattern; the design's ROI table records it as a later candidate.
- Any telemetry opt-out setting (R-7). Adding one is a product decision, not this contract's.
- The other five LLM-calling surfaces' journeys (`AD-3`).
- The roadmap's `✅ Step 9a: Token Tracking` line, a legacy prose label with no capability ID that
  no gate can resolve. Noted in the design; fixing the registry is not this plan's business.
