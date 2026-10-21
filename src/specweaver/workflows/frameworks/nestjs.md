---
name: NestJS
languages: typescript
---
# Code
## Framework: NestJS
1. Put logic in an `@Injectable()` provider; inject it through the constructor.
2. HTTP endpoints go in a `@Controller()` class with `@Get()` / `@Post()`; they delegate to the provider.
3. Validate input with DTO classes and `class-validator` decorators.
4. Register controllers and providers in a `@Module()`.
5. Throw `HttpException` subclasses (`NotFoundException`, `BadRequestException`) for errors.
# Tests
## Framework: NestJS
1. Build the unit under test with `Test.createTestingModule({ providers: [...] }).compile()` and `module.get(...)`.
2. Replace collaborators with `{ provide: X, useValue: mock }`.
3. Test HTTP endpoints with `supertest` against `app.getHttpServer()`.
