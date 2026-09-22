"""Tests for the Prowl browser-service client and its retry integration."""

# ruff: noqa: PT009

from typing import Any, Self, cast
from unittest import TestCase
from unittest.mock import patch

import pytest
import requests
from requests import Session
from requests.cookies import create_cookie

from src import utils
from src.prowl_client import (
    DEFAULT_PROWL_URL,
    PROWL_ERROR_MESSAGE_LIMIT,
    ProwlError,
    ProwlResponse,
    build_fetch_payload,
    fetch_via_prowl,
    resolve_prowl_url,
    solution_from_envelope,
    to_cookie_jar,
)
from src.utils import make_request

_OK = 200
_FORBIDDEN = 403
_URL = "https://example.test/app"


def _ok_envelope(*, body: str = "<html></html>") -> dict[str, Any]:
    """Build a successful service envelope for the given response body."""
    return {
        "status": "ok",
        "message": "",
        "solution": {
            "url": _URL,
            "status": _OK,
            "headers": {"Content-Type": "text/html"},
            "response": body,
            "cookies": [
                {
                    "name": "cf_clearance",
                    "value": "token",
                    "domain": ".example.test",
                    "path": "/",
                    "secure": True,
                    "httpOnly": True,
                },
            ],
            "userAgent": "ua-test",
        },
    }


class _StubHttpResponse:
    """Requests-like response double that returns a canned payload."""

    def __init__(self: Self, payload: Any) -> None:
        """Store the payload or the exception the transport should raise."""
        self._payload = payload

    def json(self: Self) -> Any:
        """Return the canned payload, raising it when it is an exception."""
        if isinstance(self._payload, Exception):
            raise self._payload
        return self._payload


class _DirectResponse:
    """curl_cffi-like direct response double for the non-browser path."""

    def __init__(self: Self, status_code: int) -> None:
        """Store the status code ``make_request`` inspects."""
        self.status_code = status_code
        self.text = "direct"


class ProwlUrlTests(TestCase):
    """Verify the service URL is validated and normalized."""

    def test_default_url_used_when_unset(self: Self) -> None:
        """An empty configuration falls back to the in-network default."""
        self.assertEqual(resolve_prowl_url(""), DEFAULT_PROWL_URL)

    def test_env_override_is_used(self: Self) -> None:
        """The environment variable overrides the built-in default."""
        with patch.dict("os.environ", {"PROWL_URL": "http://prowl.internal:9000"}):
            self.assertEqual(resolve_prowl_url(), "http://prowl.internal:9000")

    def test_trailing_slash_and_whitespace_are_stripped(self: Self) -> None:
        """A padded or slash-terminated value still yields one clean endpoint."""
        self.assertEqual(resolve_prowl_url("  http://prowl:8191/  "), "http://prowl:8191")

    def test_malformed_url_is_rejected(self: Self) -> None:
        """Values that cannot form a safe service origin are rejected."""
        candidates = (
            "prowl:8191",
            "ftp://prowl:8191",
            "http://",
            "://prowl",
            "http://user:secret@prowl:8191",
            "http://prowl:8191/path",
            "http://prowl:8191?query=secret",
            "http://prowl:8191#fragment",
        )
        for candidate in candidates:
            with self.subTest(candidate=candidate), pytest.raises(ValueError, match="must be an absolute") as raised:
                resolve_prowl_url(candidate)
            self.assertNotIn("secret", str(raised.value))


class ProwlPayloadTests(TestCase):
    """Verify the outgoing command envelope."""

    def test_payload_uses_get_command_and_millisecond_timeout(self: Self) -> None:
        """A fetch is a ``request.get`` with the timeout converted to milliseconds."""
        payload = build_fetch_payload(_URL, timeout_seconds=60)
        self.assertEqual(payload["cmd"], "request.get")
        self.assertEqual(payload["url"], _URL)
        self.assertEqual(payload["maxTimeout"], 60000)
        self.assertFalse(payload["returnOnlyCookies"])
        self.assertNotIn("headers", payload)

    def test_browser_owned_headers_are_dropped(self: Self) -> None:
        """Headers the browser owns are filtered out instead of failing the call."""
        payload = build_fetch_payload(
            _URL,
            timeout_seconds=60,
            headers={"User-Agent": "ua", "Cookie": "a=b", "Host": "example.test"},
        )
        self.assertEqual(payload["headers"], {"User-Agent": "ua"})

    def test_non_positive_timeout_still_sends_a_positive_budget(self: Self) -> None:
        """A zero timeout cannot produce a budget the service would reject."""
        self.assertEqual(build_fetch_payload(_URL, timeout_seconds=0)["maxTimeout"], 1000)


class ProwlSolutionTests(TestCase):
    """Verify envelope validation and response conversion."""

    def test_solution_converts_to_the_response_contract(self: Self) -> None:
        """A successful envelope exposes the attributes callers already read."""
        response = solution_from_envelope(_ok_envelope())
        self.assertEqual(response.status_code, _OK)
        self.assertEqual(response.text, "<html></html>")
        self.assertEqual(response.content, b"<html></html>")
        self.assertEqual(response.headers["content-type"], "text/html")
        self.assertEqual(response.user_agent, "ua-test")
        self.assertEqual(response.url, _URL)
        self.assertTrue(response)

    def test_json_parses_a_direct_body(self: Self) -> None:
        """A body that is already JSON is parsed as-is."""
        self.assertEqual(solution_from_envelope(_ok_envelope(body='{"a": 1}')).json(), {"a": 1})

    def test_json_parses_an_html_wrapped_body(self: Self) -> None:
        """A JSON endpoint rendered as a document is unwrapped."""
        envelope = _ok_envelope(body='<html><body><pre>{"a": 2}</pre></body></html>')
        self.assertEqual(solution_from_envelope(envelope).json(), {"a": 2})

    def test_json_raises_for_a_body_without_json(self: Self) -> None:
        """A body holding no JSON document is reported, not silently empty."""
        with pytest.raises(ValueError, match="does not contain JSON"):
            solution_from_envelope(_ok_envelope(body="<html>nope</html>")).json()

    def test_error_envelope_is_reported(self: Self) -> None:
        """A failure envelope becomes a ``ProwlError`` carrying its message."""
        with pytest.raises(ProwlError) as raised:
            solution_from_envelope({"status": "error", "message": "Challenge could not be solved", "solution": {}})
        self.assertEqual(str(raised.value), "Challenge could not be solved")

    def test_error_message_is_bounded(self: Self) -> None:
        """An over-long service message is truncated before it reaches the caller."""
        with pytest.raises(ProwlError) as raised:
            solution_from_envelope({"status": "error", "message": "x" * 500})
        self.assertEqual(len(str(raised.value)), PROWL_ERROR_MESSAGE_LIMIT)

    def test_error_without_message_is_reported(self: Self) -> None:
        """A failure envelope with no message still raises a usable error."""
        with pytest.raises(ProwlError) as raised:
            solution_from_envelope({"status": "error"})
        self.assertIn("unspecified failure", str(raised.value))

    def test_non_object_envelope_is_rejected(self: Self) -> None:
        """A list or scalar envelope is rejected."""
        with pytest.raises(ProwlError):
            solution_from_envelope(["not", "an", "envelope"])

    def test_missing_solution_is_rejected(self: Self) -> None:
        """An ``ok`` envelope without a solution is rejected."""
        with pytest.raises(ProwlError):
            solution_from_envelope({"status": "ok"})

    def test_malformed_solution_fields_are_rejected(self: Self) -> None:
        """An incompatible service contract fails once instead of causing opaque retries."""
        with pytest.raises(ProwlError, match="malformed solution"):
            solution_from_envelope(
                {
                    "status": "ok",
                    "solution": {"status": "200", "response": None, "headers": "nope", "cookies": "nope"},
                },
            )

    def test_non_dict_cookies_are_dropped(self: Self) -> None:
        """Only cookie objects survive conversion."""
        envelope = _ok_envelope()
        envelope["solution"]["cookies"] = ["nope", {"name": "a", "value": "b"}]
        response = solution_from_envelope(envelope)
        self.assertEqual(response.cookies, [{"name": "a", "value": "b"}])


class ProwlCookieJarTests(TestCase):
    """Verify browser cookies become a replayable jar."""

    def test_cookies_convert_to_a_jar(self: Self) -> None:
        """Name, value and scope survive the conversion."""
        jar = to_cookie_jar([{"name": "cf_clearance", "value": "token", "domain": ".example.test", "path": "/"}])
        cookie = next(iter(jar))
        self.assertEqual(cookie.name, "cf_clearance")
        self.assertEqual(cookie.value, "token")
        self.assertEqual(cookie.domain, ".example.test")

    def test_cookies_without_a_name_or_value_are_skipped(self: Self) -> None:
        """Incomplete cookie entries are ignored rather than guessed at."""
        jar = to_cookie_jar([{"value": "no-name"}, {"name": "only-name"}, {"name": 1, "value": "typed"}])
        self.assertEqual(list(jar), [])

    def test_unusable_cookie_does_not_fail_the_batch(self: Self) -> None:
        """One cookie the jar rejects must not discard the rest."""

        def flaky_create_cookie(**kwargs: Any) -> Any:
            if kwargs["name"] == "bad":
                msg = "invalid cookie"
                raise ValueError(msg)
            return create_cookie(**kwargs)  # type: ignore[no-untyped-call]

        with patch("src.prowl_client.create_cookie", flaky_create_cookie):
            jar = to_cookie_jar(
                [
                    {"name": "bad", "value": "v", "domain": ".example.test", "path": "/"},
                    {"name": "good", "value": "v", "domain": ".example.test", "path": "/"},
                ],
            )
        self.assertEqual([cookie.name for cookie in jar], ["good"])


class ProwlFetchTests(TestCase):
    """Verify the HTTP call and its failure handling."""

    def test_successful_fetch_returns_the_solution(self: Self) -> None:
        """A valid envelope becomes a response against the configured endpoint."""
        with patch("src.prowl_client.requests.post", return_value=_StubHttpResponse(_ok_envelope())) as post:
            response = cast("ProwlResponse", fetch_via_prowl(_URL, timeout=30))
        self.assertEqual(response.status_code, _OK)
        self.assertEqual(post.call_args.args[0], f"{DEFAULT_PROWL_URL}/v1")
        self.assertEqual(post.call_args.kwargs["json"]["cmd"], "request.get")

    def test_transport_failure_returns_none(self: Self) -> None:
        """An unreachable service yields ``None`` so the retry loop continues."""
        with patch("src.prowl_client.requests.post", side_effect=requests.ConnectionError("boom")):
            self.assertIsNone(fetch_via_prowl(_URL, timeout=30))

    def test_non_json_body_returns_none(self: Self) -> None:
        """A response that is not JSON is not treated as a page."""
        with patch("src.prowl_client.requests.post", return_value=_StubHttpResponse(ValueError("no json"))):
            self.assertIsNone(fetch_via_prowl(_URL, timeout=30))

    def test_error_envelope_returns_none(self: Self) -> None:
        """A failure envelope yields ``None`` rather than raising."""
        envelope = {"status": "error", "message": "Challenge could not be solved", "solution": {"response": "SECRET"}}
        with patch("src.prowl_client.requests.post", return_value=_StubHttpResponse(envelope)):
            self.assertIsNone(fetch_via_prowl(_URL, timeout=30))

    def test_response_body_is_never_logged(self: Self) -> None:
        """A service failure must not spill the page body into the logs."""
        envelope = {"status": "error", "message": "Challenge could not be solved", "solution": {"response": "SECRET"}}
        with (
            patch("src.prowl_client.requests.post", return_value=_StubHttpResponse(envelope)),
            patch("src.prowl_client.logger") as logger,
        ):
            fetch_via_prowl(_URL, timeout=30)
        self.assertNotIn("SECRET", str(logger.warning.call_args_list))

    def test_request_headers_are_never_logged(self: Self) -> None:
        """Caller credentials must not spill into the logs either."""
        headers = {"Authorization": "Basic super-secret"}
        with (
            patch("src.prowl_client.requests.post", side_effect=requests.ConnectionError("boom")),
            patch("src.prowl_client.logger") as logger,
        ):
            fetch_via_prowl(_URL, timeout=30, headers=headers)
        self.assertNotIn("super-secret", str(logger.warning.call_args_list))

    def test_misconfigured_endpoint_returns_none(self: Self) -> None:
        """A malformed ``PROWL_URL`` disables the fallback instead of crashing."""
        with patch.dict("os.environ", {"PROWL_URL": "not-a-url"}):
            self.assertIsNone(fetch_via_prowl(_URL, timeout=30))


class MakeRequestProwlIntegrationTests(TestCase):
    """Verify ``make_request`` uses the service as its browser fallback."""

    def test_retriable_failure_returns_the_service_response(self: Self) -> None:
        """A blocked direct request is retried through Prowl and returned."""
        response = solution_from_envelope(_ok_envelope())
        with (
            patch.object(utils, "update_session_data") as session_data,
            patch.object(utils.session, "get", return_value=_DirectResponse(_FORBIDDEN)) as direct,
            patch.object(utils, "fetch_via_prowl", return_value=response) as loader,
        ):
            result = make_request(_URL)

        self.assertIs(result, response)
        direct.assert_called()
        loader.assert_called_once_with(_URL, timeout=utils.request_timeout, headers=None)
        session_data.assert_any_call(response.user_agent, response.cookies)

    def test_service_failure_falls_back_to_a_direct_request(self: Self) -> None:
        """A service that cannot help must not abort the whole request."""
        with (
            patch.object(utils, "update_session_data"),
            patch.object(utils, "request_retries", 2),
            patch.object(utils.session, "get", return_value=_DirectResponse(_FORBIDDEN)) as direct,
            patch.object(utils, "fetch_via_prowl", return_value=None) as loader,
        ):
            result = make_request(_URL)

        self.assertEqual(result.status_code, _FORBIDDEN)
        self.assertEqual(loader.call_count, 2)
        self.assertEqual(direct.call_count, 2)

    def test_service_identity_is_applied_to_the_direct_session(self: Self) -> None:
        """The browser user agent and cookies are replayed on the HTTP session."""
        response = solution_from_envelope(_ok_envelope())
        fake_session = Session()
        with (
            patch.object(utils, "session", fake_session),
            patch.object(utils, "_headers", {}),
            patch.object(utils, "request_header", {}),
        ):
            utils.update_session_data(response.user_agent, response.cookies)

        self.assertEqual(fake_session.headers["User-Agent"], "ua-test")
        self.assertEqual(fake_session.cookies.get("cf_clearance"), "token")

    def test_session_is_untouched_without_browser_cookies(self: Self) -> None:
        """A call with no browser cookies leaves the existing jar alone."""
        fake_session = Session()
        fake_session.cookies.set("existing", "keep")
        with (
            patch.object(utils, "session", fake_session),
            patch.object(utils, "_headers", {}),
            patch.object(utils, "request_header", {}),
        ):
            utils.update_session_data()

        self.assertEqual(fake_session.cookies.get("existing"), "keep")
