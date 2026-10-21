---
name: Spring
languages: java, kotlin
---
# Code
## Framework: Spring
1. Wire dependencies through constructor injection; never field injection.
2. Mark services `@Service`, data access `@Repository`, configuration `@Configuration` with `@Bean` methods.
3. Keep business logic in plain classes the container creates; no static state.
4. Use `@Transactional` on service methods that change data.
# Tests
## Framework: Spring
1. Unit-test classes directly, passing their collaborators to the constructor (mocks with Mockito).
2. For wiring, use `@ExtendWith(SpringExtension.class)` with `@ContextConfiguration` of the classes under test only.
3. Never start the whole application context for a unit test.
