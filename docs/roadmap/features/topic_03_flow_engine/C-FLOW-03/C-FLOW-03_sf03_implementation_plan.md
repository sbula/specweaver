# C-FLOW-03 SF-03 — Parallel Engine Hardening

**Status**: APPROVED · **FRs owned**: FR-5 — deferred artifact synthesis behind the JOIN wave
(recorded 2026-08-17 under `specweaver-dev` §3.2c, from `INT-US-18-MIG`) · **Depends on**: SF-02 ·
Design: [C-FLOW-03_design.md](C-FLOW-03_design.md) §Sub-Feature Breakdown → SF-03 · Feature ID 3.27

Proof and mutant: `tests/unit/core/flow/handlers/test_decompose.py` — skipping `_run_wave_n` fails it.

**FR-3 and FR-4 are NOT owned here, or anywhere.** Both were declared and never built; the rows are
deleted from the design and the work is `TECH-062`.

## Goal

Shared documentation steps run after the parallel runs (JOIN), and LLM calls are throttled per
provider across all of them.

## Where it plugs in

- **JOIN:** `GateType.JOIN` goes into the `GateType` enum in `src/specweaver/core/flow/models.py`;
  the `GateEvaluator` in `src/specweaver/core/flow/gates.py` must handle it. `fan_out()` pipelines
  do not talk to each other beyond `asyncio.gather()`, so a strict JOIN means either moving shared
  document writes to the orchestrator's DAG wave layer (Wave 0), or interpreting JOIN inside
  `fan_out()`. The orchestrator already handles topological waves, so scheduling step batches there
  is simpler.
- **Throttling:** the `asyncio.Semaphore` must span parallel tasks under `asyncio.gather()`.
  `factory.py` spawns several `gemini.py` instances per `RunContext`, so an instance-level semaphore
  inside `.generate()` cannot prevent global 429 timeouts. Options: a global `_PROVIDER_SEMAPHORES`
  lazy-locked dict, a class-variable semaphore in `LLMAdapter`, or an `AsyncRateLimiterAdapter` in
  `factory.py`. A decorator or singleton `get_semaphore(provider)` inside `generate()` bounds API
  access.

## Changes

1. **[MODIFY] `src/specweaver/core/flow/models.py`** — `GateType` gains `JOIN`, usable from YAML
   pipeline definitions for delayed execution.
2. **[NEW] `src/specweaver/infrastructure/llm/adapters/_rate_limit.py`** —
   `class AsyncRateLimiterAdapter(LLMAdapter)`:
   - global registry `_PROVIDER_SEMAPHORES: dict[str, asyncio.Semaphore]`;
   - `.generate()` and `.generate_stream()` wrap each call in `async with _PROVIDER_SEMAPHORES[self._wrapped.provider_name]:`;
   - `logger.debug` when a lock is awaited and acquired, per `run_id`; asyncio timeouts re-raised as
     clear `LLMAdapterError` messages naming the concurrent failure.
3. **[MODIFY] `src/specweaver/infrastructure/llm/factory.py`** — in `create_llm_adapter()`, wrap the
   base adapter: `adapter = AsyncRateLimiterAdapter(adapter)`. This bounds API traffic across all
   parallel Git sandbox sessions from `fan_out()`.
4. **[MODIFY] `src/specweaver/core/flow/_decompose.py`** — `OrchestrateComponentsHandler.execute()`:
   1. after `sub_pipelines` are built from the decomposition JSON, strip every `PipelineStep` with
      `gate.type == GateType.JOIN`;
   2. run the remaining components in parallel;
   3. once all parallel runs finish without critical failure, build and run a final sequential
      "Wave N" pipeline of the captured `JOIN` documentation steps;
   4. `logger.info` how many `JOIN` steps were stripped from `fan_out`, and when Wave N starts. A
      Wave N failure raises with "Post-execution Artifact Join synchronization failed."

## Tests

- **Unit:** `AsyncRateLimiterAdapter` blocks rapid consecutive `generate()` bursts across mocked
  concurrent calls.
- **Integration:** `OrchestrateComponentsHandler` runs `[GateType.JOIN]` artifacts only after all
  sibling `Orchestrator` elements resolve; execution-log order shows no overlap.

## Decisions (HITL, Phase 4)

- **`GateType.JOIN` execution — Option B.** `OrchestrateComponentsHandler` (with the DAG
  `TopologyGraph`) strips documentation steps and runs them sequentially after `fan_out` completes.
- **Global LLM throttling — Option A.** The factory wraps each adapter in
  `AsyncRateLimiterAdapter(adapter, limit)`, over one global `asyncio.Semaphore` pool keyed by
  provider name.

## As built

- `[x]` Dev Implementation.
- `[x]` Full Quality Gate passed.

**Since moved** (noted 2026-09-25): `_run_wave_n` lives in `src/specweaver/core/flow/handlers/decompose.py`.
