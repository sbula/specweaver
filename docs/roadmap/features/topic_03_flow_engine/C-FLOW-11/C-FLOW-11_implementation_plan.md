# C-FLOW-11 — Graduated Autonomy: Plan

**FRs owned**: FR-1, FR-2, FR-3, FR-4, FR-5 · Design: [C-FLOW-11_design.md](C-FLOW-11_design.md)
(proof and mutants tabulated there)

## Where it plugs in

Three new pieces, all additive.

- `core/flow/engine/autonomy.py` — `ExecutionMode` and `resolve_execution_mode`, which mirrors
  `resolve_should_isolate` deliberately: same tri-state shape, same defensive reads, same
  composition-root policy. The author states intent; the run's DAL decides whether it stands.
- `core/flow/engine/work_unit.py` — `WorkUnit`, `WorkUnitResult`, the `AgentRuntime` protocol and
  `InProcessAgentRuntime`. The runtime drives `context.model.llm`, which the factory has already
  wrapped in a `TelemetryCollector`, so the run's spend ceiling applies with no extra wiring.
- `AutonomySettings` carries the policy; `PipelineStep.mode` carries the intent;
  `apply_isolation_policy` freezes the policy onto the context.

## Changes

Tests first, red before the code, per `ADR-005`.

1. `test_autonomy_dial.py` — the resolution rules, each with its control: the threshold works in both
   directions, a step may opt out of an agentic default, a typo is refused.
2. `autonomy.py`.
3. `test_work_unit.py` — iteration, both bounds, and the protocol's replaceability.
4. `work_unit.py`.
5. `test_autonomy_settings.py` — the dial is reachable from YAML and from config.
6. `AutonomySettings`, `PipelineStep.mode`.
7. `test_autonomy_policy_seam.py` — the policy reaches the context. Without it the setting is a
   comment, and the dial's own tests cannot tell: they build the policy by hand.
8. Seed in `apply_isolation_policy`.
9. Mutation pass, seven mutants.

## Non-Goals

- A second `AgentRuntime` implementation.
- Converting any shipped pipeline step to `agentic`. Turning the dial is a separate, deliberate act.
