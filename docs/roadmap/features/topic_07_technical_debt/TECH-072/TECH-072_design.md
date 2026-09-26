# Design: Two Agent Tools Skip the Sandbox's Own Guards

- **Feature ID**: TECH-072
- **Epic**: Topic 07 (Technical Debt)
- **Kind**: bugfix
- **Status**: APPROVED — approved by Steve Bula `[agreed 2026-09-26]` ("do not forget TDD")
- **Origin**: 2026-09-26, the subject-scatter audit behind the backlog dependency map. Both verified
  in code the same day.

## What is wrong

Two agent-facing tools bypass a guard that the sandbox already has. Both are defects in delivered
work (`E-SENS-03` grants, `C-INTL-02` MCP), so they sit here.

| # | Tool | Guard it skips | Effect |
|---|---|---|---|
| 1 | AST / code-structure tool, built in `sandbox/dispatcher.py` `_build_ast_kwargs` | `FileExecutor._PROTECTED_PATTERNS` (`context.yaml`, `.env`, `.git`, `.specweaver`) | It writes through `EngineFileExecutor`, whose protected set is empty. An agent can overwrite `context.yaml` — the file that states its own boundaries |
| 2 | `MCPExplorerTool` (`sandbox/mcp/interfaces/tool.py`) | `MCPAtom`'s runtime guard: docker/podman only, runtime resolved from the trusted PATH, host-escape arguments and host mounts refused; and its secret scrubbing | It starts `MCPExecutor` with the command from the analysed project's MCP config as written. That config is untrusted input, so a project can make the architect agent run any program |

**Both holes are latent today** (measured 2026-09-26): no production path gives an agent the
`architect` role that mounts the MCP explorer, and the AST tool cannot read or write any file through
the standard dispatcher. Repairing either would open its hole, so each repair ships with its guard.

**The AST tool is dead:** its grant matcher prefixes a relative path with `/` instead of resolving it
against the project root, so `src/main.py` matches no grant ("No grant covers path"); an absolute
path passes the grant and is refused by `FileExecutor`, which accepts relative paths only. Its comment
calls the logic "identical to FileSystemTool logic" — a copy that drifted. Repair agreed
`[agreed 2026-09-26]` (option b: repair and guard together).

**Found by the red/blue review, live (2026-09-26):** a grant on the project root covered `../anything`,
because the matcher compared `root/../anything` as text. `read_file` was saved by `FileExecutor`, but
`grep` and `find_files` walk the disk themselves: `grep(path="..")` returned a file above the project.
The file tool is in use today, so this one was not latent. Fixed in the shared matcher (FR-7).

## How the fix works

1. **AST tool:** `_build_ast_kwargs` builds the atom on `FileExecutor` instead of
   `EngineFileExecutor`. The atom only calls `read` and `write`, so nothing else changes. The atom also
   stops ignoring the write result: today it reports "Replaced symbol" even when the write failed, so
   the executor swap alone would turn the hole into a silent failure. Engine-side
   users of `CodeStructureAtom` (flow handlers) are not agent-facing and are out of scope.
2. **Grant matching, one copy:** the file tool's matcher (resolves relative paths against the
   project root, normalises `..`) moves to `sandbox/security.py`; the file tool and the AST tool
   both call it. The AST tool receives the project root from the dispatcher.
3. **MCP explorer:** the tool runs every command through the same guard `MCPAtom` uses, before any
   process starts, and scrubs the configured env secrets from the response. The guard function
   becomes public in `sandbox/mcp/core/atom.py` so both paths share one copy — not a second one.

## Functional Requirements

| # | FR | Actor | Action | Outcome |
|---|-----|-------|--------|---------|
| FR-1 | Agent AST writes respect protected paths | AST tool | SHALL refuse a write to any path containing `context.yaml`, `.env`, `.git` or `.specweaver`, and SHALL report the refusal as a failure with the file unchanged | An agent cannot rewrite its own boundary or secrets through the AST tool, and is told so |
| FR-2 | MCP explorer runs only guarded commands | MCPExplorerTool | SHALL refuse, before starting any process, a command that `MCPAtom` would refuse: a runtime other than docker/podman, host-escape arguments, forbidden host mounts | A project's MCP config cannot make the explorer run an arbitrary program |
| FR-3 | MCP explorer scrubs secrets | MCPExplorerTool | SHALL replace configured env values of 8+ characters in the returned data, as `MCPAtom` does | Secrets passed to an MCP server do not reach the agent |
| FR-4 | One guard, one copy | Both MCP paths | SHALL use the same guard function | The two paths cannot drift apart again |
| FR-5 | The agent AST tool works | AST tool | SHALL read and write a file named by a path relative to the project root, within the role's grants | An agent can use the tool it is given |
| FR-6 | One grant matcher | File tool, AST tool | SHALL decide grant coverage with the same function | The same path gets the same verdict from both tools |
| FR-7 | No path outside the root is covered | Grant matcher | SHALL resolve `..` after joining a relative path to the project root, so `../x` is judged as the parent's `x` | `grep` and `find_files` — which walk the disk themselves — cannot read beside or above the project |

## Tests

| Tier | Case |
|---|---|
| Unit | FR-1: AST tool write to `context.yaml` and `.env/x` is refused; a normal `src/` write still works |
| Unit | FR-2: explorer with `command: python`, with `--privileged`, with `-v /:/host` → error, and no process started |
| Unit | FR-3: a secret value in the server's reply comes back as `***RESTRICTED***` |
| Integration | FR-2 through the real dispatcher: the mounted explorer refuses `python` and starts docker by its trusted path |
| Integration | FR-1, FR-5 through the real dispatcher: `src/main.py` is read and rewritten; `.specweaver/`, `.git/`, `.env/` targets refused and unchanged; `../` escape refused |
| Unit | FR-1: the atom reports a refused write as FAILED |
| Unit | FR-6: the file tool and the AST tool agree on grant coverage for the same paths |

Each test is written first and seen to fail on today's code.

## Non-Goals

- The other scatter findings in the same audit (grant matchers, role maps, isolation roots) — they are
  consistency issues, not a bypass of an existing guard.
- Changing which paths are protected, or which runtimes are allowed. Both lists stay as they are.

## Open — the user's call (red/blue review, 2026-09-26)

1. **MCP config env reaches the container runtime client.** A project's MCP `env` is merged into the
   environment of the `docker`/`podman` process (`build_child_env` merges extras after the allowlist),
   so `LD_PRELOAD`, `LD_LIBRARY_PATH` or `DYLD_*` could run code in the client. Both MCP paths share
   it; it predates this ticket. Which variables to refuse is `T-BOUNDARY`.
2. **Protected names are case-sensitive.** `FileExecutor._is_protected` compares path parts exactly,
   so on a case-insensitive disk `.ENV/x` reaches `.env`. Predates this ticket; `T-BOUNDARY`.

## Progress Tracker
| SF | Name | Depends On | Design | Impl Plan | Dev | Pre-Commit | Committed |
|----|------|-----------|--------|-----------|-----|------------|-----------|
| SF-01 | Both guards applied | — | ✅ | ✅ | ✅ | ✅ | ✅ |
