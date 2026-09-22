"""HTTP client for an external Prowl browser service.

rvx-builds does not embed a browser. When a direct HTTP request cannot get past a
site's bot protection, the request is replayed by Prowl, a separate service that
owns the real browser, its persistent profile and the display, and speaks the
FlareSolverr v1 command envelope over HTTP.

This module is transport and response shaping only. It never imports browser
internals, and it never writes response bodies, headers or credentials to logs or
to raised errors.
"""

from __future__ import annotations

import json
import os
from http.cookiejar import CookieJar
from typing import Any, Final, Self
from urllib.parse import urlsplit

import requests
import turbohtml
from loguru import logger
from requests.cookies import create_cookie
from requests.structures import CaseInsensitiveDict

# Service address used when it runs beside the builder on the same network.
DEFAULT_PROWL_URL: Final[str] = "http://prowl:8191"

# Environment variable overriding DEFAULT_PROWL_URL.
PROWL_URL_ENV: Final[str] = "PROWL_URL"

# FlareSolverr-compatible command endpoint exposed by the service.
PROWL_COMMAND_PATH: Final[str] = "/v1"

# Seconds allowed for reaching the service before a fetch is written off.
PROWL_CONNECT_TIMEOUT: Final[float] = 10.0

# Floor for the read budget so a zero timeout cannot disable the call.
PROWL_MIN_READ_TIMEOUT: Final[float] = 1.0

# Upper bound on a service error message echoed back to the caller.
PROWL_ERROR_MESSAGE_LIMIT: Final[int] = 200

HTTP_STATUS_MIN: Final[int] = 100
HTTP_STATUS_MAX: Final[int] = 599

_ALLOWED_SCHEMES: Final[frozenset[str]] = frozenset({"http", "https"})

#: Headers owned by the browser. The service rejects them, and the browser sets
#: its own values anyway, so they are dropped from the outgoing payload instead
#: of failing the whole fetch.
_BROWSER_OWNED_HEADERS: Final[frozenset[str]] = frozenset(
    {
        "connection",
        "content-encoding",
        "content-length",
        "cookie",
        "expect",
        "host",
        "keep-alive",
        "proxy-authorization",
        "te",
        "trailer",
        "transfer-encoding",
        "upgrade",
    },
)


class ProwlError(Exception):
    """A service call that did not produce a usable solution."""


class ProwlResponse:
    """A service solution shaped for the existing response contract.

    The attribute set mirrors what the rest of the project reads from a
    ``requests``/``curl_cffi`` response: ``status_code``, ``text``, ``headers``
    and ``json()``. The extra ``user_agent``/``cookies`` properties carry the
    browser identity so the direct HTTP session can reuse the clearance the
    browser obtained.
    """

    __slots__ = ("_cookies", "_headers", "_status_code", "_text", "_url", "_user_agent")

    def __init__(  # noqa: PLR0913 - one keyword per response field keeps the adapter explicit
        self: Self,
        *,
        status_code: int,
        text: str,
        headers: dict[str, str] | None = None,
        cookies: list[dict[str, Any]] | None = None,
        user_agent: str | None = None,
        url: str | None = None,
    ) -> None:
        """Store one solution, keeping only cookies that can be replayed."""
        self._status_code = status_code
        self._text = text
        self._headers: CaseInsensitiveDict[str] = CaseInsensitiveDict(headers or {})
        self._cookies = [
            cookie
            for cookie in (cookies or [])
            if isinstance(cookie.get("name"), str) and isinstance(cookie.get("value"), str)
        ]
        self._user_agent = user_agent or None
        self._url = url

    @property
    def status_code(self: Self) -> int:
        """HTTP status of the page the browser loaded."""
        return self._status_code

    @property
    def text(self: Self) -> str:
        """Response body of the page the browser loaded."""
        return self._text

    @property
    def content(self: Self) -> bytes:
        """Response body encoded as UTF-8."""
        return self._text.encode("utf-8", errors="replace")

    @property
    def url(self: Self) -> str | None:
        """Final URL the service reported for the page."""
        return self._url

    @property
    def headers(self: Self) -> CaseInsensitiveDict[str]:
        """Response headers of the page the browser loaded."""
        return self._headers

    @property
    def user_agent(self: Self) -> str | None:
        """User agent the browser used, so direct requests can match it."""
        return self._user_agent

    @property
    def cookies(self: Self) -> list[dict[str, Any]]:
        """Cookies the browser holds for the loaded page."""
        return self._cookies

    def json(self: Self, **kwargs: Any) -> Any:
        """Return the parsed JSON body of the response.

        The service serializes the rendered document, so a JSON endpoint can
        arrive wrapped in the browser's HTML view; both shapes are accepted.

        :raises ValueError: when the body holds no JSON document.
        """
        try:
            return json.loads(self._text, **kwargs)
        except ValueError:
            pass
        payload = turbohtml.parse(self._text).select_one("body > pre")
        if payload is None:
            msg = "Prowl response body does not contain JSON"
            raise ValueError(msg)
        return json.loads(payload.text, **kwargs)

    def __bool__(self: Self) -> bool:
        """Return True, matching how a successful HTTP client object behaves."""
        return True

    def __repr__(self: Self) -> str:
        """Return a diagnostic representation that excludes the body."""
        return f"<ProwlResponse status={self._status_code} url={self._url!r}>"


def resolve_prowl_url(base_url: str | None = None) -> str:
    """Return the normalized service base URL without a trailing slash.

    :raises ValueError: when the configured value is not an absolute http(s)
        URL with a host, which would otherwise produce a malformed endpoint.
    """
    raw = (base_url if base_url is not None else os.environ.get(PROWL_URL_ENV, "")).strip() or DEFAULT_PROWL_URL
    candidate = raw.rstrip("/")
    parts = urlsplit(candidate)
    if (
        parts.scheme not in _ALLOWED_SCHEMES
        or not parts.hostname
        or parts.username is not None
        or parts.password is not None
        or parts.path not in {"", "/"}
        or parts.query
        or parts.fragment
    ):
        msg = f"{PROWL_URL_ENV} must be an absolute http(s) origin without credentials, path, query or fragment"
        raise ValueError(msg)
    return candidate


def build_fetch_payload(
    url: str,
    *,
    timeout_seconds: float,
    headers: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Build the ``request.get`` payload for *url*.

    Browser-owned headers are dropped because the service rejects them. The
    caller's own values are never logged.
    """
    payload: dict[str, Any] = {
        "cmd": "request.get",
        "url": url,
        "maxTimeout": max(1, int(timeout_seconds)) * 1000,
        "returnOnlyCookies": False,
    }
    if headers:
        forwarded = {name: value for name, value in headers.items() if name.lower() not in _BROWSER_OWNED_HEADERS}
        if forwarded:
            payload["headers"] = forwarded
    return payload


def solution_from_envelope(envelope: Any) -> ProwlResponse:
    """Convert a decoded service envelope into a :class:`ProwlResponse`.

    :raises ProwlError: when the envelope reports a failure or is malformed.
    """
    if not isinstance(envelope, dict):
        msg = "Prowl returned a non-object envelope"
        raise ProwlError(msg)

    if envelope.get("status") != "ok":
        reported = envelope.get("message")
        message = reported if isinstance(reported, str) and reported else "the service reported an unspecified failure"
        raise ProwlError(message[:PROWL_ERROR_MESSAGE_LIMIT])

    solution = envelope.get("solution")
    if not isinstance(solution, dict):
        msg = "Prowl returned no solution"
        raise ProwlError(msg)

    raw_status = solution.get("status")
    body = solution.get("response")
    headers = solution.get("headers")
    cookies = solution.get("cookies")
    user_agent = solution.get("userAgent")
    resolved_url = solution.get("url")
    if (
        not isinstance(raw_status, int)
        or isinstance(raw_status, bool)
        or not HTTP_STATUS_MIN <= raw_status <= HTTP_STATUS_MAX
        or not isinstance(body, str)
        or not isinstance(headers, dict)
        or not isinstance(cookies, list)
        or not isinstance(user_agent, str)
        or not isinstance(resolved_url, str)
    ):
        msg = "Prowl returned a malformed solution"
        raise ProwlError(msg)

    return ProwlResponse(
        status_code=raw_status,
        text=body,
        headers={key: value for key, value in headers.items() if isinstance(key, str) and isinstance(value, str)},
        cookies=[cookie for cookie in cookies if isinstance(cookie, dict)],
        user_agent=user_agent,
        url=resolved_url,
    )


def to_cookie_jar(cookies: list[dict[str, Any]]) -> CookieJar:
    """Build a browser cookie jar from service cookie dictionaries."""
    jar = CookieJar()
    for cookie in cookies:
        name = cookie.get("name")
        value = cookie.get("value")
        if not isinstance(name, str) or not isinstance(value, str):
            continue
        domain = cookie.get("domain")
        path = cookie.get("path")
        expires = cookie.get("expires")
        try:
            jar.set_cookie(
                create_cookie(  # type: ignore[no-untyped-call]
                    name=name,
                    value=value,
                    domain=domain if isinstance(domain, str) else "",
                    path=path if isinstance(path, str) and path else "/",
                    expires=int(expires) if isinstance(expires, int | float) and expires > 0 else None,
                    secure=bool(cookie.get("secure")),
                    rest={"HttpOnly": bool(cookie.get("httpOnly"))} if cookie.get("httpOnly") else None,
                ),
            )
        except Exception as error:  # noqa: BLE001 - a single unusable cookie must not fail the fetch
            logger.warning(f"Discarding unusable browser cookie: {type(error).__name__}")
    return jar


def fetch_via_prowl(
    url: str,
    *,
    timeout: float,
    headers: dict[str, str] | None = None,
    base_url: str | None = None,
) -> ProwlResponse | None:
    """Replay *url* through the browser service and return its solution.

    Returns ``None`` for every service-side failure, including a misconfigured
    endpoint, so the caller's retry semantics decide what happens next instead
    of the whole process aborting.
    """
    try:
        endpoint = f"{resolve_prowl_url(base_url)}{PROWL_COMMAND_PATH}"
    except ValueError as error:
        logger.warning(f"Prowl is not configured correctly: {error}")
        return None

    payload = build_fetch_payload(url, timeout_seconds=timeout, headers=headers)
    read_timeout = max(PROWL_MIN_READ_TIMEOUT, float(timeout)) + PROWL_CONNECT_TIMEOUT
    try:
        response = requests.post(
            endpoint,
            json=payload,
            timeout=(PROWL_CONNECT_TIMEOUT, read_timeout),
            headers={"Content-Type": "application/json"},
        )
    except requests.RequestException as error:
        logger.warning(f"Prowl is unreachable: {type(error).__name__}")
        return None

    try:
        envelope = response.json()
    except ValueError:
        logger.warning("Prowl returned a non-JSON response")
        return None

    try:
        return solution_from_envelope(envelope)
    except ProwlError:
        logger.warning("Prowl could not fetch the page")
        return None
