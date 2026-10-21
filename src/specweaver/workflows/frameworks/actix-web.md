---
name: Actix-web
languages: rust
---
# Code
## Framework: Actix-web
1. Handlers are `async fn` taking extractors (`web::Json<T>`, `web::Path<T>`, `web::Data<S>`) and returning `impl Responder` or `Result<HttpResponse, E>`.
2. Errors implement `ResponseError`, so a handler returns them with `?`.
3. Shared state goes in `web::Data`; register routes in a `configure(cfg: &mut web::ServiceConfig)` function.
4. Request and response bodies derive `serde::Deserialize` / `Serialize`.
# Tests
## Framework: Actix-web
1. Use `#[actix_web::test]` async tests.
2. Build the app with `actix_web::test::init_service(App::new().configure(configure))` and call it with `actix_web::test::TestRequest`.
3. Assert on the status and the decoded body (`actix_web::test::read_body_json`).
