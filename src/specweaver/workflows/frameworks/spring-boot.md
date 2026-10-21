---
name: Spring Boot
languages: java, kotlin
---
# Code
## Framework: Spring Boot
1. Wire dependencies through constructor injection; never field injection.
2. HTTP endpoints go in `@RestController` classes with `@GetMapping` / `@PostMapping`; they delegate to a `@Service`.
3. Validate request bodies with `@Valid` and Jakarta Bean Validation annotations.
4. Read settings through `@ConfigurationProperties` records, not `@Value` strings.
5. Map errors to HTTP status codes in a `@RestControllerAdvice`.
# Tests
## Framework: Spring Boot
1. Use test slices: `@WebMvcTest(<Controller>.class)` with `MockMvc` for controllers, `@DataJpaTest` for repositories.
2. Replace collaborators of the slice with `@MockitoBean`.
3. Use `@SpringBootTest` only for a test that needs the whole application.
4. Plain services are unit-tested without Spring, through their constructor.
