# A-VAL-01 SF-03 — Core Flow Engine Alignment (Atom/Tool)

**Status**: APPROVED · **FRs owned**: FR-4 · **Depends on**: SF-01, SF-02 · **Legacy Feature ID**:
3.31 · Design: [A-VAL-01_design.md](A-VAL-01_design.md) §Sub-features → SF-03

FR attribution added 2026-08-16 by `TECH-051` CB-2: the plan predates the FR ledger, so
`check_fr_coverage.py A-VAL-01` reported all five as *carried by no implementation plan* on a delivered
DAL-A capability. Mapped from this sub-feature's own scope — the Atom and Tool connectors into the flow
engine — not assigned to make a number fall. The work is unchanged.

## Goal

`ProtocolAtom` and `ProtocolTool` expose the SF-01/SF-02 `ProtocolSchemaInterface` parsers to
automated pipelines and to agents.

## Changes

**Atom** — `core/loom/atoms/protocol/`: programmatic execution on dictionaries, no LLM strings.

1. **[NEW] `src/specweaver/core/loom/atoms/protocol/context.yaml`** — `archetype: atom`. Consumes
   `commons/protocol`. Forbids `tools/*`.
2. **[NEW] `src/specweaver/core/loom/atoms/protocol/atom.py`** — `ProtocolAtom(Atom)`, intents:
   - `extract_schema_endpoints`: opens the file, picks the parser from `ProtocolParserFactory`,
     parses, returns `.model_dump()` dictionaries of `ProtocolEndpoint`.
   - `extract_schema_messages`: returns `.model_dump()` dictionaries of `ProtocolMessage`.

**Factory** — `core/loom/commons/protocol/`:

3. **[NEW] `src/specweaver/core/loom/commons/protocol/factory.py`** — protocol identification stays in
   the adapter layer. Parses `Code` content (`ruamel.yaml` loads), looks for root keys like
   `openapi: "3.0"` or `asyncapi: "3.0"`, and maps them to the split parsers.

**Tool** — `core/loom/tools/protocol/`: exposes the Atom to LLMs inside `core/agents/`.

4. **[NEW] `src/specweaver/core/loom/tools/protocol/context.yaml`** — `archetype: tool`. Consumes
   `atoms/protocol`.
5. **[NEW] `src/specweaver/core/loom/tools/protocol/tool.py`** — `ProtocolTool(StructuredLLMTool)`
   wraps `ProtocolAtom` with strict object schemas; an agent issues intents with a file path.

## Decisions (HITL)

| Decision | Why |
|---|---|
| Atom results are structural JSON/dictionary shapes | Downstream validators intersect them as arrays |
| File-format detection lives in the factory, not the Atom | Keeps file-reading logic out of the Atom |

## Tests

| Test | Checks |
|---|---|
| `test_protocol_atom.py` | `ProtocolAtom` maps `.proto`/`.yaml` via `ProtocolParserFactory` |
| `test_protocol_factory.py` | minimal mock contents map to OpenAPI vs AsyncAPI |
| Tach | the `context.yaml` boundaries of all 3 modules stay acyclic |

Manual verification: N/A.

## As built

**Since moved** (2026-05-03, `7b35a900`, TECH-01): atom and factory →
`src/specweaver/sandbox/protocol/core/{atom,factory}.py`; tool →
`src/specweaver/sandbox/protocol/interfaces/tool.py`, served from `sandbox/registry.py`.
