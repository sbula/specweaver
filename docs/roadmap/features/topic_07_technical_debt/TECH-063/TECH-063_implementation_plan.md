# Implementation Plan: TECH-063

- **Feature ID**: TECH-063
- **Status**: DELIVERED 2026-08-19
- **Commit boundaries**: one

## CB-1 — reproduce, then close

| Task | FR | Change |
|---|---|---|
| T1 | — | Reproduce consequence (1) through the real atom before writing any fix |
| T2 | FR-1 | `_resolved_runtime_command`: resolve the runtime with `shutil.which` against this process's environment, pass the absolute path |
| T3 | FR-2 | `_reject_escaping_arguments`: refuse host namespaces, `--privileged`, `--cap-add`, `--device`, and mounts of `/`, the daemon socket, `/etc`, `/root` |
| T4 | FR-3 | Replace the unconditional `sys.executable` carve-out with `_ALLOW_INTERPRETER`, false in production |
| T5 | FR-3 | Open the seam in three conftests, autouse and documented, for the tests that need a stdio server |

**T1 first, and it is the reason this ticket could be closed rather than argued.** The filing said a
security ticket argued only from reading is a hypothesis. The reproduction turned four consequences
read off the code into one demonstrated bypass and three refusals that can each be mutated.

**Prefix-matching in T3 is deliberate.** `--network=host` and `--network host` are the same request,
and a check written against a whole token lets the first through.
