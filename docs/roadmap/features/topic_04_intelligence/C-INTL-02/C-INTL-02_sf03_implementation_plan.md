# C-INTL-02 SF-03 — The Pre-Fetch Assembler (Flow Engine)

**Status**: APPROVED · **Feature ID**: 3.32c · **FRs owned**: FR-3, FR-4 · **Depends on**: SF-02 ·
Design: [C-INTL-02_design.md](C-INTL-02_design.md) §Sub-features → SF-03

## Goal

A lazy-loading Pre-Fetch Assembler in the Flow engine. It reads the MCP resources a boundary
declares, runs `MCPAtom` to fetch them over IPC, and passes the text to the `PromptBuilder`, so the
LLM gets the context with no tool-call latency.

## Where it plugs in

| Fact | Where |
|---|---|
| `flow` may not invoke `MCPAtom` yet. `flow` is `async_ready: true`; `MCPAtom` is `async_ready: false` → the handler must run it off the event loop. | `src/specweaver/core/flow/context.yaml` |
| `RunContext.topology` is a read-only `TopologyContext` record; it drops the `mcp_servers` defined on `TopologyNode`. | `src/specweaver/assurance/graph/topology.py` |

## Changes

1. **Topology bounds**
   - `core/flow/context.yaml`: add `- specweaver/loom/atoms/mcp` to `consumes`.
   - `topology.py`: the frozen `TopologyContext` dataclass gains
     `mcp_servers: dict[str, dict[str, Any]] = field(default_factory=dict)` and
     `consumes_resources: list[str] = field(default_factory=list)`. `format_context_summary()` in
     `TopologyGraph` serializes them when `TopologyContext` maps are built.
2. **Assembler** · [NEW] `src/specweaver/core/flow/handlers/mcp_assembler.py` — called by handlers
   before `PromptBuilder`.
   - `async def evaluate_and_fetch_mcp_context(context: RunContext) -> str | None:`
   - Reads `context.topology.mcp_servers` and `consumes_resources`; for each server runs
     `MCPAtom.run()` on the URIs.
   - Wraps `MCPAtom.run()` in `asyncio.to_thread(_sync_fetch, ...)`: its stdio blocks the event loop
     (NFR-2).
   - Unpacks `AtomResult.contents`, keeps only `result.contents.text`, strips the raw JSON protocol
     payload (`jsonrpc="2.0"`). Returns a YAML dict of `{URI: block}`.
3. **Handler injection**
   - `src/specweaver/core/flow/handlers/generation.py`: import `evaluate_and_fetch_mcp_context`. In
     `GenerateCodeHandler.execute()` and `GenerateTestsHandler.execute()`:
     `mcp_env = await evaluate_and_fetch_mcp_context(context)`, passed to `Generator.generate_code`
     and `generate_tests` as the new kwarg `environment_context=mcp_env`.
   - `src/specweaver/core/flow/handlers/review.py`: same sequence, `mcp_env` to `Reviewer`.
   - `src/specweaver/workflows/implementation/generator.py`: `generate_code`, `generate_tests`
     accept `environment_context: str | None = None` and append
     `.add_context(environment_context, "environment_context")` to the `PromptBuilder` chain.
   - `src/specweaver/workflows/review/reviewer.py`: same for `review_code` and `review_spec`.

## Tests

| File | Change |
|---|---|
| [MODIFY] `tests/unit/core/flow/handlers/test_generation.py` | mocks cover `MCPAtom` interactions |
| [MODIFY] `tests/unit/core/flow/handlers/test_review.py` | mirrors the generation tests |
| [MODIFY] `tests/integration/core/flow/engine/test_generation_loopback_integration.py` | mock `TopologyContext` mappings; MCP context reaches the prompt via `environment_context` without failures |

Checks: `tach check` (`core/flow` imports the atom), `ruff check .`, `mypy .`.

## As built

**Since moved** (2026-09-25 check): the assembler imports `MCPAtom` from
`specweaver.sandbox.mcp.core.atom` and reads the topology from `context.graph.topology`. Unit proof:
`tests/unit/core/flow/handlers/test_mcp_assembler.py`.
