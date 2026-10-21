"""The API's rate limit: /health is never limited, the claim endpoints are, with Retry-After."""
import pytest
from fastapi.testclient import TestClient

from app import main
from app.config import get_settings

CLAIM = {"question": "What is the time limit for claiming an FP57 refund?"}


@pytest.fixture
def client(monkeypatch, tmp_path):
    monkeypatch.setenv("DATABASE_URL", f"sqlite+aiosqlite:///{(tmp_path / 'rl.db').as_posix()}")
    monkeypatch.setenv("PLANNER_BACKEND", "reference")
    monkeypatch.setenv("GROQ_API_KEY", "")
    monkeypatch.setenv("API_BASIC_AUTH_USER", "ui")
    monkeypatch.setenv("API_BASIC_AUTH_PASSWORD", "secret")
    monkeypatch.setenv("RATE_LIMIT_PER_MINUTE", "3")
    monkeypatch.setenv("RATE_LIMIT_GLOBAL_PER_MINUTE", "5")
    get_settings.cache_clear()
    main._hits.clear()
    with TestClient(main.app) as c:
        yield c
    get_settings.cache_clear()
    main._hits.clear()


def info(client, visitor=None, auth=("ui", "secret")):
    headers = {main.VISITOR_HEADER: visitor} if visitor else {}
    return client.post("/info", json=CLAIM, auth=auth, headers=headers)


def test_health_is_never_rate_limited(client):
    for _ in range(200):
        assert client.get("/health").status_code == 200
    assert client.head("/health").status_code == 200
    assert info(client).status_code == 200  # and it spent none of the claim allowance


def test_claims_past_the_limit_get_429_with_retry_after(client):
    for _ in range(5):
        assert info(client).status_code == 200
    r = info(client)
    assert r.status_code == 429
    assert 1 <= int(r.headers["Retry-After"]) <= 60
    r = client.post("/claims", json={}, auth=("ui", "secret"))  # the shared bucket covers /claims too
    assert r.status_code == 429 and "Retry-After" in r.headers


def test_one_visitor_cannot_spend_everyones_allowance(client):
    for _ in range(3):
        assert info(client, "203.0.113.1").status_code == 200
    r = info(client, "203.0.113.1")
    assert r.status_code == 429 and "Retry-After" in r.headers
    assert info(client, "203.0.113.2").status_code == 200  # another visitor still gets through


def test_visitor_header_needs_valid_auth(client):
    assert info(client, "203.0.113.1", auth=("ui", "wrong")).status_code == 401
    assert not any(k.startswith("visitor:") for k in main._hits)
