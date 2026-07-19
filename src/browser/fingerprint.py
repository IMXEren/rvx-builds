"""Fingerprint management."""

from typing import TYPE_CHECKING, Any, Self

from pydoll.constants import PageLoadState

from src.browser.options import BrowserOptions

if TYPE_CHECKING:
    from pydoll.browser.options import ChromiumOptions


class FingerprintManager:
    """Comprehensive fingerprint evasion using browser options and JavaScript."""

    def __init__(self: Self, profile: dict[str, Any]) -> None:
        """Initialize with target profile (OS, location, device, etc.)."""
        self.profile = profile
        self.options: ChromiumOptions = BrowserOptions.new()
        self._configure_browser_options()

    def _configure_browser_options(self: Self) -> None:
        """Configure browser launch options based on profile."""
        port = self.profile["port"]
        self.options.add_argument(f"--remote-debugging-port={port}")

        screen = self.profile["screen"]
        self.options.add_argument(f"--window-size={screen['width']},{screen['height']}")
        self.options.add_argument(f"--fingerprint-screen-width={screen['width']}")
        self.options.add_argument(f"--fingerprint-screen-height={screen['height']}")

        self.options.add_argument("--fingerprint-storage-quota=1000")  # in MB
        self.options.add_argument("--fingerprint-noise=false")
        self.options.add_argument("--fingerprint-windows-font-metrics")
        self.options.add_argument("--fingerprint-allow-3p-cookies")

        # for docker with vnc
        self.options.add_argument("--use-gl=angle")
        self.options.add_argument("--use-angle=swiftshader")

        self.options.page_load_state = PageLoadState.COMPLETE
