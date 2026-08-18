# Design: Parameterised Annotations Never Match a Framework Schema

- **Feature ID**: TECH-065
- **Epic**: Topic 07 (Technical Debt)
- **Status**: STUB — not yet run through the `specweaver-design` skill
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

## Candidate Approaches (not yet designed)

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

## Non-Goals (proposed, pending design)

- **Not** `TECH-064`. That covers polyglot *architecture checks* returning success while doing nothing —
  a different subject in a different capability. The two were deliberately kept apart when this was
  found, rather than folding one into the other to save a ticket.
- **Not** new framework schemas. The shipped five are enough to expose and to verify the fix.
- **Not** `B-SENS-07`'s resolver. Unrelated mechanism, unrelated consumer.

## Verifiable Proof (when this closes)

`tests/e2e/capabilities/sandbox/test_framework_unrolling_reaches_the_agent_e2e.py` already carries the
failing case as a strict `xfail` naming this ticket. When the defect is fixed the marker comes off and
the test stands on its own — that is the whole point of it being strict.
