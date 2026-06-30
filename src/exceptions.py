"""Possible Exceptions."""

from typing import TYPE_CHECKING, Any, Self

if TYPE_CHECKING:
    from src.utils import ResponseType

NOT_FOUND_STATUS_CODE: int = 404


class BuilderError(Exception):
    """Base class for all the project errors."""

    message = "Default Error message."

    def __init__(self: Self, *args: Any, **kwargs: Any) -> None:
        if args:
            self.message = args[0]
        super().__init__(self.message)

    def __str__(self: Self) -> str:
        """Return error message."""
        return self.message


class ScrapingError(BuilderError):
    """Exception raised when the url cannot be scraped."""

    def __init__(
        self: Self,
        *args: Any,
        url: str | None = None,
        response: "ResponseType | None" = None,
        **kwargs: dict[str, Any],
    ) -> None:
        """Initialize the ScrapingError.

        Args:
        ----
            *args: Variable length argument list.
            **kwargs: Arbitrary keyword arguments.
                url (str, optional): The URL of the failed request. Defaults to None.
                response (ResponseType, optional): The ResponseType that caused the failure.
                    Allows callers to inspect the status code. Defaults to None.
        """
        super().__init__(*args, **kwargs)
        self.url = url
        self.response = response

    @property
    def status_code(self: Self) -> int | None:
        """Return the HTTP status code if a response is attached, else None."""
        if self.response is None:
            return None
        return self.response.status_code

    def is_not_found(self: Self) -> bool:
        """Return True if this error represents a 404 response.

        Falls back to True when no response is attached (matches the legacy
        assumption that every ScrapingError was a 404).
        """
        code = self.status_code
        return code == NOT_FOUND_STATUS_CODE

    def __str__(self: Self) -> str:
        """Exception message."""
        base_message = super().__str__()
        return f"Message - {base_message} Url - {self.url}"


class APKMirrorIconScrapError(ScrapingError):
    """Exception raised when the icon cannot be scraped from apkmirror."""


class DownloadError(BuilderError):
    """Generic Download failure."""

    def __init__(self: Self, *args: Any, **kwargs: Any) -> None:
        """Initialize the DownloadFailure exception.

        Args:
        ----
            *args: Variable length argument list.
            **kwargs: Arbitrary keyword arguments.
                url (str, optional): The URL of the failed icon scraping. Defaults to None.
        """
        super().__init__(*args)
        self.url = kwargs.get("url")

    def __str__(self: Self) -> str:
        """Exception message."""
        base_message = super().__str__()
        return f"Message - {base_message} Url - {self.url}"


class APKDownloadError(DownloadError):
    """Exception raised when the apk cannot be scraped."""


class APKMirrorAPKDownloadError(APKDownloadError):
    """Exception raised when downloading an APK from apkmirror failed."""


class APKMirrorAPKNotFoundError(APKDownloadError):
    """Exception raised when apk doesn't exist on APKMirror."""


class VersionNotFoundError(APKDownloadError):
    """Exception raised when the requested version is not found at the source."""


class UptoDownAPKDownloadError(APKDownloadError):
    """Exception raised when downloading an APK from uptodown failed."""


class APKPureAPKDownloadError(APKDownloadError):
    """Exception raised when downloading an APK from apkpure failed."""


class PatchingFailedError(BuilderError):
    """Patching Failed."""


class AppNotFoundError(BuilderError):
    """Not a valid Revanced App."""


class PatchesJsonLoadError(BuilderError):
    """Failed to load patches json."""

    def __init__(self: Self, *args: Any, **kwargs: Any) -> None:
        """Initialize the PatchesJsonLoadFailed exception.

        Args:
        ----
            *args: Variable length argument list.
            **kwargs: Arbitrary keyword arguments.
                file_name (str, optional): The name of json file. Defaults to None.
        """
        super().__init__(*args)
        self.file_name = kwargs.get("file_name")

    def __str__(self: Self) -> str:
        """Exception message."""
        base_message = super().__str__()
        return f"Message - {base_message} File - {self.file_name}"
