"""Utilities."""

import json
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any
from zoneinfo import ZoneInfo

import requests
from browserforge.headers import Browser, HeaderGenerator
from environs import Env
from loguru import logger
from requests import Response, Session

from src.browser.cookies import Cookies
from src.browser.site import Source
from src.browser.site import source as page_source

if TYPE_CHECKING:
    from src.app import APP

from src.downloader.sources import APK_MIRROR_APK_CHECK
from src.exceptions import ScrapingError
from src.metadata.github import GithubSourceMetadata

default_build = [
    "youtube",
    "youtube_music",
]
possible_archs = ["armeabi-v7a", "x86", "x86_64", "arm64-v8a"]
request_header = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (HTML, like Gecko)"
    " Chrome/96.0.4664.93 Safari/537.36",
    "Authorization": "Basic YXBpLWFwa3VwZGF0ZXI6cm01cmNmcnVVakt5MDRzTXB5TVBKWFc4",
    "Content-Type": "application/json",
}
default_cli = "https://github.com/revanced/revanced-cli/releases/latest"
default_patches = "https://github.com/revanced/revanced-patches/releases/latest"
bs4_parser = "html.parser"
changelog_file = "changelog.md"
changelog_json_file = "changelog.json"
request_timeout = 60
request_retries = 15
session = Session()
_browsers = [Browser("chrome", min_version=130, max_version=140)]
_headers = HeaderGenerator(browser=_browsers, os="linux", device="desktop").generate()
_headers.pop("Accept-Encoding", None)
request_header.update(_headers)
session.headers.update(_headers)

updates_file = "updates.json"
updates_file_url = "https://raw.githubusercontent.com/{github_repository}/{branch_name}/{updates_file}"
changelogs: dict[str, GithubSourceMetadata] = {}
time_zone = "Asia/Kolkata"
app_version_key = "app_version"
patches_versions_key = "patches_versions"
cli_version_key = "cli_version"
implement_method = "Please implement the method"
status_code_200 = 200
resource_folder = "apks"
branch_name = "changelogs"
app_dump_key = "app_dump"
patches_dl_list_key = "patches_dl_list"


def update_session_data(user_agent: str | None = None) -> None:
    """Update the session related data such as user-agent, headers, cookies.

    Aimed to be used in conjuction with browser. For example,
    browser would store cookies which can be reused in `Session`.
    """
    if user_agent:
        _headers.update({"User-Agent": user_agent})
    _headers.pop("Accept-Encoding", None)
    request_header.update(_headers)
    session.headers.update(_headers)
    cookie_jar = Cookies().load_to_cookie_jar()
    session.cookies.update(cookie_jar)


def update_changelog(name: str, response: dict[str, str]) -> None:
    """The function `update_changelog` updates the changelog file.

    Parameters
    ----------
    name : str
        A string representing the name of the change or update.
    response : Dict[str, str]
        The `response` parameter is a dictionary that contains information about the changes made. The keys
    in the dictionary represent the type of change (e.g., "bug fix", "feature", "documentation"), and
    the values represent the specific changes made for each type.
    """
    source_metadata = GithubSourceMetadata.from_json(response)
    changelogs[name] = source_metadata


def format_changelog(metadata: GithubSourceMetadata) -> str:
    """The `format_changelog` returns formatted changelog string.

    Parameters
    ----------
    metadata : GithubSourceMetadata
        Represents the release metadata with sufficient info.

    Returns
    -------
        a formatted changelog as str
    """
    content = (
        f"# {metadata.name}\n\n"
        f"***Release Version: [{metadata.tag}]({metadata.html_url})***  \n"
        f"***Release Date: {metadata.get_release_date()}***  \n"
        f"<details>\n<summary><b><i>Changelog:</i></b></summary>\n\n{metadata.body}</details>\n\n"
    )
    return f"{content}"


def write_changelog_to_file(updates_info: dict[str, Any]) -> None:
    """The function `write_changelog_to_file` writes a given changelog json to a file."""
    changelog_doc = ""
    metadata_list = GithubSourceMetadata.sort_by_latest_release(changelogs.values())
    for data in metadata_list:
        changelog_doc += format_changelog(data)
    with Path(changelog_file).open("w", encoding="utf_8") as file1:
        file1.write(changelog_doc)

    def encoder_default(obj: Any) -> Any:
        if isinstance(obj, datetime):
            return obj.isoformat()
        if hasattr(obj, "__dict__"):
            return obj.__dict__
        msg = f"Object of type {type(obj).__name__} is not JSON serializable"
        raise TypeError(msg)

    Path(changelog_json_file).write_text(json.dumps(changelogs, default=encoder_default, indent=4) + "\n")
    Path(updates_file).write_text(json.dumps(updates_info, indent=4, default=str) + "\n")


def get_parent_repo() -> str:
    """The `get_parent_repo()` function returns the URL of the parent repository.

    Returns
    -------
        the URL of the parent repository, which is "https://github.com/nikhilbadyal/docker-py-revanced".
    """
    project_url = "https://github.com/nikhilbadyal/docker-py-revanced"
    return f"[Docker-py-revanced]({project_url})"


def make_request(url: str, headers: dict[str, str] | None = None) -> Response | Source:
    """The `start_request()` function makes the GET request with the possible retrying methods.

    Parameters
    ----------
    url: str
        The url on which to make request.
    headers: dict[str, str]
        The request headers to be used while making the request.

    Returns
    -------
    response: Response
        The response object from the HTTP request.
    """
    i = 0
    update_session_data()
    response = session.get(url, headers=headers, allow_redirects=True, timeout=request_timeout)
    while (not response or response.status_code != status_code_200) and i < request_retries:
        i += 1
        logger.info(f"Retrying ({i})...")
        if i % 5 == 0:
            sleep_duration = 15 * (i // 5)
            logger.info(f"Sleeping for {sleep_duration}s...")
            time.sleep(sleep_duration)
            response = session.get(url, headers=headers, allow_redirects=True, timeout=request_timeout)
        else:
            response = load_page_in_browser(url, timeout=request_timeout)
            if response:
                update_session_data(response.user_agent)
    if not response:
        response = session.get(url, headers=headers, allow_redirects=True, timeout=request_timeout)
    return response


def load_page_in_browser(url: str, timeout: float = request_timeout) -> Source | None:
    """The `load_page_in_browser()` function loads the url in a browser.

    Parameters
    ----------
    url: str
        The url on which to make request.
    timeout: float
        Max wait duration in secs that'll allow the page to be loaded.

    Returns
    -------
    source: Source | None
        The `Response` like object from the browser request.
        `text` attribute will contain the source html content.
        Note that the source would be None if encountered exceptions.
    """
    try:
        import asyncio
        from concurrent.futures import ThreadPoolExecutor

        asyncio.get_running_loop()
        with ThreadPoolExecutor(1) as pool:
            source = pool.submit(lambda: asyncio.run(page_source(url, timeout))).result()
    except RuntimeError:
        return asyncio.run(page_source(url, timeout))
    except Exception as e:  # noqa: BLE001
        logger.exception(f"failed to load url in the browser => {e!r}")
        return None
    else:
        return source


def handle_request_response(response: Response | Source, url: str) -> None:
    """The function handles the response of a GET request and raises an exception if the response code is not 200.

    Parameters
    ----------
    response : Response
        The parameter `response` is of type `Response`, which is likely referring to a response object from
    an HTTP request. This object typically contains information about the response received from the
    server, such as the status code, headers, and response body.
    url: str
        The url on which request was made
    """
    response_code = response.status_code
    if response_code != status_code_200:
        msg = f"Unable to downloaded assets. Reason - {response.text}"
        raise ScrapingError(msg, url=url)


def slugify(string: str) -> str:
    """The `slugify` function converts a string to a slug format.

    Parameters
    ----------
    string : str
        The `string` parameter is a string that you want to convert to a slug format.

    Returns
    -------
        The function `slugify` returns a modified version of the input string in slug format.
    """
    # Convert to lowercase
    modified_string = string.lower()

    # Remove special characters
    modified_string = re.sub(r"[^\w\s-]", ".", modified_string)

    # Replace spaces with dashes
    modified_string = re.sub(r"\s+", ".", modified_string)

    # Remove consecutive dashes
    modified_string = re.sub(r"-+", ".", modified_string)

    # Remove leading and trailing dashes
    return modified_string.strip(".")


def _check_version(output: str) -> None:
    """Check version."""
    if "Runtime Environment" not in output:
        raise subprocess.CalledProcessError(-1, "java -version")
    if "17" not in output and "20" not in output:
        raise subprocess.CalledProcessError(-1, "java -version")


def check_java() -> None:
    """The function `check_java` checks if Java version 17 or higher is installed.

    Returns
    -------
        The function `check_java` does not return any value.
    """
    try:
        jd = subprocess.check_output(["java", "-version"], stderr=subprocess.STDOUT).decode("utf-8")
        jd = jd[1:-1]
        _check_version(jd)
        logger.debug("Cool!! Java is available")
    except subprocess.CalledProcessError:
        logger.error("Java>= 17 must be installed")
        sys.exit(-1)


def delete_old_changelog() -> None:
    """The function `delete_old_changelog` deleted old changelog file."""
    Path(changelog_file).unlink(missing_ok=True)


def apkmirror_status_check(package_name: str) -> Any:
    """The `apkmirror_status_check` function checks if an app exists on APKMirror.

    Parameters
    ----------
    package_name : str
        The `package_name` parameter is a string that represents the name of the app package to check on
    APKMirror.

    Returns
    -------
        the response from the APKMirror API as a JSON object.
    """
    body = {"pnames": [package_name]}
    response = requests.post(APK_MIRROR_APK_CHECK, json=body, headers=request_header, timeout=60)
    return response.json()


def contains_any_word(string: str, words: list[str]) -> bool:
    """Checks if a string contains any word."""
    return any(word in string for word in words)


def datetime_to_ms_epoch(dt: datetime) -> int:
    """Returns millis since epoch."""
    microseconds = time.mktime(dt.timetuple()) * 1000000 + dt.microsecond
    return round(microseconds / float(1000))


def load_older_updates(env: Env) -> dict[str, Any]:
    """Load older updated from updates.json."""
    try:
        update_file_url = updates_file_url.format(
            github_repository=env.str("GITHUB_REPOSITORY"),
            branch_name=branch_name,
            updates_file=updates_file,
        )
        with urllib.request.urlopen(update_file_url) as url:
            return json.load(url)  # type: ignore[no-any-return]
    except Exception as e:  # noqa: BLE001
        logger.error(f"Failed to retrieve update file: {e}")
        return {}


def save_patch_info(app: "APP", updates_info: dict[str, Any]) -> dict[str, Any]:
    """Save version info a patching resources used to a file."""
    updates_info[app.app_name] = {
        app_version_key: app.app_version,
        patches_versions_key: app.get_patch_bundles_versions(),
        cli_version_key: app.resource["cli"]["version"],
        "ms_epoch_since_patched": datetime_to_ms_epoch(datetime.now(ZoneInfo(time_zone))),
        "date_patched": datetime.now(ZoneInfo(time_zone)),
        "app_dump": app.for_dump(),
    }
    return updates_info
