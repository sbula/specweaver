# B-INTL-02 SF-02 — Native Core Framework Libraries

**Status**: APPROVED · **FRs owned**: FR-3, FR-5 (tool delegation to the evaluator; cascading
template resolution — recorded 2026-08-17 under `specweaver-dev` §3.2c, from `INT-US-05-SF04-MIG`) ·
**Depends on**: SF-01 · Design: [B-INTL-02_design.md](B-INTL-02_design.md) §Sub-features → SF-02

## Goal

Ship the native YAML evaluation schemas for Java/Kotlin (Spring Boot, Quarkus), TypeScript (NestJS),
Python (FastAPI, Django) and Rust (Actix-Web). They do not explain in English: they **unroll**
meta-annotations into their literal compiler equivalents (e.g. `@RestController` → `@Controller` and
`@ResponseBody`). A static compiler dictionary, so no heavy process spawning (NFR-1).

## Changes

All files go in the evaluator package from SF-01: `src/specweaver/workflows/evaluators/frameworks`.

| [NEW] File | Scope | Mapping | Example |
|------|------|------|------|
| `spring-boot.yaml` | Spring Boot, Spring WebMVC, JPA | meta-annotations → expanded code | `RestController`: `@Controller\n@ResponseBody`; `SpringBootApplication`: `@Configuration\n@EnableAutoConfiguration\n@ComponentScan` |
| `nestjs.yaml` | NestJS | decorators → DI bindings + HTTP endpoints | `Controller: "@Injectable()\n// Binds Express Router Target"` |
| `fastapi.yaml` | FastAPI | dynamic routing | `app.get: "@api_route(method='GET')"` |
| `actix-web.yaml` | Actix-Web | procedural macros → their `impl` expansions | see below |

Actix example: `"derive(Clone)": "impl Clone for >>{Target}<< {\n    fn clone(&self) -> Self\n}"`

`docs/dev_guides/language_support_guide.md` [MODIFY] — add why these meta-annotation graphs are kept
in-repo (no open-source static compiler dictionaries exist) instead of extracted at compile time:
lower latency, static reliability.

## Tests

| File | Case |
|---|---|
| `test_framework_schemas.py` (unit) | `load_evaluator_schemas()` parses every new file with no YAML errors; deep loading works; recursive lookup: `spring-boot` resolves `RestController` to `@Controller` and `@ResponseBody` |
| tool test (FR-3) | asserts the unrolled output, not only `status == "success"` — otherwise the intent could be swapped for plain `read_symbol` with the suite green |
