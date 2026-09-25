# C-INTL-02 SF-01 — Context YAML & Vault Bindings

**Status**: COMPLETED · **Feature ID**: 3.32c · **FRs owned**: FR-1, FR-2, FR-3, FR-4 (proof
recorded here, see As built) · **Depends on**: none · Design:
[C-INTL-02_design.md](C-INTL-02_design.md) §Sub-features → SF-01

## Goal

Put MCP server definitions into the DAG-based `context.yaml` boundaries. Guarantee that the
environment binding (`.specweaver/vault.env`) never leaks credentials to the repository or to logs.

## Where it plugs in

| Fact | Where |
|---|---|
| `context.yaml` is NOT validated via Pydantic. It maps to `TopologyNode` via `ruamel.yaml`. The schema expansion bypasses Pydantic, so the L2 graph does not regress. Pydantic validation migrations: deferred to `Feature 3.32d`. | `src/specweaver/assurance/graph/topology.py` |
| The configuration layer is `pure-logic`: it may not run `subprocess-git` checks from `core/config/`. The Git tracking check runs from the `flow` PipelineRunner through `GitAtom` (Option D Vault Shield). | `src/specweaver/core/flow/engine/runner.py` |

## Changes

1. **Topology fields** (FR-1) · `topology.py` — `TopologyNode` dataclass gains
   `mcp_servers: dict[str, dict] = field(default_factory=dict)` and
   `consumes_resources: list[str] = field(default_factory=list)`. `TopologyGraph.from_project()`
   reads both from the `ruamel.yaml` mapping.
2. **Option D vault verification** · `runner.py` (`PipelineRunner.start()` or the init sequence):
   1. `FileSystemAtom` checks `Path(".specweaver/vault.env").exists()`.
   2. If it exists, run `GitAtom.run(command="ls-files .specweaver/vault.env")`.
   3. A stdout hit means the file is tracked → raise
      `RuntimeError("FATAL: vault.env is currently tracked by Git! Aborting execution to prevent credential leakage.")`.

   The `.exists()` early exit costs ~0ms for projects without MCP: no boot-time regression.

## Tests

| Command | Proves |
|---|---|
| `pytest tests/unit/assurance/graph/test_topology.py` | legacy context files (without `mcp_servers`) raise no `KeyErrors` |
| `pytest tests/unit/core/flow/engine/test_runner.py` with mock `.specweaver/vault.env` files | `GitAtom` aborts the pipeline when the mock reports the file tracked |
| Manual: `sw plan` on a test repo whose `.specweaver/vault.env` is `git add`ed | the pipeline exits immediately |

## Decisions (audit)

- No open questions: Pydantic deferred; Option D fixed; every bound explicit.
- Architecture: no `subprocess` logic inside configuration, so `tach` keeps the DAG compliant.
  Side-effects need `Atoms`; `PipelineRunner` may orchestrate them.
- Files named (`TopologyNode`, `GitAtom`, `PipelineRunner`); no implicit imports. All changes stay
  within Phase 3 scope paths.

## As built

**Since moved** (2026-09-25 check): the vault audit is `verify_vault_security` in
`core/flow/engine/security.py`, called from the runner on run and resume. It uses the `GitAtom`
`is_tracked` intent (`ls-files`) rather than a raw command.

FR proof recorded 2026-08-17 under `specweaver-dev` §3.2c, from `INT-US-23-MIG`. Proof and mutants:

| Test | FRs |
|---|---|
| `tests/unit/core/flow/handlers/test_mcp_assembler.py` | FR-1, FR-3, FR-4 |
| `tests/unit/sandbox/mcp/core/mcp/test_mcp_atom.py` | FR-2 |

FR-2 needed a new test: the container-runtime allow-list could be widened to include `bash` with the
whole suite green, because the guard was only ever asserted to reject *something*.
