# Design: Contract Drift Analysis Can Never Find Anything

- **Feature ID**: TECH-066
- **Epic**: Topic 07 (Technical Debt)
- **Status**: DELIVERED 2026-08-19
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

## Functional Requirements

| # | FR | Actor | Action | Outcome |
|---|-----|-------|--------|---------|
| FR-1 | A declared contract is found and parsed | The code-validation hydrator | walks the project root for `.proto` files and YAML carrying an `openapi:`, `swagger:` or `asyncapi:` marker | the endpoints they declare are in the rule context, so `C13` has something to compare against |
| FR-2 | The comparison reaches a verdict | `C13` | compares those endpoints against the code's own structure | an endpoint the code does not carry is an ERROR naming it, code that binds it passes, and a project declaring no contract still skips |

## What the fix actually was

Approach 1 as filed, with one thing the filing did not know: **two** keys were missing, not one.
`C13` reads `protocol_schema` *and* `ast_payload`, and the executor makes a step's payload *be* the
rule context rather than a member of it — so `ast_payload` existed as the context and never as a key
inside it. Supplying only the schema left the rule skipping for the other half.

Both are hydrated in the one place both entry points pass through, so `sw check` and the pipeline
behave the same. The code structure is read through `CodeStructureAtom` with a **project-relative**
path: an absolute one is rejected as traversal, and a rejected read exports `{}` — indistinguishable
from a file with no structure.

The scope question the filing raised — *does contract drift belong at validation tier?* — answered
itself. `C13` already ships enabled in `validation_code_default.yaml`; that decision was taken when
the rule was added, and the defect was never scope but wiring.

## What is knowingly not covered

**`C13` compares an endpoint's path literally.** That suits a path-based contract, where the route
appears in a decorator the AST carries. It cannot confirm a gRPC method is implemented —
`Users/GetUser` is a name the code never has to spell — so a `.proto` can raise drift and can never
clear it. The e2e uses OpenAPI for the pass/fail pair for that reason and says so. Making the gRPC
side symmetric means matching on service and method rather than a path, which is a change to the
rule's comparison and its own piece of work.

**Discovery is bounded** to three directory levels and skips vendored trees. A contract nested deeper
is not found, and a project that keeps one there gets the honest SKIP rather than a wrong verdict.

## Verifiable Proof

| FR | Test |
|---|---|
| FR-1 | `tests/e2e/capabilities/assurance/test_contract_drift_reaches_the_check_e2e.py` — emptying discovery fails 4 of 5; removing the YAML markers fails 3 |
| FR-2 | the same file — the aligned control, the named-endpoint assertion, and the honest SKIP. Blanking the AST payload or handing the atom an absolute path each fail one |

## Candidate Approaches (as filed)

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

## Non-Goals

- Changing any protocol parser. FR-1 to FR-4 are delivered and proven; only the join is missing.
- Rewriting the C13 comparison logic. Its unit test passes against a hand-built context and the
  comparison itself is not in question.
- The polyglot AST work in `TECH-065`. That ticket is about annotation *arguments* not matching a
  schema key; this one is about the schema never arriving at all.

## Delivery

Delivered 2026-08-19, same day as filing. The guardrail the stub asked for is
`TECH-064`'s `test_architecture_check_honesty.py` in spirit and this ticket's own honest-SKIP test in
practice: SKIP stays reachable and asserted, so a future rename that breaks the wiring shows up as
the pass case failing rather than as silence.
