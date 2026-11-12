"""Auth on the config web UI (config_v2.web)."""

import base64

import pytest
from fastapi.testclient import TestClient

from config_v2 import web


def _basic(user: str, password: str) -> dict:
    token = base64.b64encode(f"{user}:{password}".encode()).decode()
    return {"Authorization": f"Basic {token}"}


@pytest.fixture
def client():
    # Static files are served without hitting the config DB, so they exercise only the middleware
    return TestClient(web.app)


def test_without_password_remote_requests_are_locked(client, monkeypatch):
    monkeypatch.delenv("CONFIG_WEB_PASSWORD", raising=False)

    response = client.get("/static/does-not-exist.css")

    assert response.status_code == 403
    assert "CONFIG_WEB_PASSWORD" in response.text


def test_without_password_loopback_is_allowed(client, monkeypatch):
    monkeypatch.delenv("CONFIG_WEB_PASSWORD", raising=False)
    monkeypatch.setattr(web, "_is_loopback", lambda host: True)

    assert client.get("/static/does-not-exist.css").status_code == 404


@pytest.mark.parametrize("headers", [
    {},
    _basic("admin", "wrong"),
    _basic("someone", "s3cret"),
    {"Authorization": "Basic not-base64!!"},
    {"Authorization": "Bearer s3cret"},
])
def test_password_set_rejects_bad_credentials(client, monkeypatch, headers):
    monkeypatch.setenv("CONFIG_WEB_PASSWORD", "s3cret")
    monkeypatch.setattr(web, "_is_loopback", lambda host: True)  # loopback gets no bypass

    response = client.get("/static/does-not-exist.css", headers=headers)

    assert response.status_code == 401
    assert response.headers["www-authenticate"].startswith("Basic ")


def test_password_set_accepts_correct_credentials(client, monkeypatch):
    monkeypatch.setenv("CONFIG_WEB_PASSWORD", "s3cret")
    monkeypatch.setenv("CONFIG_WEB_USER", "max")

    response = client.get("/static/does-not-exist.css", headers=_basic("max", "s3cret"))

    assert response.status_code == 404


def test_is_loopback():
    assert web._is_loopback("127.0.0.1") and web._is_loopback("::1")
    assert not web._is_loopback("172.18.0.1") and not web._is_loopback("testclient")
    assert not web._is_loopback(None)
