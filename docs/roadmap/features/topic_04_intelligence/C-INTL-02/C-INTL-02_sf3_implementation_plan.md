# Implementation Plan: Common MCP Client Architecture [SF-3: The Pre-Fetch Assembler]
- **Feature ID**: 3.32c
- **Sub-Feature**: SF-3 — The Pre-Fetch Assembler (Flow Engine)
- **Design Document**: docs/roadmap/features/topic_04_intelligence/C-INTL-02/C-INTL-02_design.md
- **Design Section**: §Sub-Feature Breakdown → SF-3
- **Implementation Plan**: docs/roadmap/features/topic_04_intelligence/C-INTL-02/C-INTL-02_sf3_implementation_plan.md
- **Status**: APPROVED

## Feature Summary
SF-3 implements a lazy-loading "Pre-Fetch Assembler" inside the SpecWeaver Flow engine. It statically maps architectural dependencies (MCP resources), securely triggers the `MCPAtom` to fetch external strings via standard IPC channels, and parses the output natively into the `PromptBuilder` for zero-latency LLM context tracking.

---

## 1. Topologcial Bound Modifications

### [MODIFY] `src/specweaver/core/flow/context.yaml`
**Rationale**: `flow` is mathematically restricted from invoking `MCPAtom` currently.
- Add `- specweaver/loom/atoms/mcp` to the `consumes` array.
- *Caution*: `flow` is `async_ready: true`, but `MCPAtom` is `async_ready: false`. This SLA friction demands asynchronous non-blocking thread execution inside the handler bounds.

### [MODIFY] `src/specweaver/assurance/graph/topology.py`
**Rationale**: `RunContext.topology` is a read-only `TopologyContext` record that currently drops all knowledge of `mcp_servers` originally defined in the `TopologyNode`.
- Update the frozen `TopologyContext` dataclass constructor to accept `mcp_servers: dict[str, dict[str, Any]] = field(default_factory=dict)` and `consumes_resources: list[str] = field(default_factory=list)`.
- Update `format_context_summary()` in `TopologyGraph` to properly serialize this state into the context payload when `TopologyContext` maps are generated.

---

## 2. The Context Assembler Utility

### [NEW] `src/specweaver/core/flow/handlers/mcp_assembler.py`
**Rationale**: Lazy-loading utility function that Handlers invoke before hitting `PromptBuilder`.
- Create `async def evaluate_and_fetch_mcp_context(context: RunContext) -> str | None:`
- Retrieve `context.topology.mcp_servers` and `consumes_resources`.
- Iterate through each active server, physically invoking `MCPAtom.run()` targeting the string URIs.
- **Critical SLA Guard**: Wrap `MCPAtom.run()` execution explicitly in `asyncio.to_thread(_sync_fetch, ...)` because `MCPAtom`'s internal standard I/O byte transmission blocks standard Unix thread event loops (NFR-2).
- **JSON-RPC Shredding**: Iteratively unpack `AtomResult.contents`, extracting only `result.contents.text`. Fully strip out raw JSON protocol payloads (`jsonrpc="2.0"`) prior to returning. Format string as YAML dict of `{URI: block}` to natively assist LLM Markdown context formatting.

---

## 3. Handler Context Injections

### [MODIFY] `src/specweaver/core/flow/handlers/generation.py`
- Import `evaluate_and_fetch_mcp_context` globally.
- In `GenerateCodeHandler.execute()` and `GenerateTestsHandler.execute()`:
  - Add `mcp_env = await evaluate_and_fetch_mcp_context(context)`.
  - Pass `mcp_env` string downward natively into the nested `Generator.generate_code` and `generate_tests` call via a new parameter kwarg `environment_context=mcp_env`.

### [MODIFY] `src/specweaver/core/flow/handlers/review.py`
- Follow exact sequence mapped in `generation.py` to pipe `mcp_env` string downwards to `Reviewer`.

### [MODIFY] `src/specweaver/workflows/implementation/generator.py`
- Modify `generate_code` and `generate_tests` to securely accept `environment_context: str | None = None`.
- Inside `PromptBuilder` chain, natively append `.add_context(environment_context, "environment_context")`.

### [MODIFY] `src/specweaver/workflows/review/reviewer.py`
- Modify `review_code` and `review_spec` to securely accept `environment_context: str | None = None`.
- Inside `PromptBuilder` chain, natively append `.add_context(environment_context, "environment_context")`.

---

## 4. Verification Plan

### Test Modifications
- **[MODIFY]** `tests/unit/core/flow/handlers/test_generation.py`: Update mocks ensuring `MCPAtom` interactions behave properly.
- **[MODIFY]** `tests/unit/core/flow/handlers/test_review.py`: Mirror generation tests.
- **[MODIFY]** `tests/integration/core/flow/engine/test_generation_loopback_integration.py`: Integrate mock `TopologyContext` mappings verifying MCP contexts physically traverse via `environment_context` natively without system panic limit failures.

### Automated Checks
- `tach check`: Confirm `core/flow` correctly imports the atom.
- `ruff check .`
- `mypy .`
