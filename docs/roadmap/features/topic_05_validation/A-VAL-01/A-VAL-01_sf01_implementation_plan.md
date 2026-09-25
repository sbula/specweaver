# A-VAL-01 SF-01 — ProtocolSchemaInterface & YAML Parsers

**Status**: APPROVED · **FRs owned**: FR-1, FR-3 · **Depends on**: none · **Legacy Feature ID**: 3.31 ·
Design: [A-VAL-01_design.md](A-VAL-01_design.md) §Sub-features → SF-01

FR attribution added 2026-08-16 by `TECH-051` CB-2: the plan predates the FR ledger, so
`check_fr_coverage.py A-VAL-01` reported all five as *carried by no implementation plan* on a delivered
DAL-A capability. Mapped from this sub-feature's own scope — YAML parsing (OpenAPI + AsyncAPI) and the
`ProtocolSchemaInterface` — not assigned to make a number fall. The work is unchanged.

## Goal

Core boundaries and YAML extraction for `ProtocolSchemaInterface`: OpenAPI and AsyncAPI parsing via
`ruamel.yaml`, without breaking the programming-language Code Structure workflows.

## Changes

Module `core/loom/commons/protocol` — boundaries, data models, YAML parsers.

1. **[NEW] `src/specweaver/core/loom/commons/protocol/context.yaml`**
   — `adapter` archetype for external format ingestion; strict
   `consumes`/`forbids` so nothing leaks down into the flow engine or Atom structures.
   - `archetype: adapter`
   - `consumes: [specweaver/commons]`
   - `forbids: [specweaver/loom/tools/*, specweaver/loom/atoms/*]`
2. **[NEW] `src/specweaver/core/loom/commons/protocol/models.py`**
   — Pydantic models for API endpoints and schemas:
   - `ProtocolEndpoint`: HTTP methods, paths, or gRPC RPCs.
   - `ProtocolMessage`: payload structures/schemas.
   - `ProtocolSchemaSet`: a collection of the parsed outputs.
3. **[NEW] `src/specweaver/core/loom/commons/protocol/interfaces.py`**
   — `ProtocolSchemaError` and the ABC `ProtocolSchemaInterface`:
   - `extract_endpoints(raw_schema: str) -> list[ProtocolEndpoint]`
   - `extract_messages(raw_schema: str) -> list[ProtocolMessage]`
4. **[NEW] `src/specweaver/core/loom/commons/protocol/openapi_parser.py`**
   — `ProtocolSchemaInterface` for OpenAPI `3.x`, `ruamel.yaml` safe load.
5. **[NEW] `src/specweaver/core/loom/commons/protocol/asyncapi_parser.py`**
   — `ProtocolSchemaInterface` for AsyncAPI `3.x`, `ruamel.yaml` safe
   load. Reads `channels` and `messages`.

`ruamel.yaml` `YAML(typ='safe')` gives fast IO. Separate `OpenAPIParser` and `AsyncAPIParser` avoid
branching on format inside one parser.

## Decisions (HITL)

| Decision | Why |
|---|---|
| Parsers return strict Pydantic structures, not raw dictionaries | Prevents type hallucination later inside the engine's AST difference checkers |
| No embedded generic validation via `jsonschema` | NFR-1 speed budget. If `openapi.yaml` structural keys like `paths` are malformed, failure is a `ProtocolSchemaError` raised on the key miss |

## Tests

| Test | Checks |
|---|---|
| `test_openapi_parser.py` | valid and malformed YAML; < 5ms token generation per payload |
| `test_asyncapi_parser.py` | the returned Pydantic properties are correct |
| Tach | the `context.yaml` `forbids` bounds hold |

Manual verification: N/A.

## As built

**Since moved** (2026-05-03, `7b35a900`, TECH-01): `core/loom/commons/protocol/` →
`src/specweaver/sandbox/protocol/core/`; `interfaces.py` → `protocol_interfaces.py`.
