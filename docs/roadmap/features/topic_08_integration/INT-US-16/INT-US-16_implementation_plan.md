# INT-US-16 — Implementation Plan

**Status**: APPROVED (2026-08-16). Implemented 2026-08-16. · **FRs owned**: FR-1, FR-2, FR-3, FR-4
(all of them — single feature, no decomposition). **CB-1 owns FR-1 and FR-3; CB-2 owns FR-2 and
FR-4.** · Preconditions: `check_story_preconditions.py INT-US-16` exits 0 · Design:
[INT-US-16_design.md](INT-US-16_design.md)

## Goal

Prove the US-16 journey once, end to end, and fix the defects that journey exposes. Nothing else in
US-16 is touched: the four add-on groups (dynamic routing, friction analytics, OpenTelemetry
tracing, REST telemetry API) stay unbuilt.

One source module gains a guard and a cost pass-through; the rest is tests. The rigour that matters
is **falsifiability**, not volume: each boundary is done when its mutants are killed.

## Where it plugs in

| Fact | Where |
|---|---|
| `TelemetryCollector` wraps the adapter when a project is given; again for the routed path | `factory.py:84-92`, `router.py:120` |
| `PipelineRunner._flush_telemetry` drains it in a `finally` | `runner.py:300-314` → `core/flow/engine/telemetry.py:20-35` |
| Surfaces passing `telemetry_project`: `sw run`, `sw resume`, `sw implement`, `sw review` ×2, drift | `core/flow/interfaces/cli.py:96,289`, `workflows/implementation/interfaces/cli.py:219`, `workflows/review/interfaces/cli.py:195,293`, `cli_drift.py:97` |
| `sw usage` / `sw costs` render real aggregates | `infrastructure/llm/interfaces/cli.py:127` |
| `telemetry_project=None` skips the collector wrap; `# type: ignore[arg-type]` beside it | `cli.py:216-219` |
| No active project: `load_settings(db, None)` raises before `create_llm_adapter` | `settings_loader.py:179` |
| `scripted_world` patches `create_llm_adapter` to a bare `ScriptedLLM` | `tests/scripted_llm.py:80-97` |

**R-1 — The recipe for a real-factory e2e exists.**
`tests/e2e/capabilities/infrastructure/test_telemetry_e2e.py:165-183` sets
`@patch.dict(os.environ, {"GEMINI_API_KEY": "e2e-key"})` and patches
`specweaver.infrastructure.llm.factory._get_adapter_class` to a local `FakeGeminiAdapter`
(`provider_name = "gemini"`, `api_key_env_var`, `available() -> True`). The **real**
`create_llm_adapter` then runs, including the `if telemetry_project:` branch, and the test asserts
`isinstance(adapter, TelemetryCollector)`. This is the patch point `AD-2` mandates.

**R-2 — Never `scripted_world`.** It returns `(settings_mock(), llm, MagicMock())` where `llm` is a
bare `ScriptedLLM`. `context.model.llm` would then not be a `TelemetryCollector`, `flush_telemetry`
would return at its `isinstance` guard, and the test would pass having proven nothing.

**R-3 — The existing implement CLI tests run with NO active project.**
`tests/unit/workflows/implementation/interfaces/test_implementation_cli.py:73-150` invokes
`["implement", str(spec), "--project", str(project)]` with no `sw use`, asserting only
`result.exit_code == 0` plus file existence. They patch **both** `create_llm_adapter` *and*
`settings_loader.load_settings`; without the second they would exit 1 on `Project 'None' not
found`. Verify rather than assume, and give `test_cli_implement_isolation.py` the same look.

**R-4 — `_COLLECTABLE` is a known-passing generated pair.** Same file, line 55: `def greet(): pass`
plus a test that calls it. The implement pipeline's `run_tests` step runs pytest on generated code,
and on failure loops back to `generate_code` (`max_retries=2`), leaving the run non-completed and
exit 1. Scripting the fake to return this pair is how the journey reaches a completed run.

**R-5 — House style for this warning exists.** `sw usage` prints `[yellow]No active
project.[/yellow] Use [bold]sw use <name>[/bold] or pass [bold]--all[/bold].`
(`infrastructure/llm/interfaces/cli.py:150-156`). FR-2's wording matches it.

**R-6 — Two unrelated things are called "telemetry".**
`docs/dev_guides/agent_memory_state_tracking.md:198-205` describes a "fail-safe telemetry sweep" —
**handover context** (`files_touched`, `error_message`, 8KB budget), not LLM usage. This plan means
LLM token/cost telemetry throughout.

**R-7 — There is no telemetry opt-out setting.** Grepped `core/config/settings.py` and all of
`src/`: no `telemetry_enabled` / `disable_telemetry`. FR-2's message names the remedy and does not
imply a toggle.

**R-8 — No command passes `cost_overrides` into `create_llm_adapter`.**
`core/flow/interfaces/cli.py:96`, `workflows/implementation/…/cli.py:219`,
`workflows/review/…/cli.py:195,293` all omit it; the only reader of `get_cost_overrides()` in
`src/` is `sw costs` itself, for display (`llm/interfaces/cli.py:43`). Every run prices from the
built-in table — or **`0.0`** for a model absent from it, buried in a `logger.warning`.

## Changes

Order: CB-1 pins the wiring that already works before CB-2 changes anything around it. No red
crosses a commit boundary (`ADR-003`); a red carried across a commit is what gets silenced with a
skip, the shape `check_proof_tier.py` exists to catch.

| Boundary | Delivers | How it is falsified |
|---|---|---|
| **CB-1** | **FR-1** token journey e2e + **FR-3** seam test and its siblings (no-project refusal, failed-run spend, hostile project name) | Expected to pass on first run — the wiring genuinely works. **Exit condition is killing the mutant**, as in `TECH-017`: a containment test that passed immediately proved nothing, because the function it covered returned `{}` for every caller, and only the mutant said so |
| **CB-2** | **FR-4** cost journey e2e, written **red**, then two fixes: `sw implement` passing `cost_overrides`, and **FR-2**'s message | Ordinary red → green inside the boundary, then M-3 |

The second fix is in scope by `AD-4`'s principle — the contract carries the defect its journey
exposes rather than deferring it to a ticket. Approved by the user 2026-08-16.

### CB-1 — the wiring that already works, pinned

`tests/integration/workflows/implementation/test_implement_collector_wiring.py` [NEW]:

1. **FR-3** — drive the real `implement` command and capture the `RunContext` it builds (spy on
   `PipelineRunner`); assert `isinstance(context.model.llm, TelemetryCollector)`. Never construct a
   `RunContext` by hand (Q5).
2. **Boundary** — with **no** active project the command stops before any adapter exists.
3. **Degradation** — a run that ends **non-completed** still records what it spent, because
   `_flush_telemetry` sits in a `finally` (`runner.py:314`).
4. **Hostile** — a project name carrying SQL metacharacters round-trips through write and read
   without executing, pinning parameter binding at *our* boundary.

Plus the FR-1 e2e: `init` → `use` → `implement` → `sw usage` shows that run's tokens.

**Done when** M-2 is KILLED:

| Mutant | File | Neutralise | Must kill |
|---|---|---|---|
| M-2 | `infrastructure/llm/factory.py` | `if telemetry_project:` → `if False:` | FR-3's integration test |

A green that survives M-2 asserts on something other than the seam; the boundary is not done.

### CB-2 — the money journey, red first, then two fixes

1. `tests/e2e/interfaces/test_implement_usage_journey_e2e.py` — **FR-4**:
   - `sw init --path tmp_path` + `sw use`, so an active project exists. DB isolation from the
     global `_isolate_env` only (see Tests).
   - `sw costs set <fake-model> <in-rate> <out-rate>` (`AD-6`).
   - Patch `factory._get_adapter_class` → a fake returning `_COLLECTABLE`-shaped payloads (R-1,
     R-4) with a `TokenUsage` the assertion names exactly. **Never patch `create_llm_adapter`**
     (R-2), never `scripted_world`.
   - `sw implement <spec> --project <path>`, then `sw usage`.
   - Assert the fake model name, the exact token count, and a **non-zero** USD figure.
   - **Red on the cost**, because `sw costs set` reaches no run (R-8).
2. `workflows/implementation/interfaces/cli.py` — **FR-2's message.** Resolve the active project as
   today (line 216, unchanged); if falsy, print an error in the `sw usage` house style (R-5) naming
   the condition and the remedy `sw use <name>`, and exit 1. Exit code unchanged (NFR-3); only
   what the user reads changes. FR-2 originally said "warn, then continue the run unchanged" —
   replaced because there is no run to continue (`AD-5`), established by running it in CB-1.
3. `workflows/implementation/interfaces/cli.py` — **cost-override pass-through.** Load the
   overrides the way `sw costs` does (`LlmRepository.get_cost_overrides()`,
   `llm/interfaces/cli.py:43`) and hand them to `create_llm_adapter(..., cost_overrides=...)`, the
   keyword it has always accepted (`factory.py:43`).
4. R-3's existing tests pass unchanged — verify, including `test_cli_implement_isolation.py`. **If
   one asserts on full output, give that test an active project rather than softening the
   warning.**
5. One line in `docs/user_guides/1_installation_and_setup.md` where `sw use` is introduced: LLM cost
   is recorded per active project, so a run without one is not recorded. There is no telemetry
   opt-out setting (R-7). Written in this boundary's pre-commit documentation phase.

**Done when** M-1 and M-3 are KILLED:

| Mutant | File | Neutralise | Must kill |
|---|---|---|---|
| M-1 | `core/flow/engine/telemetry.py` | `llm.flush(db)` → `pass` | FR-1's e2e |
| M-3 | `workflows/implementation/interfaces/cli.py` | delete the warning branch | FR-2's integration test |

## Tests

| Tier | Class | Case |
|---|---|---|
| E2E | `TestImplementRecordsUsage` (FR-1; FR-4 adds the cost) | `init` → `use` → `costs set` → `implement` → `sw usage`: model, exact tokens, non-zero USD |
| Integration | `TestImplementInstallsTelemetryCollector` (FR-3) | collector on the `RunContext` the command builds; no project → stops before any adapter |
| Integration | `TestImplementWarnsWithoutActiveProject` (FR-2) | no active project → the warning appears, through `tests/rendering.py::shows()` (NFR-4) → exit code unchanged |

Command: `python scripts/tests.py cb INT-US-16` — **no `--kind`, no `--all`**.

> [!NOTE]
> `tests.py matrix` carries an `INTEGRATION story (INT-US-NN)` profile whose `cb` column is already
> `integration: all` and `e2e: domain` — the two tiers this contract writes. `--kind` belongs to
> TECH tickets only; the `CLAUDE.md` lesson about `cb` selecting the unit tier alone is the
> **TECH** profile's behaviour, not this one. This profile runs **no unit tier at all**, consistent
> with writing no unit tests: every FR crosses a module boundary.
>
> **`e2e: domain` makes the e2e's location load-bearing.** Confirm the run selects the new file — a
> tier reporting `selected NO tests` is a failure, not a pass. If the domain scoping misses it, move
> the file rather than reaching for `--all`, which would hide the mis-placement.

Rules:

- **Naming** (`R6`/`R7`): classes name the symbol or behaviour under test. Mark the e2e
  `@pytest.mark.e2e` per `tests/CLAUDE.md`.
- **Assertions** (NFR-5): `sw usage` prints several numeric columns, so a bare substring match can
  pass on the wrong one. Give the fake a distinctive token count that cannot collide with a cost, a
  duration or a call count, and assert through `tests/rendering.py::shows()`.
- **DB isolation**: use the global `tests/e2e/conftest.py::_isolate_env` (`autouse=True` for the
  tier; sets `SPECWEAVER_DATA_DIR`, `core/config/paths.py:32-37`), so the command resolves its own
  DB at `tmp_path/.specweaver-test/specweaver.db`. **Do not copy `test_cli_decentralized_e2e.py`**:
  its `autouse` fixture `_patch_config_path` (lines 32-49) monkeypatches
  `specweaver.interfaces.cli._core.get_db` to a hand-built `Database(tmp_path/"specweaver.db")`,
  taking DB resolution *out* of the journey. Verified by probe: under `_isolate_env` alone, the
  only `*.db` under `tmp_path` is that one, and a hand-seeded `sqlite3` INSERT into
  `tmp_path/specweaver.db` fails with `no such table`.

## Decisions (audit)

| # | Question | Chosen | Why |
|---|---|---|---|
| Q5 | Build a `RunContext` by hand for FR-3? | **No** — spy on `PipelineRunner` | A constructed context proves nothing about what the command builds |
| Q6 | `FakeGeminiAdapter` lives inside another test module — import it? | **Duplicate it locally**, with a comment naming `test_telemetry_e2e.py:52` as the original | A test-to-test import couples two e2e modules through an undeclared dependency; promote to a shared helper when a **third** caller appears |
| Q9 | Re-prove flush failure (NFR-1)? | **No** | `TelemetryCollector.flush` documents *"Never raises — telemetry failures are logged, not propagated"* (`collector.py:159-167`); `tests/unit/infrastructure/llm/test_collector.py` covers it at unit tier |

Also recorded: `FR-2` adds no import — `_core` is already imported at `cli.py:17`; no cycle is
reachable.

## Risks

| # | Risk | Mitigation |
|---|---|---|
| R-1 | The journey cannot reach a completed run because generated code fails its own test | Script the fake to return `_COLLECTABLE` (R-4). If the run still ends non-completed, assert on `sw usage` alone — the flush is in a `finally`. State which was used |
| R-2 | `FakeGeminiAdapter` reuse means a test-to-test import | Q6 |
| R-3 | FR-3's `RunContext` spy couples the test to `PipelineRunner`'s construction | Accept: that coupling **is** the seam under test. A weaker assertion (that `create_llm_adapter` was called with a non-None project) proves the call and not the wiring; Red/Blue rejected one vacuous phrasing of FR-3 |
| R-4 | FR-2's warning becomes noise in the existing tests' output | They assert exit codes only; verify in CB-2 |

## Out of scope

- Extracting FR-2's guard into a shared helper for `sw run` / `sw review` / drift — see the
  duplication baseline below.
- Any telemetry opt-out setting (R-7). A product decision, not this contract's.
- The other five LLM-calling surfaces' journeys (`AD-3`).
- The roadmap's `✅ Step 9a: Token Tracking` line — noted in the design.

## As built (2026-08-16)

CB-1 `c8be134c`, CB-2 `f7a98a4c`.

- FR-2 uses the existing `_core._require_active_project()`, as every other `sw` command does.
- FR-2 and FR-4 were extended to `sw review`, both call sites — same two defects.
- M-1 and M-2 are durable campaigns in [INT-US-16_mutants.json](INT-US-16_mutants.json).

**Duplication baseline.** With `sw review` fixed too, the same block stands in `sw implement` and
twice in `sw review`. **Three homes for a shared helper were tried and `tach` refused all three** —
`interfaces/cli` may not depend on `infrastructure/llm`; `infrastructure/llm` may not depend on
`core.config.bootstrap`; `workflows/*/interfaces` may not depend on `llm.interfaces`. Each needed
new module edges, an architectural switch a duplication finding does not justify. What could move
legally did: `factory.build_adapter_for_project` holds the three lines that carried the FR-4
defect, exposed in `tach.toml`. What remains repeated — the import block, the
`_require_active_project()` call and two `except` clauses turning errors into console text — is
**presentation, which the boundaries keep per-command**. Baselined 2026-08-16 with the count
re-frozen at 122; the call sites carry comments saying why. Revisit at a fourth caller.

**Since moved** (checked 2026-09-25): the e2e lives at
`tests/e2e/capabilities/interfaces/test_implement_usage_journey_e2e.py`.
