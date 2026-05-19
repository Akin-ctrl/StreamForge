from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import Response
from starlette.requests import Request

from app.core.security import extract_user_token
from app.core.settings import settings
from app.routers.auth import apply_user_auth_cookie, clear_user_auth_cookie


def build_request(*, cookie_header: str | None = None) -> Request:
    headers: list[tuple[bytes, bytes]] = []
    if cookie_header is not None:
        headers.append((b"cookie", cookie_header.encode("utf-8")))
    return Request({"type": "http", "headers": headers})


def test_extract_user_token_prefers_bearer_header() -> None:
    request = build_request(cookie_header=f"{settings.auth_cookie_name}=cookie-token")

    assert extract_user_token(request, "bearer-token") == "bearer-token"


def test_extract_user_token_falls_back_to_cookie() -> None:
    request = build_request(cookie_header=f"{settings.auth_cookie_name}=cookie-token")

    assert extract_user_token(request, None) == "cookie-token"


def test_extract_user_token_returns_none_without_bearer_or_cookie() -> None:
    request = build_request()

    assert extract_user_token(request, None) is None


def test_apply_user_auth_cookie_sets_http_only_cookie(monkeypatch) -> None:
    monkeypatch.setattr(settings, "auth_cookie_name", "sf_user_session")
    monkeypatch.setattr(settings, "auth_cookie_domain", "")
    monkeypatch.setattr(settings, "auth_cookie_samesite", "lax")
    monkeypatch.setattr(settings, "auth_cookie_secure", False)

    response = Response()
    apply_user_auth_cookie(
        response,
        "token-value",
        datetime.now(timezone.utc) + timedelta(hours=12),
    )

    set_cookie = response.headers["set-cookie"]
    assert "sf_user_session=token-value" in set_cookie
    assert "HttpOnly" in set_cookie
    assert "Path=/" in set_cookie
    assert "SameSite=lax" in set_cookie


def test_apply_user_auth_cookie_respects_secure_cookie_and_domain(monkeypatch) -> None:
    monkeypatch.setattr(settings, "auth_cookie_name", "sf_user_session")
    monkeypatch.setattr(settings, "auth_cookie_domain", "streamforge.test")
    monkeypatch.setattr(settings, "auth_cookie_samesite", "strict")
    monkeypatch.setattr(settings, "auth_cookie_secure", True)

    response = Response()
    apply_user_auth_cookie(
        response,
        "token-value",
        datetime.now(timezone.utc) + timedelta(hours=12),
    )

    set_cookie = response.headers["set-cookie"]
    assert "Secure" in set_cookie
    assert "Domain=streamforge.test" in set_cookie
    assert "SameSite=strict" in set_cookie


def test_clear_user_auth_cookie_expires_cookie(monkeypatch) -> None:
    monkeypatch.setattr(settings, "auth_cookie_name", "sf_user_session")
    monkeypatch.setattr(settings, "auth_cookie_domain", "")
    monkeypatch.setattr(settings, "auth_cookie_samesite", "lax")
    monkeypatch.setattr(settings, "auth_cookie_secure", False)

    response = Response()
    clear_user_auth_cookie(response)

    set_cookie = response.headers["set-cookie"]
    assert "sf_user_session=" in set_cookie
    assert "Max-Age=0" in set_cookie
