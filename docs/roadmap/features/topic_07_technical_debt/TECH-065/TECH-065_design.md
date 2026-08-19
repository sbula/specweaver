# Design: Parameterised Annotations Never Match a Framework Schema

- **Feature ID**: TECH-065
- **Epic**: Topic 07 (Technical Debt)
- **Status**: DELIVERED 2026-08-19
- **Origin**: found 2026-08-18 writing the `INT-US-05` P-4 journey test. Measurements:
  [`docs/analysis/polyglot_dependency_resolution_2026-08-18.md`](../../../../analysis/polyglot_dependency_resolution_2026-08-18.md)

## Problem Statement

`B-INTL-02` (Macro Evaluator, `✅`) exists so an agent reading `@RestController` is told it means
`@Controller` + `@ResponseBody` rather than being left to know Spring Boot. Its FR-2 claims schemas for
"Spring Boot, Quarkus, NestJS, FastAPI, and Actix are evaluated correctly".

**An annotation that carries arguments never matches its schema entry.** The parsers extract the
marker with its argument list attached; every schema key is a bare name.

| Language | Source | Extracted marker | Schema key | Match |
|---|---|---|---|---|
| Java | `@RestController` | `RestController` | `RestController:` | ✅ |
| Java | `@GetMapping("/orders/{id}")` | `GetMapping("/orders/{id}")` | `GetMapping:` | ❌ |
| Rust | `#[get("/orders")]` | `get("/orders")` | `get:` | ❌ |

Measured by driving the packaged schemas through the real tool against real source. The `@RestController`
case unrolls; the `@GetMapping` on the same class does not, and the Actix sample unrolls nothing at all
because both its route decorators take a path.

**This is most of what a framework schema is for.** Routing and mapping annotations nearly always carry
a path or a method. What still works is the argument-less subset — `@RestController`, `@Controller`,
`@ApplicationScoped`, `@Transactional`, `@Inject`, `@Entity`, and JAX-RS `@GET`/`@POST`. Roughly half of
every shipped schema is unreachable.

**Why no test caught it.** The capability's own tests exercise the evaluator with fixture schemas whose
keys match the fixture markers, so both sides agree by construction. The mismatch only appears when the
*shipped* schemas meet a *real* parser, which nothing did until `INT-US-05` P-4.

## Functional Requirements

| # | FR | Actor | Action | Outcome |
|---|-----|-------|--------|---------|
| FR-1 | A marker with arguments finds its schema entry | `SchemaEvaluator` | looks a marker up exactly, then by its bare name | `GetMapping("/orders/{id}")` matches the `GetMapping:` key, and a key that already carries arguments (`derive(Clone)`) keeps its exact meaning |
| FR-2 | The arguments survive the lookup | `SchemaEvaluator` | substitutes the argument text for `>>{args}<<` before template recursion | a schema can say *"HTTP GET /orders/{id}"*, so the path is data rather than something discarded to make the match work |
| FR-3 | The shipped schemas are driven, not fixtures | the integration tier | evaluates `load_evaluator_schemas()` against the marker text parsers really produce | the mismatch between shipped keys and extracted markers is visible to a test, which it was not |

## The decision taken

**Arguments are data.** The ticket named this as the decision worth taking deliberately, and the
cheapest option — strip and discard — would have traded one silent loss for another: a route path is
exactly what an unrolled description should carry. So the lookup normalises and the template keeps
access to what was normalised away.

Approach 3 — normalising at extraction, across all five parsers — is not taken. It is the version
that stops the next consumer repeating this, and it is a change to five parsers' output contract; the
`>>{args}<<` token makes the arguments available without one.

**`>>{args}<<` is substituted before recursion, and that ordering is load-bearing.** `_resolve_template`
resolves `>>{key}<<` against the schema category, so a category defining a key called `args` would
capture the token and the route path would vanish exactly where it was asked for.

## Verified against the shipped schemas

The three cases the ticket measured as broken, driven through `load_evaluator_schemas()`:

```
// [Framework Eval] @Controller\n@ResponseBody          <- RestController      (always worked)
// [Framework Eval] @RequestMapping(method = RequestMethod.GET)   <- GetMapping("/orders/{id}")
// [Framework Eval] @RequestMapping(method = RequestMethod.POST)  <- PostMapping("/orders")
// [Framework Eval] // Actix HTTP GET Route              <- get("/orders")
// [Framework Eval] impl Clone for >>{Target}<< ...      <- derive(Clone)       (exact key)
```

## Verifiable Proof

| FR | Test |
|---|---|
| FR-1 | `tests/unit/sandbox/language/core/language/test_schema_evaluator.py::TestMarkersCarryingArguments` — removing the fallback fails 5; letting the fallback outrank exact match fails 7 |
| FR-2 | the same class — discarding the argument text fails 1 |
| FR-3 | `tests/integration/sandbox/language/test_packaged_schemas_unroll.py` — the real files, the real marker text. Making any marker match anything fails 2, which is what its silence control is for |

## Candidate Approaches (as filed)

- **Normalise the marker before lookup** — strip the argument list, look up the bare name. Smallest
  change; loses the arguments, which some unrollings may want (`>>{Target}<<` templating already
  suggests an appetite for them).
- **Match on a prefix or a declared key pattern** — lets a schema opt into `GetMapping(...)` and keep
  the path available for interpolation. More expressive, more surface.
- **Normalise at extraction instead** — have the parsers return the bare name plus its arguments as
  separate fields, so no consumer has to parse a string. Touches all five parsers, and is the version
  that stops the next consumer repeating this.

**The decision worth taking deliberately is whether arguments are data or noise.** A route path is
exactly the sort of thing an unrolled description should carry (*"HTTP GET /orders/{id}"*), so throwing
it away to make the lookup work may trade one silent loss for another.

## Non-Goals

- **Not** `TECH-064`. That covers polyglot *architecture checks* returning success while doing nothing —
  a different subject in a different capability. The two were deliberately kept apart when this was
  found, rather than folding one into the other to save a ticket.
- **Not** new framework schemas. The shipped five are enough to expose and to verify the fix.
- **Not** `B-SENS-07`'s resolver. Unrelated mechanism, unrelated consumer.

## Verifiable Proof (when this closes)

`tests/e2e/capabilities/sandbox/test_framework_unrolling_reaches_the_agent_e2e.py` already carries the
failing case as a strict `xfail` naming this ticket. When the defect is fixed the marker comes off and
the test stands on its own — that is the whole point of it being strict.
