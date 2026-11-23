"""Regression tests for Uptodown's client API download path."""

# ruff: noqa: PT009, SLF001

import base64
import json
from types import SimpleNamespace
from typing import TYPE_CHECKING, Any, Self, cast
from unittest import TestCase
from unittest.mock import patch

from src.downloader.uptodown import UptoDown

if TYPE_CHECKING:
    from src.app import APP
    from src.config import RevancedConfig

SOURCE = "https://example-app.en.uptodown.com/android"


class _Response(SimpleNamespace):
    """Response double with the fields read by `handle_request_response` and the JSON parsers."""

    status_code: int = 200
    payload: Any = None

    def json(self: Self) -> Any:
        """Return the stored JSON payload."""
        return self.payload


def _app() -> APP:
    """Build the APP fields the Uptodown downloader reads."""
    return cast(
        "APP",
        SimpleNamespace(app_name="EXAMPLE", package_name="com.example.app", download_source=SOURCE),
    )


def _api(path: str) -> dict[str, Any]:
    """Answer the client API calls of one app with two files."""
    answers: dict[str, dict[str, Any]] = {
        "/apps/byPackagename/com.example.app": {"appID": 42},
        "/v3/apps/42/device/0": {"urlShare": "https://example-app.uptodown.com/android"},
        "/apps/42/file/200/downloadUrl?update=0": {"downloadURL": "https://dw.uptodown.com/dwn/second"},
        "/apps/42/file/300/downloadUrl?update=0": {"downloadURL": "https://dw.uptodown.com/dwn/variant"},
    }
    return answers[path]


VERSIONS = _Response(
    payload={
        "data": [
            {"version": "2.0", "fileID": 100, "kindFile": "apk"},
            {"version": "1.0", "fileID": 200, "kindFile": "xapk"},
        ],
    },
)


def _without_variants() -> list[_Response]:
    """Answer the version list, the cookie priming request and a release without variants."""
    return [VERSIONS, _Response(), _Response(status_code=404)]


class UptodownDownloaderTests(TestCase):
    """Verify that Uptodown downloads go through the client API's signed file URLs."""

    def _downloader(self: Self) -> UptoDown:
        """Build a downloader without the full env config."""
        return UptoDown(cast("RevancedConfig", SimpleNamespace()))

    def test_specific_version_downloads_signed_file_url(self: Self) -> None:
        """The requested version's file id is exchanged for a signed URL, keeping its archive kind."""
        downloader = self._downloader()
        with (
            patch.object(UptoDown, "_api_get", side_effect=_api),
            patch("src.downloader.uptodown.make_request", side_effect=_without_variants()),
            patch.object(downloader, "_download") as download,
        ):
            file_name, url = downloader.specific_version(_app(), "1.0")

        self.assertEqual(("EXAMPLE.xapk", "https://dw.uptodown.com/dwn/second"), (file_name, url))
        download.assert_called_once_with("https://dw.uptodown.com/dwn/second", "EXAMPLE.xapk")

    def test_release_with_variants_downloads_best_variant(self: Self) -> None:
        """A release listing several builds downloads the variant with the best arch and density."""
        variants = _Response(
            payload={
                "content": """
                    <section class="variants"><div class="content"><p>arm64-v8a</p></div></section>
                    <div class="variant"><img data-file-id="300"><div class="v-screen">nodpi</div></div>
                """,
            },
        )
        downloader = self._downloader()
        with (
            patch.object(UptoDown, "_api_get", side_effect=_api),
            patch("src.downloader.uptodown.make_request", side_effect=[VERSIONS, _Response(), variants]),
            patch.object(downloader, "_download") as download,
        ):
            downloader.specific_version(_app(), "1.0")

        download.assert_called_once_with("https://dw.uptodown.com/dwn/variant", "EXAMPLE.xapk")

    def test_latest_version_takes_newest_entry_and_resolves_it(self: Self) -> None:
        """The version list is newest first, and the chosen entry names the concrete version."""
        app = _app()
        downloader = self._downloader()
        with (
            patch.object(
                UptoDown,
                "_api_get",
                side_effect=lambda path: (
                    {"downloadURL": "https://dw.uptodown.com/dwn/newest"} if "/file/100/" in path else _api(path)
                ),
            ),
            patch("src.downloader.uptodown.make_request", side_effect=_without_variants()),
            patch.object(downloader, "_download"),
        ):
            file_name, _url = downloader.latest_version(app)

        self.assertEqual("EXAMPLE.apk", file_name)
        self.assertEqual("2.0", app.resolved_version)

    def test_source_for_package_uses_english_host(self: Self) -> None:
        """Discovery turns the share URL into the source format the downloader factory recognizes."""
        with patch.object(UptoDown, "_api_get", side_effect=_api):
            self.assertEqual(SOURCE, UptoDown.source_for_package("com.example.app"))

    def test_authorize_caches_token_until_jwt_expiry(self: Self) -> None:
        """The token is reused until shortly before the expiry its JWT payload names."""
        payload = base64.urlsafe_b64encode(json.dumps({"exp": 4_000_000_000}).encode()).decode().rstrip("=")
        token = f"header.{payload}.signature"
        with (
            patch.object(UptoDown, "_token", ""),
            patch.object(UptoDown, "_token_expiry", 0.0),
            patch("src.downloader.uptodown.session.post", return_value=_Response(payload={"token": token})) as post,
        ):
            self.assertEqual(token, UptoDown._authorize())
            self.assertEqual(token, UptoDown._authorize())

        post.assert_called_once()
