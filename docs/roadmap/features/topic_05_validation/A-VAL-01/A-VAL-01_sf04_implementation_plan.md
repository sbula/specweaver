# A-VAL-01 SF-04 — Contract Drift Validation Rules

**Status**: APPROVED · **FRs owned**: FR-5 · **Depends on**: SF-03 · **Legacy Feature ID**: 3.31 ·
Design: [A-VAL-01_design.md](A-VAL-01_design.md) §Sub-features → SF-04

FR attribution added 2026-08-16 by `TECH-051` CB-2: the plan predates the FR ledger, so
`check_fr_coverage.py A-VAL-01` reported all five as *carried by no implementation plan* on a delivered
DAL-A capability. Mapped from this sub-feature's own scope — the C13 contract-drift rule — not assigned
to make a number fall. The work is unchanged.

## Goal

`c13_contract_drift.py` compares code structure paths (extracted from backend Python/TS) with the
expected `ProtocolEndpoint` set passed in through context from the schema tools.

## Changes

1. **[NEW] `src/specweaver/assurance/validation/rules/code/c13_contract_drift.py`** — matches the
   schemas in `self.context.get("protocol_schema")` against detected framework routers.
   - Needs context: if `self.context` does not carry `ast_payload`, returns `Status.SKIP`.
   - Emits a `DriftFinding` for every `ProtocolEndpoint` in the YAML or Proto with no matching
     tree-sitter routing node.
2. **[MODIFY] `src/specweaver/assurance/validation/rules/code/context.yaml`** — declare
   `C13ContractDriftRule` in `exposes:` so registry lookup does not fail.
3. **[MODIFY] `src/specweaver/assurance/validation/rules/code/register.py`** — import and register
   `C13ContractDriftRule`.

**Dependency constraint:** L2 pure-logic validation `forbids: specweaver/loom/*`, so C13 never
instantiates parsers; it relies only on the `rule.context` `ast_payload` dictionary.

## Tests

| Test | Checks |
|---|---|
| `test_c13_contract_drift.py` | dummy `ProtocolEndpoint` contexts; matching router stubs → `Status.PASS`; missing paths → `Status.FAIL` |
| Manual | dummy pipeline tests cascade the SF-03 Atom payloads down to validation `step.params` |

## As built

Committed `b3037104` (2026-04-18). C13 is registered as `"C13"` in `register.py`. It skips when
`protocol_schema` or `ast_payload` is missing. `core/flow/handlers/validation_hydrator.py` fills
`protocol_schema` through `ProtocolAtom`.
