# Tool Architecture (4-Layer Stack)

Each tool domain (filesystem, git, qa_runner, web, mcp) follows one layered pattern. Agents reach
I/O only through Interface → Tool → Executor. The flow engine reaches it through an Atom.

```text
Flow Engine ──▶ Atom ──▶ Interface ──▶ Tool ──▶ Executor
(Lifecycle)    (Step)    (Role RBAC)   (Intent)  (Raw I/O)
```

## Layers

| Layer | Location | Responsibility |
|-------|----------|----------------|
| **Executor** | `sandbox/{domain}/core/executor.py` | Raw I/O with transport-level security (whitelists, path validation, symlink blocking) |
| **Tool** | `sandbox/{domain}/interfaces/tool.py` | Intent-based operations with role gating (`ROLE_INTENTS`) + grant enforcement (`FolderGrant`) |
| **Interface** | `sandbox/{domain}/interfaces/facades.py` | Role-specific facades — unauthorized methods are absent, not blocked |
| **Atom** | `sandbox/{domain}/core/atom.py` | Engine-internal workflow operations (unrestricted, not agent-facing) |

Since moved (noted 2026-09-25): tools and facades were `sandbox/{domain}/tool.py` and
`sandbox/{domain}/interfaces.py`. The `web` domain has only `interfaces/`.

## Security stack

1. **Executor** — transport-level blocking (whitelists, path validation, symlink blocking)
2. **Tool** — intent-level gating (`ROLE_INTENTS`) + grant enforcement (`FolderGrant`)
3. **Interface** — method-level RBAC (unauthorized methods absent)

Rule: do NOT create parallel security mechanisms. Use this stack.

---

# Atom vs Tool

Both wrap the same executors. They differ in consumer and trust:

| | Tool | Atom |
|---|------|------|
| **Consumer** | AI agent (LLM) | Flow engine (SpecWeaver internal) |
| **Access control** | Role-restricted interfaces — methods absent | Unrestricted — full access to executor |
| **Trust model** | Agent is untrusted — security enforced at every layer | Engine is trusted — no role gating needed |
| **Location** | `sandbox/{domain}/interfaces/` | `sandbox/{domain}/core/` |
| **Dependency rule** | `interfaces/` consumes `core/` | `core/` does not import `interfaces/` |
| **Example** | `GitTool.commit()` checks conventional commits, role gating | `EngineGitExecutor.run()` — raw `git` with full whitelist |

The dependency rule replaced the old `forbids` pair (tools forbade `atoms/*`, atoms forbade
`tools/*`) when the domains split into `core/` and `interfaces/`.

## Why two paths

**Tools exist because agents cannot be trusted.** Every tool method:

1. Checks if the agent's role allows this intent.
2. Checks if the agent's folder grants cover this path — with the one shared matcher,
   `sandbox.security.grant_mode_for`, never a copy of its own.
3. Delegates to the executor with validated parameters.

**Atoms exist because the engine needs unrestricted access** for workflow operations (running tests,
linting, committing after review). They skip role/grant checks because the engine is trusted code.

```text
Agent (LLM)                          Engine (SpecWeaver)
     │                                     │
     ▼                                     ▼
Role Interface ──▶ Tool ──▶ Executor  Atom ──▶ Executor
  (RBAC)         (Intent)  (Raw I/O)        (Raw I/O)
```

## Atom base class

Defined in `sandbox/base.py`.

```python
class Atom(ABC):
    @abstractmethod
    def run(self, context: dict[str, Any]) -> AtomResult:
        """Execute the discrete unit of work."""

    def cleanup(self) -> None:
        """Graceful teardown hook (SIGINT/SIGTERM)."""
```

Returns `AtomResult(status=SUCCESS|FAILED|RETRY, message, exports)`. The engine writes `exports` to
the flow context for downstream atoms.

### Atom ≠ single operation

An Atom is one indivisible **unit of the flow**: one `run()` call, one `AtomResult`. How much
`run()` does inside is an ordinary design choice:

- **Single-operation** (`RuleAtom`): reads its expected keys straight off `context` and does one thing.
- **Multi-operation** (`QARunnerAtom`, `LanguageAtom`, `ProtocolAtom`): reads an `intent`/`action`
  key from `context` and dispatches internally (e.g. `QARunnerAtom` alone handles `run_tests`,
  `run_linter`, `run_complexity`, `run_compiler`, `run_debugger`, `run_architecture`).

Pick the shape by how many closely related operations the domain has. A Tool for the same domain
usually mirrors its Atom's shape, since both wrap the same Executor operations.
