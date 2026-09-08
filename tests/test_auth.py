from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from app.auth.basic_auth import get_current_username
from app.config import Settings, get_settings


def _client(settings: Settings) -> TestClient:
    app = FastAPI()
    app.dependency_overrides[get_settings] = lambda: settings

    @app.get("/protected")
    def protected(username: str = Depends(get_current_username)) -> dict[str, str]:
        return {"username": username}

    return TestClient(app)


def test_basic_auth_accepts_configured_credentials(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("OKANE_FINANCE_API_USER", "api-user")
    monkeypatch.setenv("OKANE_FINANCE_API_PASSWORD", "api-password")
    client = _client(Settings())

    response = client.get("/protected", auth=("api-user", "api-password"))

    assert response.status_code == 200
    assert response.json() == {"username": "api-user"}


def test_basic_auth_rejects_wrong_credentials(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("OKANE_FINANCE_API_USER", "api-user")
    monkeypatch.setenv("OKANE_FINANCE_API_PASSWORD", "api-password")
    client = _client(Settings())

    response = client.get("/protected", auth=("api-user", "wrong"))

    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Basic"


def test_basic_auth_reports_missing_server_configuration(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("OKANE_FINANCE_API_USER", raising=False)
    monkeypatch.delenv("OKANE_FINANCE_API_PASSWORD", raising=False)
    client = _client(Settings())

    response = client.get("/protected", auth=("any", "value"))

    assert response.status_code == 500
    assert response.json() == {"detail": "API authentication is not configured"}
