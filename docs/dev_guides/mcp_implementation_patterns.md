# Developer Guide: MCP Infrastructure Architecture

SpecWeaver utilizes a robust implementation of Anthropic's **Model Context Protocol (MCP)** to natively integrate external workspace contexts (like remote PostgreSQL database schemas, Jira tickets, and external repositories) precisely into the Agent logic bounds without succumbing to System Prompt token saturation.

## 1. Architectural Strategy

SpecWeaver adheres to the **Pre-Fetched Context Envelope** pattern (AD-1). We strictly forbid standard "conversational tool use" for MCP injection. Instead:
- External dependencies are formally defined in a project's `context.yaml`.
- The `ContextAssembler` pre-fetches the string states asynchronously during the L3 bootstrap using the `MCPAtom`.
- The string payloads are deeply serialized as an immutable `<environment_context>` block and injected into the target LLM generation frame.

## 2. Loom Orchestration Bounds (The MCP Atom)

The engine bridges connection streams into standard JSON-RPC packets.

```yaml
# src/specweaver/sandbox/mcp/context.yaml
module: "specweaver.sandbox.mcp"
archetype: "orchestrator"
forbids:
  - "specweaver.sandbox.*" # Agents cannot directly hit the raw Atom.
```

The underlying `MCPExecutor` binds the target string dynamically over standard I/O byte transmission channels to prevent asynchronous pipeline blocking.

### Isolation Mandates (NFR-2)
To completely mitigate Agent RCE (Remote Code Execution) exposure during server bootstrapping, `MCPAtom` **strictly** dictates execution inside isolated Docker/Podman engines. Passing `["node", "index.js"]` dynamically will structurally panic the initialization string. Native Python execution paths (`sys.executable`) are whitelisted uniquely for internal CI mapping frameworks.

## 3. Extending the MCP Client

Adding a new intent natively to the MCP bridging pipe requires extending `MCPAtom.run()`.
1. Append your expected target vector to `MCPAtom._intent_<your_method>`.
2. Map the payload securely into the internal `_executor.call_rpc` buffer constraint.
3. Establish appropriate integration tests tracking your raw JSON string formatting logic inside `test_atom_ipc.py`.


### MCP Explorer Tool
The **MCP Explorer Tool** serves as the dynamic discovery endpoint for L2 Architects. While implementations and code generation handlers simply receive injected pre-fetched context from explicit URIs, the Architect role can actively explore 
esources/list natively during the planning phase via ArchitectMCPInterface.
