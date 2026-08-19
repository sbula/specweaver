# Implementation Plan: TECH-066

- **Feature ID**: TECH-066
- **Status**: DELIVERED 2026-08-19
- **Commit boundaries**: one

## CB-1 — find the contract, and give the rule both keys

| Task | FR | Change |
|---|---|---|
| T1 | FR-1 | `discover_protocol_endpoints`: walk the project root, sniff YAML for a schema marker, read `.proto` by suffix |
| T2 | FR-1 | Parse through `ProtocolAtom`, not the parser factory — the factory is not part of `sandbox`'s public interface, and `tach` says so |
| T3 | FR-2 | Hydrate `ast_payload` as a KEY of the rule context, which nothing did on either path |
| T4 | FR-2 | Read the structure with a project-relative path; an absolute one is rejected as traversal and exports `{}` |
| T5 | FR-2 | The e2e: drift, the endpoint named, the aligned control, and the honest SKIP |

**T5 was written first and failed on three of four.** The fourth — a project declaring no contract
still skips — passed from the start, which is what distinguishes the defect from "C13 skips": it
skipped when a contract *was* there.

**Why T3 was not in the filing.** The ticket measured one missing key. The second only appears when
the rule is actually reached, and reaching it needed the first.
