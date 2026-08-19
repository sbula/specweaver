# Delivery Record: Integration Migration to (Sub)Story Path Inventories

- **Feature ID**: TECH-060
- **Epic**: Topic 07 (Technical Debt)
- **Status**: DELIVERED — ledger closed out here, 26 of 27 discharged

## The `-MIG` ledger

`ADR-004`: a (sub)story holding closed features owns an integration story for them. These 27 place
every path into the new structure — feature, inventory row, or deferred row — and are then
discharged. Ordered by capability cluster, so a shared seam is decided once with every claimant
visible.

The ledger lives here rather than in `master_story_roadmap.md`. A discharged row is a record of work
done, and the roadmap holds the state of open registry IDs — so the one row still open is quoted
there and the other 26 are read here. `TECH-060` FR-2 named the roadmap as the registry's surface;
that was true while the batch was the active work list, and the FR's stated outcome — trackable in
one place, removable in one edit — is what this document keeps.

| Cluster | Migration | Story | Sub-story / contract | Closed capabilities |
|---|---|---|---|---|
| B-SENS-02 (6) | `✅` `INT-US-10-MIG` | US-10 | Monolith Dependency Visualizer | `B-SENS-02` |
|  | `✅` `INT-US-11-MIG` | US-11 | GraphRAG for Brownfield Scale | `B-SENS-02` |
|  | `✅` `INT-US-12-MIG` | US-12 | Legacy Spec Extraction | `B-SENS-02` |
|  | `✅` `INT-US-15-MIG` | US-15 | Enterprise Audit & Traceability | `B-SENS-02` |
|  | `✅` `INT-US-26-MIG` | US-26 | Fleet-Wide CVE Remediation | `B-SENS-02` |
|  | `✅` `INT-US-27-MIG` | US-27 | Autonomous Production Self-Healing | `B-SENS-02` |
| A-SENS-01 (2) | `✅` `INT-US-11-SF01-MIG` | US-11 | Infinite Scale Management | `A-SENS-01` |
|  | `✅` `INT-US-19-SF01-MIG` | US-19 | Distributed Topology Scaling | `A-SENS-01` |
| C-FLOW-02 (2) | `✅` `INT-US-06-MIG` | US-6 | Remote Dashboard | `C-FLOW-02`, `E-UI-02` |
|  | `✅` `INT-US-07-MIG` | US-7 | IDE Copilot | `C-FLOW-02` |
| C-FLOW-03 (2) | `✅` `INT-US-18-MIG` | US-18 | Productionizing External Targets | `C-FLOW-03` |
|  | `✅` `INT-US-19-MIG` | US-19 | Microservice Fleet Orchestration | `C-FLOW-03`, `B-SENS-02` |
| singletons (15) | `✅` `INT-US-08-MIG` | US-8 | Greenfield Bootstrap Wizard | `D-SENS-01` |
|  | `✅` `INT-US-20-MIG` | US-20 | Enterprise Architecture Enforcement | `D-SENS-01`, `B-SENS-02`, `C-EXEC-01` |
|  | `✅` `INT-US-22-MIG` | US-22 | Polyglot Contract Enforcement | `A-VAL-01`, `C-VAL-04` |
|  | `✅` `INT-US-23-MIG` | US-23 | Enterprise Tool Extension (MCP) | `C-INTL-02` |
|  | `✅` `INT-US-01-SF02-MIG` | US-1 | Enforce Internal Architecture | `C-EXEC-01`, `C-EXEC-03` |
|  | `✅` `INT-US-01-SF03-MIG` | US-1 | Configurable Multi-Stage Reviews | `E-VAL-02`, `B-VAL-02` |
|  | `✅` `INT-US-03-SF01-MIG` | US-3 | Multi-Language Test Support | `D-VAL-03` |
|  | `✅` `INT-US-04-SF05-MIG` | US-4 | Advanced Routing & Conditional Flows | `C-FLOW-05` |
|  | `🔵` `INT-US-09-SF01-MIG` | US-9 | Containerized Isolation — HELD, needs `B-EXEC-01`'s FRs cited against the container path | `D-EXEC-01`, `B-EXEC-01` |
|  | `✅` `INT-US-10-SF01-MIG` | US-10 | Code-to-Spec Drift Checking | `B-VAL-01` |
|  | `✅` `INT-US-15-SF01-MIG` | US-15 | Enterprise Compliance Protocols | `B-SENS-01` |
|  | `✅` `INT-US-25-SF01-MIG` | US-25 | Dynamic Risk Controls | `D-VAL-02`, `D-VAL-04`, `C-VAL-03` |
|  | `✅` `INT-US-05-SF03-MIG` | US-5 | Intelligent Code Exclusions | `C-SENS-02` |
|  | `✅` `INT-US-05-SF04-MIG` | US-5 | Framework Native Understanding | `B-INTL-02` |
|  | `✅` `INT-US-21-SUB-MIG` | US-21 | Recursive Planning | `C-INTL-01` |


## Exit

The section leaves the roadmap when every row is discharged, not row by row — a half-migrated
registry is the state that most needs to be visible. One row remains: `INT-US-09-SF01-MIG` is held,
and its blocker is named on its roadmap line.
