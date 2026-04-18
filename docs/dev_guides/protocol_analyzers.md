# Protocol & Schema Analyzers

SpecWeaver utilizes a purely native, zero-compilation protocol parsing layer located at `specweaver/core/loom/commons/protocol`. This module is designed to structurally map external API definitions (like OpenAPI `paths`, AsyncAPI `channels`, and gRPC `rpc` methods) into standard `ProtocolEndpoint` and `ProtocolMessage` Pydantic models.

Currently supported out of the box:
- **OpenAPI 3.x**: Extracts `paths` and `components.schemas`.
- **AsyncAPI 3.x**: Extracts `channels` and `components.messages`.

## Architectural Constraints

The Protocol module operates inside the Execution layer (Loom) but acts as an **adapter**.
1. **Zero I/O Logic**: The interface only accepts standard python `str` payloads. The logic to read files from disk is managed by `ProtocolTool` and passed downward.
2. **Strict Typings**: Due to the heavily nested and chaotic nature of YAML dictionaries inside `components.schemas`, standard dictionaries are banned from passing the Loom boundary. Everything must be mapped to `ProtocolMessage` cleanly before extraction completes.
3. **Speed over Validity**: We explicitly skip robust library-level semantic validation (e.g., `jsonschema` library validation) to maintain the strict < 50ms per-file parsing speed budget. If an API contract violates basic topological expectations, exceptions like `ProtocolSchemaError` are raised immediately natively.

## Integrating a New Protocol

If you need to add support for GraphQL, Avro, or Thrift, follow these steps:

1. **Implement `ProtocolSchemaInterface`**:
    Define a new class inside `commons/protocol/<format>_parser.py` implementing `extract_endpoints` and `extract_messages`.
2. **Adhere closely to Pydantic**: 
    If a schema concept doesn't cleanly map to an endpoint or message, map the raw dictionary values into the generic `.properties` dictionary of the Model.
3. **Register the Parser**:
    (Will be wired up during Atom integrations)
