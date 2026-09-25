# MCP Implementation Patterns

Use when: you change how SpecWeaver pulls external context (remote PostgreSQL schemas, Jira tickets,
external repositories) through Anthropic's **Model Context Protocol (MCP)**, or add an MCP intent.

## Pre-Fetched Context Envelope (AD-1)

MCP context is never injected through conversational tool use; that would saturate the system
prompt. Instead:

1. External dependencies are declared in the project's `context.yaml`.
2. The `ContextAssembler` pre-fetches them asynchronously during the L3 bootstrap via `MCPAtom`.
3. The payloads are serialized into an immutable `<environment_context>` block in the LLM generation
   frame.

Exception: the **MCP Explorer Tool**. Implementation and code-generation handlers only get the
pre-fetched context from explicit URIs; the L2 Architect can explore `resources/list` during
planning via `ArchitectMCPInterface`.

## The MCP Atom (Loom)

The engine turns connection streams into JSON-RPC packets. `MCPExecutor` talks to the server over
standard I/O so the pipeline does not block.

```yaml
# src/specweaver/sandbox/mcp/context.yaml
module: "specweaver.sandbox.mcp"
archetype: "orchestrator"
forbids:
  - "specweaver.sandbox.*" # Agents cannot directly hit the raw Atom.
```

Since moved (2026-09-25): the module is split into `sandbox/mcp/core/` (`archetype: adapter`) and
`sandbox/mcp/interfaces/`.

### Isolation (NFR-2)

To close Agent RCE (Remote Code Execution) exposure at server bootstrap, `MCPAtom` runs servers only
inside Docker/Podman. A bare command like `["node", "index.js"]` is refused at initialization.
`sys.executable` is allowed only for internal tests (they patch `_ALLOW_INTERPRETER`).

## Steps: add an MCP intent

1. Add `MCPAtom._intent_<your_method>`; `MCPAtom.run()` dispatches to it.
2. Send the payload through `_executor.call_rpc`.
3. Add integration tests for the raw JSON string formatting in `test_atom_ipc.py`.
