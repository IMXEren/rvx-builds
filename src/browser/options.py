"""Browser preferences/options."""

from pydoll.browser.options import ChromiumOptions


class BrowserOptions:
    """Simple class to form and return a predefined instance of `ChromiumOptions()`."""

    @classmethod
    def new(cls) -> ChromiumOptions:
        """Return an instance of chrome `ChromiumOptions()`."""
        ## Ref1: https://github.com/Ulyssedev/Rust-undetected-chromedriver/blob/29222ff29fdf8bf018eb7ce668aa3ef4f9d84ab3/src/lib.rs#L107
        ## Ref2: https://stackoverflow.com/a/59678801

        options = ChromiumOptions()
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-blink-features=AutomationControlled")

        options.browser_preferences = {
            "enable_do_not_track": False,
            "profile": {
                "default_content_setting_values": {
                    "notifications": 2,  # Block notifications
                },
                "block_third_party_cookies": False,
                "cookie_controls_mode": 2,  # Allow 3rd party cookies (not available in incognito)
            },
            "browser": {
                "has_seen_welcome_page": True,
                "theme": {
                    "color_scheme2": 2,  # dark
                    "color_variant2": 1,
                    "user_color2": -3491677,
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
