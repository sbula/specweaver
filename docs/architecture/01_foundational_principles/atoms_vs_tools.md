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

### Atom ≠ single operation

"Atom" describes an indivisible **unit of the flow** — one `run()` call the
engine invokes and gets one `AtomResult` back from. It does NOT mean the
Atom only implements one operation. Whether `run()` handles one thing or
many is an independent implementation choice, not part of what makes
something an Atom:

- **Single-operation** (`RuleAtom`): reads its expected keys straight off
  `context` and does the one thing it exists to do.
- **Multi-operation** (`QARunnerAtom`, `LanguageAtom`, `ProtocolAtom`):
  reads an `intent`/`action` key from `context` and dispatches internally
  (e.g. `QARunnerAtom` alone handles `run_tests`, `run_linter`,
  `run_complexity`, `run_compiler`, `run_debugger`, `run_architecture`).

Pick single vs. multi-operation the same way you'd pick it for any class —
by how many closely-related operations the domain naturally has — not by
any rule about what "Atom" is allowed to mean. A Tool serving the same
domain often mirrors whichever shape its Atom counterpart uses, since both
usually wrap the same underlying Executor operations.
