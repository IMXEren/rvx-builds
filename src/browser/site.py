"""Methods for fetching the site and source."""

import asyncio
import atexit
import base64
import json
import time
from typing import Any, Self, cast

from bs4 import BeautifulSoup
from loguru import logger
from pydoll.commands.fetch_commands import FetchCommands
from pydoll.constants import By as ByDoll
from pydoll.exceptions import ElementNotVisible
from pydoll.protocol.fetch.events import FetchEvent
from pydoll.protocol.fetch.types import RequestStage
from requests.structures import CaseInsensitiveDict

from src.browser.browser import Browser
from src.browser.cookies import Cookie, Cookies
from src.browser.exceptions import JSONExtractError, PageLoadError


class Source:
    """The `Response` like object from the browser request.

    Major purpose is to denote the page's html content
    hence, `text` attribute will contain the source html content.
    """

    def __init__(
        self: Self,
        source: str,
        status_code: str | int | None = None,
        headers: dict[str, str] | CaseInsensitiveDict | None = None,
        user_agent: str | None = None,
    ) -> None:
        self.__default__()
        self._text = source
        if isinstance(status_code, int):
            self.status_code = status_code
        elif isinstance(status_code, str):
            try:  # noqa: SIM105
                self.status_code = int(status_code)
            except:  # noqa: E722, S110
                pass
        if isinstance(headers, dict | CaseInsensitiveDict):
            self.headers.update(headers)
        self.user_agent = user_agent

    def __default__(self: Self) -> None:
        """Set attributes to default values."""
        self.status_code = None
        self.headers = CaseInsensitiveDict()
        self.user_agent = None

    @property
    def text(self: Self) -> str:
        """Returns the html content of the page."""
        return self._text

    def json(self: Self, **kwargs) -> Any:  # noqa: ANN003
        r"""Returns the json-encoded content of a response, if any.

        :param \*\*kwargs: Optional arguments that ``json.loads`` takes.
        :raises JSONDecodeError: If the response body does not
            contain valid json.
        :raises JSONExtractError: If the json extraction impl
            fails or no such json.

        The idea is basically that if the content view shows raw json,
        then it's possible to extract it. As done using `requests` package,
        i.e. if this fails with `JSONExtractError` then most likely `requests`
        would also fail for the same.
        """
        soup = BeautifulSoup(self.text, "html.parser")
        data = soup.select_one("body > pre")
        if not data:
            msg = "the json extractor implementation failed"
            raise JSONExtractError(msg)
        return json.loads(data.text, **kwargs)


class Site:
    """Convenient default class to load any site."""

    NOT_FOUND_STATUS_CODE: int = 404

    def __init__(self: Self, browser: Browser) -> None:
        self._browser = browser
        self._cdp = browser.browser
        self.status_code = None
        self.response_found = False
        self.redirected_url = None
        self.cf_encountered = False
        self.cf_encountered_on_url = None
        self.user_agent = None
        self._on_request_callback_id = None
        self._loaded = asyncio.Event()

    async def get(self: Self, url: str, timeout: int) -> Source:  # noqa: ASYNC109
        """Loads the url.

        Waits for the page to load until timeout is hit.
        Raises `PageLoadError` on load failure.
        """
        self.url = url
        self.timeout = timeout
        logger.info(f"Non-exclusive impl to fetch page for url -> {self.url} : Fetching with default config...")
        try:
            self.start = time.perf_counter()
            source = None
            self.tab = await self._cdp.new_tab()
            await self._browser.evader.apply_to_tab(self.tab)
            await self.add_network_listeners()
            async with self.tab.expect_and_bypass_cloudflare_captcha(
                custom_selector=(ByDoll.XPATH, "//*[div/div/input[@name='cf-turnstile-response']]"),
                time_before_click=3,
                time_to_wait_captcha=10,
            ):
                await self.tab.go_to(self.url, timeout=round(self.timeout))
                await self._browser.evader.apply_to_tab(self.tab)

            if not await self.check_if_loaded():
                msg = f"page load check mechanism failed out for: {url}"
                raise PageLoadError(msg)

            # Wait for page to load, if any redirects
            logger.info("Waiting for requested page to load...")
            await self.tab._wait_page_load(self.timeout)  # noqa: SLF001
            await asyncio.sleep(30000)
            source = await self.tab.page_source
            soup = BeautifulSoup(source, "html.parser")
            title = soup.select_one("title")
            if title and title.text.lower().startswith("just a moment"):
                msg = "cloudflare protection (captcha verification required)"
                raise PageLoadError(msg)

            return Source(
                source,
                status_code=self.status_code,
                headers=self.response_headers,
                user_agent=self.user_agent,
            )
        except PageLoadError:
            raise
        except Exception as e:
            msg = f"unknown error while loading --> {e}"
            raise PageLoadError(msg) from e

    async def check_if_loaded(self: Self) -> bool:
        """Checks if the page was loaded.

        Better to Implement it explicitly for any site based on element visibility or any other mechanism. Used with
        Browsers's Network Monitor (CDP).
        """
        try:
            async with asyncio.timeout(self.timeout):
                await self._loaded.wait()
        except TimeoutError:
            logger.error("Timeout occurred!")
            return False
        except Exception as e:  # noqa: BLE001
            logger.error(f"{e!r}")
            return False
        else:
            return self.response_found is not None and self.response_found
        finally:
            await self.remove_network_listeners()
            if self.response_found:
                logger.success(f"Response found set from interceptor [loaded]: {self.status_code}")
            else:
                logger.error(f"Response failed with possible status code: {self.status_code}")

    async def on_request(self: Self, event: dict[str, Any]) -> None:  # noqa: C901
        """Intercepts requests using CDP for the page."""
        params = event["params"]
        _params = {"requestId": params["requestId"]}
        if self.response_found:
            # Don't intercept, just continue the request
            await self.tab.continue_request(_params["requestId"])

        url = params["request"]["url"]
        status_code = params.get("responseStatusCode")
        self.user_agent = params["request"]["headers"]["User-Agent"]
        if _are_urls_equal(url, (self.cf_encountered_on_url or self.redirected_url or self.url)):
            self.status_code = status_code
            self.response_headers = _generate_headers(params.get("responseHeaders", []))
        logger.debug(f"Status code: {status_code} -> Site: {url}")
        if (
            _are_urls_equal(url, self.url)
            and self.cf_encountered
            and not str(status_code).startswith("2")
            and status_code != self.NOT_FOUND_STATUS_CODE
        ):
            self.cf_encountered = False
            logger.debug("CF re-encounter; Box appeared again")
        if params.get("responseStatusCode") in [301, 302, 303, 307, 308]:
            # redirected request
            if _are_urls_equal(url, (self.redirected_url or self.url)):
                lheader = next(
                    filter(lambda obj: obj["name"].lower() == "location", params["responseHeaders"]),
                    None,
                )
                self.redirected_url: str | None = lheader["value"] if lheader else None
            await self.tab.continue_request(_params["requestId"])
            return

        ## Ref: https://github.com/ttlns/Selenium-Driverless/blob/eca2bd74c17f071ce84b3eae63de81b74877956b/README.md?plain=1#L131
        cmd = FetchCommands.get_response_body(_params["requestId"])
        _body = await self.tab._execute_command(cmd)  # noqa: SLF001
        body = _body.get("result", None)
        if not body:
            e = _body["error"]  # type: ignore  # noqa: PGH003
            ERROR_CODE = -32000  # noqa: N806
            if (
                e["code"] == ERROR_CODE
                and e["message"] == "Can only get response body on requests captured after headers received."
            ):
                cmd = FetchCommands.continue_response(_params["requestId"])
                await self.tab._execute_command(cmd)  # noqa: SLF001
                return
            raise RuntimeError(e)

        await self.tab.continue_request(_params["requestId"])
        if not self.cf_encountered:
            await self._check_cf_encounter(url, dict(body))

        _status_code = str(params["responseStatusCode"])
        if _are_urls_equal(url, (self.redirected_url or self.url)) and (
            _status_code.startswith("2") or _status_code == str(self.NOT_FOUND_STATUS_CODE)
        ):
            await self.remove_network_listeners()
            self.status_code = status_code
            self.response_headers = _generate_headers(params.get("responseHeaders", []))
            self.response_found = True
            self._loaded.set()

        if _are_urls_equal(url, self.cf_encountered_on_url) and _status_code.startswith("2"):
            await self.remove_network_listeners()
            self.status_code = status_code
            self.response_headers = _generate_headers(params.get("responseHeaders", []))
            self.response_found = True
            self._loaded.set()

        return

    async def add_network_listeners(self: Self) -> None:
        """Add network listeners to the browser session."""
        await self.tab.enable_fetch_events(request_stage=RequestStage.RESPONSE)
        self._on_request_callback_id = await self.tab.on(FetchEvent.REQUEST_PAUSED, self.on_request)

    async def remove_network_listeners(self: Self) -> None:
        """Remove network listeners from the browser session."""
        if callback_id := self._on_request_callback_id:
            await self.tab.remove_callback(callback_id)
        await self.tab.disable_fetch_events()

    async def _check_cf_encounter(self: Self, url: str, body: dict[str, Any]) -> None:
        """Check if cf was encountered on the page."""
        try:
            body_decoded = body["body"]
            if body["base64Encoded"]:
                body_decoded = base64.b64decode(body["body"]).decode()
            soup = BeautifulSoup(body_decoded, "html.parser")
            title = soup.select_one("title")
        except:  # noqa: E722, S110
            pass
        else:
            if title and title.text.startswith("Just a moment"):
                self.cf_encountered = True
                self.cf_encountered_on_url = url
                logger.debug("[Cloudflare] encountered the checkbox challenge")
                await self.find_and_click()

    async def find_and_click(self) -> bool:
        """Find and clicks the checkbox to complete cf challenge."""
        selector = (ByDoll.XPATH, "//*[div/div/input[@name='cf-turnstile-response']]")
        element = await self.tab.find_or_wait_element(
            *selector,
            timeout=10,
            raise_exc=False,
        )
        if element and not isinstance(element, list):
            logger.debug("[Cloudflare] trying to click cf checkbox")
            await element.execute_script('this.style="width: 300px"')
            await asyncio.sleep(2)
            try:
                await element.click()
            except ElementNotVisible:
                logger.debug("[Cloudflare] cf checkbox element not visible to click")
                return False
            else:
                logger.debug("[Cloudflare] clicked cf checkbox")
                return True
        return False

def _are_urls_equal(url1: str | None, url2: str | None) -> bool:
    if url1 is None or url2 is None:
        return False
    if not url1.endswith("/"):
        url1 += "/"
    if not url2.endswith("/"):
        url2 += "/"
    return url1 == url2

def _generate_headers(headers: list[dict[str, str]]) -> CaseInsensitiveDict:
    gen_headers = CaseInsensitiveDict()
    for _header in headers:
        gen_headers.update({_header["name"]: _header["value"]})
    return gen_headers


async def source(url: str, timeout: int = 60) -> Source:  # noqa: ASYNC109
    """Wrapper to return html source of the url on successful loading.

    Waits for the page to load until timeout is hit.
    Raises `PageLoadError` on load failure.

    Still be prepared for any other exceptions for example, for now,
    setup won't run on Windows and you are responsible to download chrome,
    hence can error if they aren't detected when starting the Browser instance.
    """
    browser = None
    try:
        browser = await Browser.create()
        stored_cookies = Cookies()
        await browser.browser.set_cookies(stored_cookies.into_cookie_param_list())
        source = await browser.get(url, timeout)
        # Cookie doesn't have any extra methods so it's safe to assume it.
        stored_cookies.update_cookies(cast("list[Cookie]", await browser.browser.get_cookies()))
        return source
    finally:
        if browser:
            await browser.quit()


def _clear_stored_cookies() -> None:
    cookies = Cookies()
    cookies.delete_cookies()


atexit.register(_clear_stored_cookies)
