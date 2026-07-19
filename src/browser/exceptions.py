"""Browser impl exceptions."""


class BrowserError(Exception):
    """Base Browser exception."""


class BrowserStartError(BrowserError):
    """Implies failed to start the browser process."""


class BrowserTabError(BrowserError):
    """Implies error propagated by the browser's tab."""


class BrowserShutdownError(BrowserError):
    """Implies failed to shutdown the browser process."""


class PageLoadError(BrowserError):
    """Implies that the page load checker mechanism failed."""


class JSONExtractError(BrowserError):
    """Implies that the json extractor mechanism failed or no such json."""
