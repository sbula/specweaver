# Design: Two Agent Tools Skip the Sandbox's Own Guards

- **Feature ID**: TECH-072
- **Epic**: Topic 07 (Technical Debt)
- **Kind**: bugfix
- **Status**: DRAFT — awaiting approval
- **Origin**: 2026-09-26, the subject-scatter audit behind the backlog dependency map. Both verified
  in code the same day.

## What is wrong

Two agent-facing tools bypass a guard that the sandbox already has. Both are defects in delivered
work (`E-SENS-03` grants, `C-INTL-02` MCP), so they sit here.

| # | Tool | Guard it skips | Effect |
|---|---|---|---|
| 1 | AST / code-structure tool, built in `sandbox/dispatcher.py` `_build_ast_kwargs` | `FileExecutor._PROTECTED_PATTERNS` (`context.yaml`, `.env`, `.git`, `.specweaver`) | It writes through `EngineFileExecutor`, whose protected set is empty. An agent can overwrite `context.yaml` — the file that states its own boundaries |
| 2 | `MCPExplorerTool` (`sandbox/mcp/interfaces/tool.py`) | `MCPAtom`'s runtime guard: docker/podman only, runtime resolved from the trusted PATH, host-escape arguments and host mounts refused; and its secret scrubbing | It starts `MCPExecutor` with the command from the analysed project's MCP config as written. That config is untrusted input, so a project can make the architect agent run any program |

## How the fix works

1. **AST tool:** `_build_ast_kwargs` builds the atom on `FileExecutor` instead of
   `EngineFileExecutor`. The atom only calls `read` and `write`, so nothing else changes. Engine-side
   users of `CodeStructureAtom` (flow handlers) are not agent-facing and are out of scope.
2. **MCP explorer:** the tool runs every command through the same guard `MCPAtom` uses, before any
   process starts, and scrubs the configured env secrets from the response. The guard function
   becomes public in `sandbox/mcp/core/atom.py` so both paths share one copy — not a second one.

## Functional Requirements

| # | FR | Actor | Action | Outcome |
|---|-----|-------|--------|---------|
| FR-1 | Agent AST writes respect protected paths | AST tool | SHALL refuse a write to any path containing `context.yaml`, `.env`, `.git` or `.specweaver` | An agent cannot rewrite its own boundary or secrets through the AST tool |
| FR-2 | MCP explorer runs only guarded commands | MCPExplorerTool | SHALL refuse, before starting any process, a command that `MCPAtom` would refuse: a runtime other than docker/podman, host-escape arguments, forbidden host mounts | A project's MCP config cannot make the explorer run an arbitrary program |
| FR-3 | MCP explorer scrubs secrets | MCPExplorerTool | SHALL replace configured env values of 8+ characters in the returned data, as `MCPAtom` does | Secrets passed to an MCP server do not reach the agent |
| FR-4 | One guard, one copy | Both MCP paths | SHALL use the same guard function | The two paths cannot drift apart again |

## Tests

| Tier | Case |
|---|---|
| Unit | FR-1: AST tool write to `context.yaml` and `.env/x` is refused; a normal `src/` write still works |
| Unit | FR-2: explorer with `command: python`, with `--privileged`, with `-v /:/host` → error, and no process started |
| Unit | FR-3: a secret value in the server's reply comes back as `***RESTRICTED***` |
| Integration | FR-1 through the real dispatcher: an agent role's AST tool cannot write `context.yaml` |

Each test is written first and seen to fail on today's code.

## Non-Goals

- The other scatter findings in the same audit (grant matchers, role maps, isolation roots) — they are
  consistency issues, not a bypass of an existing guard.
- Changing which paths are protected, or which runtimes are allowed. Both lists stay as they are.

## Progress Tracker
| SF | Name | Depends On | Design | Impl Plan | Dev | Pre-Commit | Committed |
|----|------|-----------|--------|-----------|-----|------------|-----------|
| SF-01 | Both guards applied | — | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ |
