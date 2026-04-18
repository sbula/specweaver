# Implementation Plan: Macro & Annotation Evaluator [SF-2: Native Core Framework Libraries]

- **Feature ID**: 3.30
- **Sub-Feature**: SF-2 — Native Core Framework Libraries
- **Design Document**: docs/roadmap/phase_3/feature_3.30/feature_3.30_design.md
- **Design Section**: §Sub-Feature Breakdown → SF-2
- **Implementation Plan**: docs/roadmap/phase_3/feature_3.30/feature_3.30_sf2_implementation_plan.md
- **Status**: APPROVED

## 1. Goal

Implement the native ecosystem YAML Evaluation schemas covering major framework lifecycles for Java/Kotlin (Spring Boot, Quarkus), TypeScript (NestJS), Python (FastAPI, Django), and Rust (Actix-Web). Instead of outputting english explanations, these declarative mapping schemas will **unroll** complex meta-annotations into their deterministic, literal compiler-equivalent counterparts (e.g., `@RestController` unrolls into `@Controller` and `@ResponseBody`). This effectively serves as a static compiler dictionary proxy, resolving NFR-1 limits on heavy runtime process spawning.

## 2. Proposed Changes

All files will be created inside the core evaluator static package boundary established in SF-1.

### `src/specweaver/workflows/evaluators/frameworks` (The Unroller Dictionary)

#### [NEW] `spring-boot.yaml`
- **Scope**: Spring Boot, Spring WebMVC, JPA.
- **Mapping Strategy**: Converts meta-annotations to standard expanded code.
- **Decorators Example**: 
  - `RestController`: `@Controller\n@ResponseBody`
  - `SpringBootApplication`: `@Configuration\n@EnableAutoConfiguration\n@ComponentScan`

#### [NEW] `nestjs.yaml`
- **Scope**: NestJS.
- **Mapping Strategy**: Decodes NestJS decorators into expanded DI bindings and HTTP endpoints.
- **Decorators Example**: `Controller: "@Injectable()\n// Binds Express Router Target"`

#### [NEW] `fastapi.yaml`
- **Scope**: FastAPI.
- **Mapping Strategy**: Decodes dynamic framework routing boundaries.
- **Decorators Example**: `app.get: "@api_route(method='GET')"`

#### [NEW] `actix-web.yaml`
- **Scope**: Actix-Web.
- **Mapping Strategy**: Translates common procedural macros to their `impl` expansions.
- **Decorators Example**: `"derive(Clone)": "impl Clone for >>{Target}<< {\n    fn clone(&self) -> Self\n}"`

### `docs/dev_guides/language_support_guide.md`
#### [MODIFY]
- **Documentation Step**: As requested, append a specific design rationale explaining *why* we maintain these meta-annotation graphs natively (lack of open-source static compiler dictionaries) rather than extracting them dynamically at compile time, explicitly referencing latency reduction and static reliability.

## 3. Verification Plan

### Automated Tests
1. **Unit Tests in `test_framework_schemas.py`**:
   - Programmatically invoke `load_evaluator_schemas()` to parse all the new files.
   - Assert that no YAML parsing errors occur and that deep dictionary loading executes flawlessly.
   - Verify specific recursive lookups (e.g., `spring-boot` successfully resolves `RestController` to `@Controller` and `@ResponseBody`).
