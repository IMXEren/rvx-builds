"""Methods to load the page in the browser using webdriver."""

from typing import Self

from loguru import logger
from pydoll.browser import Chrome
from pydoll.browser.options import ChromiumOptions
from pydoll.browser.tab import Tab

from src.browser.ip_geo import IPGeolocationInfo

BROWSER_SETUP_TRIALS = 0


class Browser:
    """Convenient class to load urls in the browser opposed to HTTPRequest."""

    setup_max_trials = 2

    def __init__(self: Self) -> None:
        """Initialises the browser by setting up the dependencies and init the webdriver.

        Not meant to be invoked directly instead with `Browser.create()`.
        """
        if not find_chrome_executable():
            if self.under_max_setup_trial():
                self.setup_dependencies()
                self.increment_setup_trial()
            else:
                # It's unnecessary to run setup everytime.
                msg = "Max trials for the Browser setup was hit and yet the browser setup isn't complete."
                raise ValueError(msg)

        ip_info = IPGeolocationInfo.get_info()
        ip_profile = {}
        if ip_info:
            ip_profile = {
                "timezone": ip_info.timezone,
                "offset": ip_info.diff_utc_local_in_minutes(),
                "geolocation": {
                    "latitude": ip_info.latitude,
                    "longitude": ip_info.longitude,
                },
            }

        profile = {
            "screen": {
                "width": 1920,
                "height": 1080,
            },
        }
        profile.update(ip_profile)
        self.evader = FingerprintEvader(profile)
        self.browser = Chrome(options=self.evader.options)

    @classmethod
    async def create(cls: type[Self]) -> Self:
        """Creates the browser instance.

        Exceptions are raised by the `pydoll.browser.Chrome()` impls.
        """
        instance = cls()
        _tab = await instance.browser.start()
        # Don't close tab otherwise browser would be closed
        return instance

    async def quit(self: Self) -> None:
        """Cleares up the browser instance."""
        return await self.browser.stop()

    async def get(self: Self, url: str, timeout: int = 60):  # noqa: ANN201, ASYNC109
        """Loads the url.

        Waits for the page to load until timeout is hit.
        Raises `PageLoadError` on load failure.
        """
        site = self.map_url(url)
        return await site.get(url, timeout)

    def map_url(self: Self, url: str):  # noqa: ANN201
        """Maps the url, to their site implementation based on the pattern matching.

        Returns default `Site` on no match.
        """
        from src.browser.apkmirror import APKMirror  # noqa: PLC0415
        from src.browser.site import Site  # noqa: PLC0415

        site = Site(self)
        if "www.apkmirror.com" in url:
            site = APKMirror(self)

        return site

    @staticmethod
    def increment_setup_trial(by: int = 1) -> None:
        """Increment the setup trial count by 1 or any number."""
        global BROWSER_SETUP_TRIALS  # noqa: PLW0603
        BROWSER_SETUP_TRIALS += by

    def under_max_setup_trial(self: Self) -> bool:
        """Check if the current trial count is less the max trial count."""
        return self.setup_max_trials > BROWSER_SETUP_TRIALS

    def setup_dependencies(self: Self) -> bool:
        """Not implemented yet for all (linux only for now).

        Setups the browser dependencies based on systems and returns the bool result.
        """
        import platform  # noqa: PLC0415

        system = platform.system().lower()
        if system == "linux":
            setup = self.setup_dependencies_on_linux()
        elif system == "windows":
            setup = self.setup_dependencies_on_windows()
        elif system == "darwin":
            setup = self.setup_dependencies_on_mac()
        else:
            setup = self.setup_dependencies_on_unknown(system)
        return setup

    @staticmethod
    def setup_dependencies_on_linux() -> bool:
        """Setups the browser dependencies on linux.

        Returns the bool result.
        """
        import subprocess  # noqa: PLC0415
        from pathlib import Path  # noqa: PLC0415

        setup = False
        setup_script = Path(__file__).parent.joinpath("setup_browser.sh").as_posix()
        try:
            subprocess.run(["bash", setup_script, "google-chrome"], check=True)
            setup = True
        except subprocess.CalledProcessError as e:
            logger.error(f"failed to setup browser dependencies: {e!r}")
        return setup

    @staticmethod
    def setup_dependencies_on_windows() -> bool:
        """Not implemented yet.

        Setups the browser dependencies on windows.

        Returns the bool result.
        """
        try:
            msg = (
                "setup not yet implemented for Windows, kindly setup chrome browser manuallly "
                "or write yourself a powershell script"
            )
            raise NotImplementedError(msg)
        except NotImplementedError as e:
            logger.error(f"failed to setup browser dependencies: {e!r}")
        return False

    @staticmethod
    def setup_dependencies_on_mac() -> bool:
        """Not implemented yet.

        Setups the browser dependencies on mac.

        Returns the bool result.
        """
        try:
            msg = (
                "setup not yet implemented for Mac OS, kindly setup chrome browser manually "
                "or write yourself a zsh script"
            )
            raise NotImplementedError(msg)
        except NotImplementedError as e:
            logger.error(f"failed to setup browser dependencies: {e!r}")
        return False

    @staticmethod
    def setup_dependencies_on_unknown(system: str) -> bool:
        """Not implemented yet.

        Setups the browser dependencies on unknown.

        Returns the bool result.
        """
        try:
            msg = f"unexpected system: {system}, kindly setup chrome browser manually"
            raise NotImplementedError(msg)
        except NotImplementedError as e:
            logger.error(f"failed to setup browser dependencies: {e!r}")
        return False


class BrowserOptions:
    """Simple class to form and return a predefined instance of `ChromiumOptions()`."""

    def __new__(cls: type[Self]) -> ChromiumOptions:
        """Return an instance of chrome `ChromiumOptions()`."""
        ## Ref1: https://github.com/Ulyssedev/Rust-undetected-chromedriver/blob/29222ff29fdf8bf018eb7ce668aa3ef4f9d84ab3/src/lib.rs#L107
        ## Ref2: https://stackoverflow.com/a/59678801

        options = ChromiumOptions()
        # options.add_argument("--headless=new")  # noqa: ERA001
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--log-level=3")
        options.add_argument("--disable-blink-features=AutomationControlled")

        options.browser_preferences = {
            "enable_do_not_track": False,
            "profile": {
                "default_content_setting_values": {
                    "notifications": 2,  # Block notifications
                },
            },
            "browser": {
                "has_seen_welcome_page": True,
                "theme": {
                    "color_scheme": 2,
                    "color_variant": 1,
                    "user_color": -3491677,
                },
            },
            "safebrowsing": {
                "enabled": False,
            },
            "user_experience_metrics": {
                "reporting_enabled": False,
            },
        }

        return options


# Ref: https://github.com/kaliiiiiiiiii/Selenium-Driverless/blob/ca333fd88b0b7722ac128e08deccbb5ffbd66b39/src/selenium_driverless/utils/utils.py#L24
def find_chrome_executable() -> str:
    """
    Finds the Chrome, Chrome beta, Chrome canary, Chromium executable.

    Returns
    -------
    executable_path :  str
        the full file path to found executable

    """
    import os  # noqa: PLC0415
    import sys  # noqa: PLC0415

    IS_POSIX = sys.platform.startswith(("darwin", "cygwin", "linux", "linux2"))  # noqa: N806
    candidates = set()
    if IS_POSIX:
        for item in os.environ.get("PATH", "").split(os.pathsep):
            for subitem in (
                "google-chrome",
                "chromium",
                "chromium-browser",
                "chrome",
                "google-chrome-stable",
            ):
                candidates.add(os.sep.join((item, subitem)))  # noqa: PTH118
        if "darwin" in sys.platform:
            candidates.update(
                [
                    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
                    "/Applications/Chromium.app/Contents/MacOS/Chromium",
                ],
            )
    else:
        for item in map(
            os.environ.get,
            ("PROGRAMFILES", "PROGRAMFILES(X86)", "LOCALAPPDATA", "PROGRAMW6432"),
        ):
            if item is not None:
                for subitem in (
                    "Google/Chrome/Application",
                    "Google/Chrome Beta/Application",
                    "Google/Chrome Canary/Application",
                ):
                    candidates.add(os.sep.join((item, subitem, "chrome.exe")))  # noqa: PTH118
    for candidate in candidates:
        if os.path.exists(candidate) and os.access(candidate, os.X_OK):  # noqa: PTH110
            return os.path.normpath(candidate)
    raise FileNotFoundError("Couldn't find installed Chrome or Chromium executable")  # noqa: EM101, TRY003


class FingerprintEvader:
    """Comprehensive fingerprint evasion using browser options and JavaScript."""

    def __init__(self, profile: dict) -> None:
        """Initialize with target profile (OS, location, device, etc.)."""
        self.profile = profile
        self.options = BrowserOptions()
        self._configure_browser_options()

    def _configure_browser_options(self) -> None:
        """Configure browser launch options based on profile."""
        # 1. Window size (screen dimensions)
        screen = self.profile["screen"]
        self.options.add_argument(f"--window-size={screen['width']},{screen['height']}")

        # 2. Device scale factor (for high-DPI displays)
        if screen.get("deviceScaleFactor", 1.0) != 1.0:
            self.options.add_argument(f"--device-scale-factor={screen['deviceScaleFactor']}")

        # 3. Timezone
        if self.profile.get("timezone"):
            self.options.add_argument(f"--tz={self.profile['timezone']}")

    async def apply_to_tab(self, tab: Tab) -> None:
        """Apply JavaScript overrides to tab after launch."""
        has_web_share_script = """
        if (!navigator.share) {
            Object.defineProperty(Navigator.prototype, 'share', {
                value: async () => Promise.resolve(),
                configurable: true,
                enumerable: true,
                writable: true
            });
        }

        if (!navigator.canShare) {
            Object.defineProperty(Navigator.prototype, 'canShare', {
                value: () => false,
                configurable: true,
                enumerable: true,
                writable: true
            });
        }
        """

        screen = self.profile["screen"]
        height = screen["height"]
        width = screen["width"]
        no_taskbar_script = f"""
        const originalScreen = window.screen;
        Object.defineProperties(window.screen, {{
            'availHeight': {{ get: () => {height - 40} }}, // 40px taskbar
            'availWidth': {{ get: () => {width} }},
            'height': {{ get: () => {height} }},
            'width': {{ get: () => {width} }},
            'availTop': {{ get: () => 0 }},
            'availLeft': {{ get: () => 0 }}
        }});
        """

        await tab.execute_script(has_web_share_script)
        await tab.execute_script(no_taskbar_script)

        # Apply geolocation if provided
        if "geolocation" in self.profile:
            await self._override_geolocation(tab)

        # Apply timezone if provided
        if "timezone" in self.profile:
            await self._override_timezone(tab)

    async def _override_geolocation(self, tab: Tab) -> None:
        """Override geolocation API."""
        geo = self.profile["geolocation"]
        await tab._execute_command(  # noqa: SLF001
            {
                "method": "Emulation.setGeolocationOverride",
                "params": {
                    "latitude": geo["latitude"],
                    "longitude": geo["longitude"],
                    "accuracy": 1,
                    "altitude": None,
                    "altitudeAccuracy": None,
                    "heading": None,
                    "speed": None,
                },
            },
        )

    async def _override_timezone(self, tab: Tab) -> None:
        """Override timezone-related functions."""
        timezone = self.profile["timezone"]
        await tab._execute_command(  # noqa: SLF001
            {
                "method": "Emulation.setTimezoneOverride",
                "params": {
                    "timezoneId": timezone,
                },
            },
        )
