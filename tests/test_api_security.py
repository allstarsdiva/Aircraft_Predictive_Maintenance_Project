from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from src.api.security import APIAccessMiddleware


def client_with_guard(**options):
    app = FastAPI()

    @app.get("/api/health")
    def health():
        return {"status": "ok"}

    @app.post("/api/test")
    async def protected(request: Request):
        return {"size": len(await request.body())}

    app.add_middleware(APIAccessMiddleware, **options)
    return TestClient(app)


def test_shared_api_key_is_required_for_api_but_health_stays_public():
    client = client_with_guard(api_key="test-secret", auth_required=True)

    assert client.get("/api/health").status_code == 200
    assert client.post("/api/test", json={"ok": True}).status_code == 401
    assert client.post("/api/test", headers={"X-API-Key": "wrong"}, json={"ok": True}).status_code == 401
    response = client.post("/api/test", headers={"X-API-Key": "test-secret"}, json={"ok": True})
    assert response.status_code == 200
    assert response.json()["size"] > 0


def test_required_but_unconfigured_api_key_fails_closed():
    client = client_with_guard(api_key=None, auth_required=True)
    response = client.get("/api/test")
    assert response.status_code == 503
    assert "no server key" in response.json()["detail"]


def test_request_body_size_is_limited():
    client = client_with_guard(api_key=None, auth_required=False, max_body_bytes=4)
    response = client.post("/api/test", content=b"12345")
    assert response.status_code == 413


def test_rate_limit_returns_retry_after_and_does_not_block_health():
    client = client_with_guard(api_key=None, auth_required=False, rate_limit_per_minute=1)
    assert client.get("/api/test").status_code == 405
    response = client.get("/api/test")
    assert response.status_code == 429
    assert response.headers["retry-after"] == "60"
    assert client.get("/api/health").status_code == 200

