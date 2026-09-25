# A-VAL-01 SF-02 — gRPC Protobuf Parser

**Status**: APPROVED · **FRs owned**: FR-2 · **Depends on**: SF-01 · **Legacy Feature ID**: 3.31 ·
Design: [A-VAL-01_design.md](A-VAL-01_design.md) §Sub-features → SF-02

FR attribution added 2026-08-16 by `TECH-051` CB-2: the plan predates the FR ledger, so
`check_fr_coverage.py A-VAL-01` reported all five as *carried by no implementation plan* on a delivered
DAL-A capability. Mapped from this sub-feature's own scope — the gRPC/proto parser — not assigned to
make a number fall. The work is unchanged.

## Goal

A gRPC parser on `proto-schema-parser` that extracts `.proto` schemas and maps services into the
normalized `ProtocolSchemaInterface` Pydantic models from SF-01.

## Changes

1. **[MODIFY] `pyproject.toml`** — add `proto-schema-parser>=0.5.0` to `dependencies`.
2. **[MODIFY] `src/specweaver/core/loom/commons/protocol/models.py`** — small addition only if needed;
   gRPC semantics mostly fit a generic `payload: dict` or custom properties on existing models, still
   resolving into standard `ProtocolEndpoint`.
3. **[NEW] `src/specweaver/core/loom/commons/protocol/grpc_parser.py`** — `ProtocolSchemaInterface` on
   `proto_schema_parser.parser.Parser`:
   - Top-level `service` nodes iterate their nested `rpc` methods.
   - Each `rpc` → `ProtocolEndpoint` (`method` ="RPC", `path`="{service_name}/{rpc_name}").
   - `message` items → `ProtocolMessage`.

RPC parameters map to Request types and return payloads to Response types.

## Decisions (HITL)

| Decision | Why |
|---|---|
| gRPC is mapped into standard `ProtocolEndpoint` | Keeps one type for downstream Flow pipelines that check for missing endpoints |
| `tree-sitter-proto` omitted | Its native `.so` compilation crashes CI/CD sandboxes that lock GCC builds |

## Tests

| Test | Checks |
|---|---|
| `test_grpc_parser.py` | complex layered `.proto` definitions; RPC request/response types captured |
| NFR-2 | zero build extensions invoked; pure Python `ast`-style visiting |

Manual verification: N/A.

## As built

**Since moved** (2026-05-03, `7b35a900`, TECH-01): `grpc_parser.py` →
`src/specweaver/sandbox/protocol/core/grpc_parser.py`.
