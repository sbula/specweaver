# US-23: Enterprise Tool Extension (MCP) - Integration Contracts

## Base Story Contract (`INT-US-23`)
* **Status:** ⬜ Pending — migration `INT-US-23-MIG` discharged 2026-08-17; no path
  waits on this contract, so closure is a scope decision
* **Integration Description:** US-23 plugs SpecWeaver into a company's internal tools over MCP. Its
only
  closed capability is `C-INTL-02` (MCP Client Architecture); `B-INTL-05` (Dynamic Tool Gating via
  Archetypes) is unbuilt.
* **Verifiable Proof:** P-1 by `check_fr_coverage.py C-INTL-02`, which exits 0 with all four FRs
behind
  killed mutants.

### Path Inventory (`ADR-004`)

| # | Path | Span | Owner | Runnable today | Blocker |
|---|---|---|---|---|---|
| P-1 | `mcp_servers` parsed, server booted in a container, resources fetched, envelope injected | single feature | `C-INTL-02` | yes — **done** | — |
| P-2 | Tool access gated per agent archetype before an MCP call is issued | cross-feature | `B-INTL-05` | retired | `ADR-003` — owned by `B-INTL-05`, which declares this seam as its own FR |
| P-3 | Journey: plug in Jira/Confluence over MCP without writing a Python adapter | cross-feature | `B-INTL-05` | retired | `ADR-003` — owned by `B-INTL-05`, which declares this seam as its own FR |

**One finding, with a security shape.** FR-2 requires the MCP server to boot inside a container
runtime, and the guard rejects anything absent from `{"docker", "podman"}`. Widening that set to
include
`bash` passed the entire suite: the existing test asserted only that *something* was rejected,
leaving
the allow-list itself unpinned. A sandbox boundary able to move silently is worse than one that is
merely untested, so `test_only_container_runtimes_are_allowed` now pins it against shells and
interpreters.

Also recorded: FR-3's prose names a `read_mcp_resource` request while the code calls a
`read_resource`
intent issuing `resources/read`. Same mechanism, different vocabulary — searching for the FR's own
words
finds nothing and reads as absent code, which is how a naming drift can be mistaken for a
`TECH-062`.

**`INT-US-23-MIG` is discharged, and every deferred path now names the ticket that owns it.**
No path waits on this contract. Whether it closes is a scope decision under `ADR-004`, which
reopened the one `CLOSED EMPTY` of this shape: a contract over closed capabilities is not empty
while their cross-feature paths are unproven.

## Sub-Story Add-Ons

* No explicit sub-story contracts defined yet.
