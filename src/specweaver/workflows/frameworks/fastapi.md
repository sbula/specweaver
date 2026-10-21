---
name: FastAPI
languages: python
---
# Code
## Framework: FastAPI
1. Endpoints are functions on an `APIRouter` with `@router.get` / `@router.post`, typed with Pydantic models.
2. Inject collaborators with `Depends(...)`, never module globals.
3. Raise `HTTPException` with a status code for errors.
4. Keep logic in plain functions the endpoints call.
# Tests
## Framework: FastAPI
1. Test endpoints with `fastapi.testclient.TestClient(app)`.
2. Replace dependencies with `app.dependency_overrides[dep] = fake`, and clear them after the test.
3. Plain logic is tested directly, without the client.
