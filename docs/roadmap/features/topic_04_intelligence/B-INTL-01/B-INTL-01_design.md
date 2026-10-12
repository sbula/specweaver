# B-INTL-01 — Archetype-Based Rule Sets

**Status**: Built; `🔧` until the user signs off. · **Feature ID**: 3.29 · **Phase**: 3

| | |
|---|---|
| Reads | the nearest `context.yaml` `archetype` (e.g. `spring-boot`) · the archetype's evaluator schema |
| Touches | `core/flow/handlers/archetype_pipelines.py` · `sw check` · `assurance/validation` (C12, S12) |
| Uses | `B-INTL-02` (the annotations a schema expands) |
| Not here | the edges an IoC container adds at runtime — `B-SENS-08` |

## What it does

A folder's archetype picks the rules its specs and its code are checked by, in `sw check` and in a
pipeline's validate steps alike. A spec gets `validation_spec_<archetype>`. Code gets
`validation_code_<archetype>` when the file is in one of the archetype's languages — the
`supported_languages` of its evaluator schema — and the default rules otherwise, so a Python script
in a Spring folder is not judged as Spring code. The code rules see the file's framework markers
(annotations, supertypes), read by the code-structure parser.

## Decisions

| # | Decision | Rationale |
|---|----------|-----------|
| AD-1 | The flow layer reads the file's structure and markers and hands them to the rules as data | `assurance/` stays free of parsers (`layer_isolation_and_di.md`) |
| AD-2 | One marker rule, `C12`, configured per archetype | no Python wrapper per framework |
| AD-3 | An archetype's languages live in its evaluator schema only `[agreed 2026-10-12]` | one place to say it; the pipeline does not repeat it |

## Functional Requirements

| # | FR | Actor | Action | Outcome |
|---|-----|-------|--------|---------|
| FR-1 | Profile by archetype | `sw check`, validate steps | SHALL check a file by its archetype's pipeline, and by the default one when the archetype has none | rules fit the component without configuration |
| FR-2 | Markers reach the rules | flow layer | SHALL give the code rules the file's framework markers: per symbol, its annotations and supertypes | a rule can see `@RestController` |
| FR-3 | Code bounds | `C12` | SHALL fail a file that lacks a required marker or has a forbidden one, naming the marker; a marker matches with or without `@` | the code has the framework parts its archetype needs |
| FR-4 | Spec bounds | `S12` | SHALL fail a spec that lacks a required section, naming it | the spec has the sections its archetype needs |
| FR-5 | Languages | flow layer | SHALL apply an archetype's code pipeline only to files in its schema's `supported_languages` (none named: any), and refuse an unknown language name `[agreed 2026-10-12]` | Java and Kotlin get the Spring rules; a Python file there gets the default ones |
| FR-6 | `sw check` too | `sw check` | SHALL apply the archetype unless `--pipeline` names a pipeline `[agreed 2026-10-12]` | the command people check with uses the same rules as a run |

## Non-Functional Requirements

| # | NFR | Threshold / Constraint |
|---|-----|----------------------|
| NFR-1 | Architectural purity | `assurance/` imports no parser and no `sandbox/` module |
| NFR-2 | Own archetypes | an archetype SpecWeaver does not ship works from the project's `.specweaver/pipelines/` and `.specweaver/evaluators/` |

## Accepted limits

- Spring Boot code is checked by `C07`, `C09`, `C12` and `C13` only: the other default code rules
  read Python. Java and Kotlin syntax, tests and coverage rules are `D-VAL-03` / `D-VAL-05` work.
- `nestjs` names JavaScript, which has no parser yet.

## Live demo

A project with `svc/context.yaml` saying `archetype: spring-boot`: `sw check
svc/src/Hello.java --level code` passes when `Hello` is annotated `@RestController` and fails
naming the marker when it is not; no Python rule runs. The same with `Hello.kt`. A spec in `svc/`
without `## 2. Boundaries` fails S12 naming it. `--pipeline validation_spec_default` skips the
archetype.

## Sub-features

| SF | Does | FRs | Plan |
|----|------|-----|------|
| SF-01 | Archetype lookup, pipeline choice, payload | FR-1, FR-2, FR-5, FR-6 | [sf01](B-INTL-01_sf01_implementation_plan.md) |
| SF-02 | Framework marker queries per language | FR-2 | [sf02](B-INTL-01_sf02_implementation_plan.md) |
| SF-03 | `C12` and `S12` | FR-3, FR-4 | [sf03](B-INTL-01_sf03_implementation_plan.md) |
