from fastapi.testclient import TestClient

from main import app


def test_health():
    client = TestClient(app)
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_me_requires_auth():
    client = TestClient(app)
    response = client.get("/v1/me")
    assert response.status_code == 401  # HTTPBearer rejects missing credentials
