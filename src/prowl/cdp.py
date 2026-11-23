"""Drive a Prowl reserved tab with pydoll through Prowl's authenticated CDP gateway."""

import os
from contextlib import contextmanager
from pathlib import Path
from typing import Final
lazy from collections.abc import Iterator

import requests
from loguru import logger
from pydoll.sync import Chrome, Tab

from src.prowl.client import resolve_prowl_url

# The same variable Prowl reads its gateway token from.
PROWL_CDP_TOKEN_FILE_ENV: Final[str] = "PROWL_CDP_TOKEN_FILE"  # noqa: S105 - a variable name, not a secret
# A reservation may start a browser.
RESERVATION_TIMEOUT: Final[float] = 120.0


class ProwlTabError(Exception):
    """A reserved tab could not be created."""


def cdp_token() -> str:
    """Return the configured CDP token, or an empty string when reserved tabs are not set up."""
    token_file = os.environ.get(PROWL_CDP_TOKEN_FILE_ENV, "").strip()
    if not token_file:
        return ""
    try:
        return Path(token_file).read_text(encoding="utf-8").strip()
    except OSError as error:
        logger.warning(f"Unable to read {PROWL_CDP_TOKEN_FILE_ENV}: {type(error).__name__}")
        return ""


@contextmanager
def reserved_tab(token: str, base_url: str | None = None) -> Iterator[Tab]:
    """Reserve a Prowl tab and yield it as a pydoll tab, releasing the reservation on exit."""
    base = resolve_prowl_url(base_url)
    headers = {"Authorization": f"Bearer {token}"}
    try:
        response = requests.post(f"{base}/cdp/reservations", json={}, headers=headers, timeout=RESERVATION_TIMEOUT)
    except requests.RequestException as error:
        msg = f"Prowl is unreachable: {type(error).__name__}"
        raise ProwlTabError(msg) from error
    if not response.ok:
        msg = f"Prowl refused the tab reservation with HTTP {response.status_code}"
        raise ProwlTabError(msg)
    reservation = response.json()
    tab_url = f"{base}/cdp/reservations/{reservation['tab']}"
    try:
        try:
            version = requests.get(f"{tab_url}/json/version", headers=headers, timeout=RESERVATION_TIMEOUT).json()
        except (requests.RequestException, ValueError) as error:
            msg = f"Prowl did not describe the reserved tab: {type(error).__name__}"
            raise ProwlTabError(msg) from error
        browser = Chrome()
        browser.connect(version["webSocketDebuggerUrl"], headers=headers)
        try:
            # The browser socket lists all of Prowl's tabs.
            tab = next((tab for tab in browser.get_opened_tabs() if tab.target_id == reservation["target"]), None)
            if tab is None:
                msg = "Prowl's browser does not list the reserved tab"
                raise ProwlTabError(msg)
            yield tab
        finally:
            browser.close()
    finally:
        try:
            requests.delete(tab_url, headers=headers, timeout=RESERVATION_TIMEOUT)
        except requests.RequestException as error:
            logger.warning(f"Unable to release Prowl tab {reservation['tab']}: {type(error).__name__}")
