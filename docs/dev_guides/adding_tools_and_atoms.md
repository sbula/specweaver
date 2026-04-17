# Developer Guide: Adding a New Tool & Atom

This guide details the process of expanding SpecWeaver’s autonomous agent capabilities securely. Because we firmly enforce a zero-trust model for LLMs, capabilities are never directly exposed. Instead, they are routed through our 4-layer execution boundary.

---

## 1. The Component Execution Layers

When a capability (e.g., File I/O, Git, Web Search) is added, it must securely serve two completely different consumers: the **Untrusted LLM Agent**, and the **Trusted Flow Engine**.

Because of this dual-trust model, capabilities are built as decoupled, parallel components acting on a shared executor:

```text
For the Agent (Untrusted):
LLM Agent ──▶ Role Interface ──▶ Intent Tool ──▶ Executor (Raw I/O)
(Note: Complex tools like `CodeStructureTool` may securely encapsulate trusted `Atoms` and logical capabilities like `SchemaEvaluator` under the hood to prevent duplicating parsing logic, but they still strictly enforce Role/Folder Grants before delegation.)

For the Engine (Trusted):
Flow Engine ──▶ Atom ──▶ Executor (Raw I/O)
```

### Component: Executor (`commons/`)
The **Executor** is the raw I/O controller (e.g., `FileSystemExecutor`, `GitExecutor`).
- **Location:** `src/specweaver/loom/commons/<domain>/`
- **Role:** Handles subprocess execution, transport-level security (symlink blocking, binary parsing, path traversal protection).
- **Rule:** Never imports from `tools/` or `atoms/`.

### Component: Tool (`tools/`)
The **Tool** wraps the intent and strictly evaluates the Agent's credentials.
- **Location:** `src/specweaver/loom/tools/<domain>/tool.py`
- **Role:** Defines operations based on Intent. Enforces `ROLE_INTENTS` mapping (e.g., stopping a Reviewer from running compilations). Handles contextual `FolderGrant` boundaries.

### Component: Interface (`tools/interfaces.py`)
The **Interface** strips unauthorized commands out entirely.
- **Role:** If a role shouldn’t use a command, it is physically absent on the interface class. The LLM dispatcher won't even see the method.

### Component: Atom (`atoms/`)
The **Atom** provides unrestricted operations reserved solely for the SpecWeaver flow engine.
- **Location:** `src/specweaver/loom/atoms/<domain>/`
- **Role:** The engine is trusted, so atoms bypass `ROLE_INTENTS` and `FolderGrant` checking to directly hit the `Executor`.

---

## 2. Step-by-Step Implementation

To add a new capability string (like `SearchWeb`):

### A. Construct the Base Executor
1. Build `src/specweaver/loom/commons/web/executor.py`.
2. Implement your native logic via API boundaries or strictly controlled subprocess wrappers. 

### B. Define the Tool & Its Interfaces
1. Build `src/specweaver/loom/tools/web/tool.py`.
2. Encapsulate your capabilities behind Intents. 
3. Inject the `ToolDefinition` payload that will be sent to the LLM (OpenAI/Anthropic compatible schema) within `definitions.py`.
4. In `interfaces.py`, define Role facades (e.g., `ReviewerWebInterface` vs `ImplementerWebInterface`).

### C. Construct the Atom (For the Engine)
1. Build `src/specweaver/loom/atoms/web/atom.py`.
2. Provide a clean `run(context)` method for the internal Flow Engine to use if it needs autonomous, non-LLM invocation of the capability.
3. **The Atom calls the Executor directly; it NEVER imports the Tool.** (However, an Untrusted Tool *can* instantiate an Atom instance to reuse its operations, provided the Tool validates Role constraints first).

### D. Wire It Up
1. Connect the newly defined `ToolDefinition` payload into the LLM context injector.
2. Hook the Intent strings heavily into `flow/_review` or `flow/_generation` via the central `loom/dispatcher.py` to ensure routing natively triggers the tool functions.

---

## 3. Security Requirements

- **Never** place a Tool inside `commons/`. Tools strictly require the Executor layer.
- **Never** inject parallel security checks. Use the native `FolderGrant` and path-traversal hooks.
- **`manifest.yaml` checks**: Ensure that the `context.yaml` inside your tools layer correctly `forbids: atoms/*` to prevent circular leakage between trusted/untrusted realms.
