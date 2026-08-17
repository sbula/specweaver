# Design: The MCP Container Boundary Checks a Name, Not a Command

- **Feature ID**: TECH-063
- **Epic**: Topic 07 (Technical Debt)
- **Status**: STUB — not yet run through the `specweaver-design` skill
- **Origin**: found 2026-08-17 by `INT-US-23-MIG` while citing `C-INTL-02` FR-2
- **Severity**: security. Analysis only — **no exploit has been demonstrated**, see Evidence.

## Problem Statement

`MCPAtom.__init__` enforces `C-INTL-02` NFR-2 — *"executions must run through isolated environments
(docker/podman). Bare executable forbidden"* — like this
(`sandbox/mcp/core/atom.py:51-59`):

```python
allowed_executables = {"docker", "podman"}
import sys
executor_target = command[0]
if executor_target not in allowed_executables and executor_target != sys.executable:
    raise ValueError("NFR-2 Boundary Violation: ...")
```

**It inspects `argv[0]` as a string and nothing else.** The command then reaches
`subprocess.Popen(self._command, env=env, stdin=PIPE, stdout=PIPE, text=True)`
(`sandbox/mcp/core/executor.py:37-43`) — raw `Popen`, persistent, bidirectional, with a daemon reader
thread.

### Where the command comes from

Traced end to end, and this is what makes it a security question rather than a hygiene one:

| Step | Site |
|---|---|
| `context.yaml` in the **analysed project** declares `mcp_servers` and `consumes_resources` | topology parse |
| both are read off the topology | `handlers/mcp_assembler.py:105-106` |
| `server_config["command"]` — a string is `shlex.split`, `args` appended | `mcp_assembler.py:74-84` |
| `server_config["env"]` passed through verbatim | `mcp_assembler.py:89` |
| `MCPAtom(command=command, env=env)` | `mcp_assembler.py:30` |
| `Popen(command, env=env)` | `mcp/core/executor.py:37` |

It fires **automatically** during context assembly for review and generation prompts whenever a
topology declares both keys. Nobody has to invoke anything.

## Four consequences, in severity order

**1. `argv[0]` is a name, not a path — and the same config supplies `PATH`.** `env` is returned
verbatim into `Popen(env=...)`, so a config pairing `command: "docker …"` with
`env: {PATH: "/tmp/x"}` and a file named `docker` on that path satisfies the guard completely. The
check validates a *name* while the attacker controls what the name resolves to. **This needs no
widening of the allow-list.**

**2. Arguments are never inspected, so `docker` itself is an escape.**
`docker run --privileged -v /:/host alpine sh -c '…'` passes: `argv[0]` is `docker`. NFR-2's stated
intent is satisfied on paper by a host takeover. Equally `--network host`, or mounting
`/var/run/docker.sock`.

**3. The `sys.executable` carve-out is enforced in production.** Its comment says *"for internal test
infrastructure"*, but the condition runs on every construction. It requires the exact interpreter
path — conventional and discoverable (`.venv/bin/python`).

**4. It bypasses `SubprocessExecutor`.** The documented `TECH-010` exemption, still open: no timeout
escalation and no credential stripping, on a long-lived process.

## Evidence, and its limits

Verified by reading: the guard, the `Popen` call, and every step of the data flow above.

**Not verified:** no exploit was run. Nothing here has been demonstrated end to end, and the
severity rests on `context.yaml` being attacker-influenced.

**That premise is SpecWeaver's own brownfield case**, not a hypothetical: US-12 reverse-weaves
undocumented repositories, US-18 targets an external proprietary system, US-26 sweeps *every*
repository in a fleet, and `E-VAL-03` sits in the routing queue precisely because analysed source is
untrusted input. A repository carrying its own `context.yaml` is the normal condition.

**A reproduction is the first task of this ticket**, before any fix is chosen. A security ticket
argued only from reading is a hypothesis.

## Candidate Approaches (not yet designed)

1. **Resolve the runtime ourselves and ignore config `PATH`.** `shutil.which("docker")` at a trusted
   moment, pass the absolute path, and never let config decide resolution. Addresses (1) directly.
2. **Allow-list the arguments, not just the binary.** Refuse `--privileged`, `--network host`,
   `-v` mounts outside a scratch root, and socket mounts. Addresses (2), and is the part most likely
   to need iteration.
3. **Construct the command ourselves from config *data*.** Config supplies an image name and
   resource URIs; SpecWeaver builds the argv. The strongest option — config stops being a command —
   and the largest change.
4. **Delete the `sys.executable` carve-out** and give tests a seam instead of production a hole.
5. **Route through `SubprocessExecutor`**, which is `TECH-010` and larger than this ticket.

Approach 3 plus 4 is the shape most likely to close the class rather than the instances.

## Non-Goals (proposed, pending design)

- `TECH-010`'s persistent-process executor migration. Related, separately owned, and not required to
  close (1)–(3).
- `E-VAL-03` (AST prompt-injection sanitisation). Different untrusted-input path, same trust premise.
- Broadening `C-INTL-02`'s scope. Its four FRs are cited and mutant-verified; this is the boundary
  behind FR-2, not new capability.

## Guardrail

`test_only_container_runtimes_are_allowed` already pins the allow-list against shells and
interpreters, so it cannot *drift*. That stops regression and addresses none of (1)–(3) — it is
recorded here so the existing test is not mistaken for a fix.
