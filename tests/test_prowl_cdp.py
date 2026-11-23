"""Regression tests for reserving a Prowl tab and attaching pydoll to it."""

# ruff: noqa: PT009, PT027

from types import SimpleNamespace
from typing import Any, Self
from unittest import TestCase
from unittest.mock import MagicMock, patch

import requests

from src.prowl.cdp import ProwlTabError, cdp_token, reserved_tab

BASE = "http://prowl:8191"


def _response(payload: Any = None, *, ok: bool = True, status_code: int = 200) -> SimpleNamespace:
    """Build a requests response double."""
    return SimpleNamespace(ok=ok, status_code=status_code, json=lambda: payload)


class ReservedTabTests(TestCase):
    """Verify reservation, tab selection and release."""

    def test_yields_the_reserved_target_and_releases_it(self: Self) -> None:
        """Pydoll connects with the bearer header, and the reserved target is picked from every tab."""
        reserved = SimpleNamespace(target_id="target-2")
        browser = MagicMock()
        browser.get_opened_tabs.return_value = [SimpleNamespace(target_id="main"), reserved]
        with (
            patch("src.prowl.cdp.requests.post", return_value=_response({"tab": "tab-1", "target": "target-2"})),
            patch("src.prowl.cdp.requests.get", return_value=_response({"webSocketDebuggerUrl": "ws://gw/socket"})),
            patch("src.prowl.cdp.requests.delete") as delete,
            patch("src.prowl.cdp.Chrome", return_value=browser),
            reserved_tab("token", BASE) as tab,
        ):
            self.assertIs(reserved, tab)

        browser.connect.assert_called_once_with(
            "ws://gw/socket",
            headers={"Authorization": "Bearer token"},
        )
        browser.close.assert_called_once_with()
        delete.assert_called_once()
        self.assertEqual(f"{BASE}/cdp/reservations/tab-1", delete.call_args.args[0])

    def test_refused_reservation_raises(self: Self) -> None:
        """A rejected reservation reports its status instead of connecting."""
        with (
            patch("src.prowl.cdp.requests.post", return_value=_response(ok=False, status_code=401)),
            self.assertRaisesRegex(ProwlTabError, "401"),
            reserved_tab("token", BASE),
        ):
            pass

    def test_unreachable_prowl_raises_tab_error(self: Self) -> None:
        """A connection failure surfaces as the error the downloader handles."""
        with (
            patch("src.prowl.cdp.requests.post", side_effect=requests.ConnectionError),
            self.assertRaisesRegex(ProwlTabError, "unreachable"),
            reserved_tab("token", BASE),
        ):
            pass

    def test_missing_reserved_target_raises_and_releases(self: Self) -> None:
        """A reservation whose tab the browser does not list is released instead of leaking."""
        browser = MagicMock()
        browser.get_opened_tabs.return_value = [SimpleNamespace(target_id="main")]
        with (
            patch("src.prowl.cdp.requests.post", return_value=_response({"tab": "tab-1", "target": "target-2"})),
            patch("src.prowl.cdp.requests.get", return_value=_response({"webSocketDebuggerUrl": "ws://gw/socket"})),
            patch("src.prowl.cdp.requests.delete") as delete,
            patch("src.prowl.cdp.Chrome", return_value=browser),
            self.assertRaisesRegex(ProwlTabError, "does not list"),
            reserved_tab("token", BASE),
        ):
            pass

        browser.close.assert_called_once_with()
        delete.assert_called_once()

    def test_token_comes_from_the_shared_token_file(self: Self) -> None:
        """The builder reads the same token file Prowl is configured with."""
        with patch.dict("os.environ", {"PROWL_CDP_TOKEN_FILE": ""}):
            self.assertEqual("", cdp_token())
