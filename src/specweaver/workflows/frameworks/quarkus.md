---
name: Quarkus
languages: java, kotlin
---
# Code
## Framework: Quarkus
1. Beans are `@ApplicationScoped`; inject collaborators through the constructor or `@Inject`.
2. HTTP endpoints are Jakarta REST resources: `@Path`, `@GET`, `@POST`, returning DTOs or `Response`.
3. Read settings with `@ConfigMapping` interfaces.
4. Avoid reflection-only tricks; code must work in native mode.
# Tests
## Framework: Quarkus
1. Annotate integration tests with `@QuarkusTest`; call endpoints with REST Assured (`given().when().get(...)`).
2. Replace beans with `@InjectMock`.
3. Plain logic is unit-tested without Quarkus, through its constructor.
