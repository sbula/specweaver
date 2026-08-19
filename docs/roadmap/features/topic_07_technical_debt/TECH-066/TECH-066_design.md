# Design: Contract Drift Analysis Can Never Find Anything

- **Feature ID**: TECH-066
- **Epic**: Topic 07 (Technical Debt)
- **Status**: STUB — not yet run through the `specweaver-design` skill
- **Origin**: found 2026-08-19 giving `US-22` the spanning proof `ADR-005` requires. The story's
  first path could not be tested because there is no chain to test.

## Problem Statement

`A-VAL-01` FR-5 promises *"Compares Code ASTs against Protocol definitions — emits ERRORs on
missing/mismatched signatures"*. The C13 rule that implements it reads two keys from its execution
context, `protocol_schema` and `ast_payload`, and skips when either is absent.

**Nothing in `src/` ever produces `protocol_schema`.** `execute_validation_pipeline` builds a rule's
context from `ast_payload` alone (`executor.py`, `base_context = ast_payload …`), and no pipeline
YAML, handler or step parameter supplies the other key. `C13` is listed in
`workflows/pipelines/validation_code_default.yaml`, so it runs on every code check and takes the
skip branch every time.

**Measured 2026-08-19.** A project with `api.proto` declaring `service Users { rpc GetUser … }` and a
`src/svc.py` containing an unrelated function, checked with
`sw check src/svc.py --level code`:

```
C13  Contract Drift Analysis  SKIP  Missing 'protocol_schema' or …
```

The parsers are real and unit-proven — `A-VAL-01` FR-1 to FR-4 cover OpenAPI, AsyncAPI and `.proto`,
each behind its own test. What is missing is the join between them and validation. FR-5's own unit
test (`test_c13_contract_drift.py`) hands the rule a `protocol_schema` literal, so it proves the
rule against a context that no run constructs.

**Why this is not simply a missing test.** `ADR-005` puts a story's spanning proof in the story, and
`US-22` P-1 is exactly this path. A test written today could only assert the SKIP, which would
record the defect as the intended behaviour. `finished-stories-immutable` also bars adding the
wiring as a new FR on `A-VAL-01`, which is `✅` — hence a ticket.

## Candidate Approaches (not yet designed)

1. **Wire it in the validation handler.** `handlers/validation.py` already assembles `ast_payload`
   from the AST atom; discover protocol files under the project root, parse them through
   `ProtocolSchemaInterface`, and pass the result as a second context key. Follows the shape that is
   already there, and makes C13 live on every code check.
2. **Make it an explicit step parameter.** The pipeline names the contract file, so a project opts
   in per pipeline rather than by file discovery. Narrower blast radius; needs a schema decision on
   how the step declares it.
3. **Descope FR-5.** If contract drift is not wanted at validation tier, delete the row from
   `A-VAL-01`'s FR table so the descoping is visible, and remove C13 from the default pipeline —
   a rule that always skips is worse than an absent one, because a green check reads as a clean
   verdict.

## Non-Goals (proposed, pending design)

- Changing any protocol parser. FR-1 to FR-4 are delivered and proven; only the join is missing.
- Rewriting the C13 comparison logic. Its unit test passes against a hand-built context and the
  comparison itself is not in question.
- The polyglot AST work in `TECH-065`. That ticket is about annotation *arguments* not matching a
  schema key; this one is about the schema never arriving at all.

## Next Step

Run the `specweaver-design` skill. The decision it must take is approach 1 versus 3 — whether
contract drift is a validation-tier concern at all — because approach 2 only makes sense once that
is settled. Whichever is chosen, ship the guardrail with it: a rule that can only ever SKIP in a
real run must be a finding, or this regrows silently the next time a context key is renamed.
