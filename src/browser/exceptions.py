"""Browser impl exceptions."""


class FailedToStartBrowserError(Exception):
    """Implies failed to create the browser process or tab group."""


class PageLoadError(Exception):
    """Implies that the page load checker mechanism failed."""


class JSONExtractError(Exception):
    """Implies that the json extractor mechanism failed or no such json."""
