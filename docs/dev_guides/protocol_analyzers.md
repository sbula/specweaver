# Protocol and Schema Analyzers

Use when: you add or change parsing of API contracts (OpenAPI, AsyncAPI, gRPC, or a new format).

SpecWeaver's zero-compilation protocol layer maps external API definitions (OpenAPI `paths`,
AsyncAPI `channels`, gRPC `rpc` methods) into `ProtocolEndpoint` and `ProtocolMessage` Pydantic
models. Documented location: `specweaver/sandbox/commons/protocol`; since moved (2026-09-25) to
`src/specweaver/sandbox/protocol/core/` (parsers, factory, atom) and
`src/specweaver/sandbox/protocol/interfaces/tool.py`.

| Format | Extracts |
|---|---|
| **OpenAPI 3.x** | `paths` and `components.schemas` |
| **AsyncAPI 3.x** | `channels` and `components.messages` |
| **gRPC (.proto)** | `service`/`rpc` as paths, `message` payloads, via `proto-schema-parser` |

## Rules

The module sits in the execution layer (Loom) but is an **adapter**.

1. **Zero I/O.** Parsers accept python `str` payloads only. `ProtocolTool` reads files and passes
   the text down.
2. **Strict types.** YAML under `components.schemas` is deeply nested and irregular, so raw
   dictionaries may not cross the Loom boundary. Map everything to `ProtocolMessage` before
   extraction completes.
3. **Speed over validity.** No library-level semantic validation (e.g. `jsonschema` library
   validation), to hold the < 50ms per-file parsing budget. A contract that breaks basic topological
   expectations raises `ProtocolSchemaError` immediately.

## Steps: add a protocol (e.g. GraphQL, Avro, Thrift)

1. **Implement `ProtocolSchemaInterface`** in `commons/protocol/<format>_parser.py` (today
   `sandbox/protocol/core/<format>_parser.py`) with `extract_endpoints` and `extract_messages`.
2. **Stay in the Pydantic models.** A concept that fits neither endpoint nor message goes, as raw
   values, into the model's generic `.properties` dictionary.
3. **Register the parser** in the `ProtocolParserFactory.create_parser(payload)` regex routing in
   `src/specweaver/sandbox/protocol/factory.py` (today `sandbox/protocol/core/factory.py`) so it
   detects your format.

## Atom and Tool

| Connector | Does |
|---|---|
| **`ProtocolAtom`** | Takes an intent (`extract_schema_endpoints` or `extract_schema_messages`) and a `file_path`; reads the disk; returns bounded `AtomResult` payloads. OS or Runtime exceptions become a `FAILED` result. |
| **`ProtocolTool`** | Wraps the Atom and returns `ToolDefinition` schemas that provider LLMs use directly, so agents extract protocol intents inside the execution harness. |

## Validation: C13 Contract Drift

`ProtocolAtom` feeds **C13 Contract Drift Rule** in the architectural check pipeline:

1. The orchestrator calls `ProtocolAtom` and gets a `List[ProtocolEndpoint]`.
2. A separate syntax lookup puts framework routes into `ast_payload` string mappings.
3. Both go into `rule.context["protocol_schema"]` and `rule.context["ast_payload"]` before the rule
   runs.
4. An endpoint from the Spec missing from the Python routes makes `C13ContractDriftRule` halt and
   fail the generation cycle.
