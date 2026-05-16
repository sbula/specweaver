# Tool Architecture (4-Layer Stack)

Each tool domain (filesystem, git, qa_runner, web) follows the same layered pattern:

```text
Flow Engine ──▶ Atom ──▶ Interface ──▶ Tool ──▶ Executor
(Lifecycle)    (Step)    (Role RBAC)   (Intent)  (Raw I/O)
```

## Layer Responsibilities

| Layer | Location | Responsibility |
|-------|----------|----------------|
| **Executor** | `sandbox/{domain}/` | Raw I/O with transport-level security (whitelists, path validation, symlink blocking) |
| **Tool** | `sandbox/{domain}/tool.py` | Intent-based operations with role gating (`ROLE_INTENTS`) + grant enforcement (`FolderGrant`) |
| **Interface** | `sandbox/{domain}/interfaces.py` | Role-specific facades — unauthorized methods physically absent |
| **Atom** | `sandbox/{domain}/` | Engine-internal workflow operations (unrestricted, not agent-facing) |

## Security Stack

1. **Executor** — transport-level blocking (whitelists, path validation, symlink blocking)
2. **Tool** — intent-level gating (`ROLE_INTENTS`) + grant enforcement (`FolderGrant`)
3. **Interface** — method-level RBAC (unauthorized methods physically absent)

Do NOT create parallel security mechanisms. Use the existing stack.

---

# Atom vs Tool

Both atoms and tools use executors from `commons/` — but they serve fundamentally
different consumers and have different trust models:

| | Tool | Atom |
|---|------|------|
| **Consumer** | AI agent (LLM) | Flow engine (SpecWeaver internal) |
| **Access control** | Role-restricted interfaces — methods physically absent | Unrestricted — full access to executor |
| **Trust model** | Agent is untrusted — security enforced at every layer | Engine is trusted — no role gating needed |
| **Location** | `sandbox/{domain}/` | `sandbox/{domain}/` |
| **Forbids** | `atoms/*` | `tools/*` |
| **Example** | `GitTool.commit()` checks conventional commits, role gating | `EngineGitExecutor.run()` — raw `git` with full whitelist |

## Key Distinction

Tools exist because **agents cannot be trusted**. Every tool method:
1. Checks if the agent's role allows this intent
2. Checks if the agent's folder grants cover this path
3. Delegates to the executor with validated parameters

Atoms exist because **the engine needs unrestricted access** to perform
workflow operations (e.g., running tests, linting, committing after review).
They bypass the role/grant checking because the engine itself is trusted code.

```text
Agent (LLM)                          Engine (SpecWeaver)
     │                                     │
     ▼                                     ▼
Role Interface ──▶ Tool ──▶ Executor  Atom ──▶ Executor
  (RBAC)         (Intent)  (Raw I/O)        (Raw I/O)
```

## Atom Base Class

```python
class Atom(ABC):
    @abstractmethod
    def run(self, context: dict[str, Any]) -> AtomResult:
        """Execute the discrete unit of work."""

    def cleanup(self) -> None:
        """Graceful teardown hook (SIGINT/SIGTERM)."""
```

Returns `AtomResult(status=SUCCESS|FAILED|RETRY, message, exports)`.
The engine reads `exports` and writes them to the flow context for
downstream atoms.
