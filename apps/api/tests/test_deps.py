"""Unit tests for app.deps using a fake Supabase client (no network)."""

from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app import deps


class _Result:
    def __init__(self, data):
        self.data = data


class _Query:
    def __init__(self, client):
        self._client = client

    def select(self, *args, **kwargs):
        return self

    def eq(self, *args, **kwargs):
        return self

    def limit(self, *args, **kwargs):
        return self

    def execute(self):
        self._client.executions += 1
        return _Result(self._client.rows)


class _Auth:
    def __init__(self, client):
        self._client = client

    def get_user(self, token):
        if self._client.user_error is not None:
            raise self._client.user_error
        return SimpleNamespace(user=self._client.user)


class FakeClient:
    """Fake Supabase client with configurable rows, user and auth error."""

    def __init__(self, rows=None, user=None, user_error=None):
        self.rows = rows if rows is not None else []
        self.user = user
        self.user_error = user_error
        self.executions = 0
        self.auth = _Auth(self)

    def table(self, name):
        return _Query(self)


def _settings(demo_mode=False, owner="owner-1"):
    return lambda: SimpleNamespace(
        demo_mode=demo_mode,
        demo_owner_user_id=owner,
        supabase_url="x",
        supabase_service_key="y",
    )


@pytest.fixture(autouse=True)
def _reset_cache(monkeypatch):
    monkeypatch.setattr(deps, "_demo_business_id", None)


def test_demo_mode_returns_demo_business_id(monkeypatch):
    client = FakeClient(rows=[{"id": "biz-demo"}])
    monkeypatch.setattr(deps, "get_settings", _settings(demo_mode=True))
    monkeypatch.setattr(deps, "get_supabase_client", lambda: client)
    assert deps.get_current_business_id(None) == "biz-demo"


def test_demo_mode_caches_result(monkeypatch):
    client = FakeClient(rows=[{"id": "biz-demo"}])
    monkeypatch.setattr(deps, "get_settings", _settings(demo_mode=True))
    monkeypatch.setattr(deps, "get_supabase_client", lambda: client)
    assert deps.get_current_business_id(None) == "biz-demo"
    assert deps.get_current_business_id(None) == "biz-demo"
    assert client.executions == 1


def test_demo_mode_empty_owner_raises_500(monkeypatch):
    client = FakeClient(rows=[{"id": "biz-demo"}])
    monkeypatch.setattr(deps, "get_settings", _settings(demo_mode=True, owner=""))
    monkeypatch.setattr(deps, "get_supabase_client", lambda: client)
    with pytest.raises(HTTPException) as exc:
        deps.get_current_business_id(None)
    assert exc.value.status_code == 500


def test_demo_mode_no_business_row_raises_404(monkeypatch):
    client = FakeClient(rows=[])
    monkeypatch.setattr(deps, "get_settings", _settings(demo_mode=True))
    monkeypatch.setattr(deps, "get_supabase_client", lambda: client)
    with pytest.raises(HTTPException) as exc:
        deps.get_current_business_id(None)
    assert exc.value.status_code == 404


def test_non_demo_missing_header_raises_401(monkeypatch):
    client = FakeClient()
    monkeypatch.setattr(deps, "get_settings", _settings(demo_mode=False))
    monkeypatch.setattr(deps, "get_supabase_client", lambda: client)
    with pytest.raises(HTTPException) as exc:
        deps.get_current_business_id(None)
    assert exc.value.status_code == 401


def test_non_demo_non_bearer_header_raises_401(monkeypatch):
    client = FakeClient()
    monkeypatch.setattr(deps, "get_settings", _settings(demo_mode=False))
    monkeypatch.setattr(deps, "get_supabase_client", lambda: client)
    with pytest.raises(HTTPException) as exc:
        deps.get_current_business_id("Basic abc")
    assert exc.value.status_code == 401


def test_non_demo_get_user_raises_401(monkeypatch):
    client = FakeClient(user_error=Exception("bad token"))
    monkeypatch.setattr(deps, "get_settings", _settings(demo_mode=False))
    monkeypatch.setattr(deps, "get_supabase_client", lambda: client)
    with pytest.raises(HTTPException) as exc:
        deps.get_current_business_id("Bearer tok")
    assert exc.value.status_code == 401


def test_non_demo_valid_user_no_business_raises_403(monkeypatch):
    client = FakeClient(rows=[], user=SimpleNamespace(id="user-1"))
    monkeypatch.setattr(deps, "get_settings", _settings(demo_mode=False))
    monkeypatch.setattr(deps, "get_supabase_client", lambda: client)
    with pytest.raises(HTTPException) as exc:
        deps.get_current_business_id("Bearer tok")
    assert exc.value.status_code == 403


def test_non_demo_valid_user_with_business_returns_id(monkeypatch):
    client = FakeClient(rows=[{"id": "biz-42"}], user=SimpleNamespace(id="user-1"))
    monkeypatch.setattr(deps, "get_settings", _settings(demo_mode=False))
    monkeypatch.setattr(deps, "get_supabase_client", lambda: client)
    assert deps.get_current_business_id("Bearer tok") == "biz-42"


def test_get_supabase_client_empty_url_raises_500(monkeypatch):
    monkeypatch.setattr(
        deps,
        "get_settings",
        lambda: SimpleNamespace(
            demo_mode=False,
            demo_owner_user_id="owner-1",
            supabase_url="",
            supabase_service_key="y",
        ),
    )
    with pytest.raises(HTTPException) as exc:
        deps.get_supabase_client()
    assert exc.value.status_code == 500
