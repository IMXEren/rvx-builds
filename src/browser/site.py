"""Methods for fetching the site and source."""

import asyncio
import atexit
import base64
import contextlib
import json
import time
from typing import TYPE_CHECKING, Any, Self, cast
from urllib.parse import parse_qsl, urlsplit

from loguru import logger
from pydoll.browser.tab import Tab
from pydoll.commands.dom_commands import DomCommands
from pydoll.commands.fetch_commands import FetchCommands
from pydoll.commands.runtime_commands import RuntimeCommands
from pydoll.commands.target_commands import TargetCommands
from pydoll.constants import By as ByDoll
from pydoll.exceptions import ElementNotVisible
from pydoll.protocol.dom.types import Node as PDNode
from pydoll.protocol.fetch.events import FetchEvent
from pydoll.protocol.fetch.types import RequestStage
from requests.structures import CaseInsensitiveDict
from turbohtml import Element, Html, Node, Text
from turbohtml import parse as tb_parse

from src.browser.browser import Browser, TabGroup
from src.browser.cookies import Cookie, Cookies
from src.browser.exceptions import JSONExtractError, PageLoadError
from src.browser.utils import run_coroutine_sync
from src.signals import get_process_cancel_token

if TYPE_CHECKING:
    from collections.abc import Mapping


def _add_doctype_header(html: str) -> str:
    """Prepend the HTML5 doctype declaration to an HTML string."""
    return f"<!DOCTYPE html>\n{html}"


class Source:
    """The `Response` like object from the browser request.

    Major purpose is to denote the page's html content
    hence, `text` attribute will contain the source html content.
    """

    def __init__(
        self: Self,
        source: str,
        status_code: str | int | None = None,
        headers: dict[str, str] | CaseInsensitiveDict | None = None,  # type: ignore[type-arg]
        user_agent: str | None = None,
        url: str | None = None,
    ) -> None:
        self.__default__()
        self._text = source
        if isinstance(status_code, int):
            self.status_code = status_code
        elif isinstance(status_code, str):
            with contextlib.suppress(Exception):
                self.status_code = int(status_code)
        if isinstance(headers, dict | CaseInsensitiveDict):
            self.headers.update(headers)
        self.user_agent = user_agent
        self.url = url

    def __default__(self: Self) -> None:
        """Set attributes to default non-None values."""
        self.headers: CaseInsensitiveDict = CaseInsensitiveDict()  # type: ignore[type-arg]

    @property
    def text(self: Self) -> str:
        """Returns the html content of the page."""
        return self._text

    def json(self: Self, **kwargs: Any) -> Any:
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
        doc = tb_parse(self.text)
        data = doc.select_one("body > pre")
        if not data:
            msg = "the json extractor implementation failed"
            raise JSONExtractError(msg)
        return json.loads(data.text, **kwargs)


class Site:
    """Convenient default class to load any site."""

    NOT_FOUND_STATUS_CODE: int = 404

    def __init__(self: Self, tg: TabGroup) -> None:
        self._tg = tg
        self._loaded = asyncio.Event()
        self._reset()

    def _reset(self: Self) -> None:
        self.status_code: int | str | None = None
        self.response_found: bool = False
        self.response_headers: CaseInsensitiveDict | None = None  # type: ignore[type-arg]
        self.redirected_url: str | None = None
        self.cf_encountered: bool = False
        self.cf_encountered_on_url: str | None = None
        self.cf_auto_solve_enabled: bool = False
        self.user_agent: str | None = None
        self._on_request_callback_id: int | None = None
        self._loaded.clear()
        self.cleanup_done: bool = False

    def get_time_left(self: Self) -> float:
        """Get the left time before timeout."""
        elapsed = time.perf_counter() - self.start
        return max(0, self.timeout - elapsed)

    async def _new_tab(self: Self) -> Tab:
        """Returns a new tab in the current browser group."""
        return await self._tg.new_tab()

    async def get(self: Self, url: str, timeout: int) -> Source:  # noqa: ASYNC109
        """Loads the url.

        Waits for the page to load until timeout is hit.
        Raises `PageLoadError` on load failure.
        """
        self._reset()
        self.url = url
        self.timeout = timeout
        logger.info(f"Non-exclusive impl to fetch page for url -> {self.url} : Fetching with default config...")
        try:
            self.start = time.perf_counter()
            self.tab = await self._tg.ptab
            await self._add_network_listeners()
            await self.tab.enable_page_events()
            await self.tab.go_to(self.url, timeout=round(self.get_time_left()))

            if not await self._check_if_loaded():
                msg = f"page load check mechanism failed out for: {url}"
                raise PageLoadError(msg)

            # Wait for page to load, if any redirects
            logger.info("Waiting for requested page to load...")
            await asyncio.wait_for(self._wait_page_load(), timeout=self.get_time_left())
            tree = await self.build_dom_tree()
            title_el = tree.select_one("title")
            if title_el and title_el.text and title_el.text.lower().startswith("just a moment"):
                msg = "cloudflare protection (captcha verification required)"
                raise PageLoadError(msg)

            source = _add_doctype_header(tree.serialize(Html()))
            return Source(
                source=source,
                status_code=self.status_code,
                headers=self.response_headers,
                user_agent=self.user_agent,
            )
        except Exception as e:
            raise PageLoadError(e) from e
        finally:
            await self._cleanup()

    async def _cleanup(self) -> None:
        if self.cleanup_done:
            return
        if self.cf_auto_solve_enabled:
            await self.tab.disable_auto_solve_cloudflare_captcha()
        await self.tab.disable_page_events()
        await self._remove_network_listeners()
        self.cleanup_done = True

    async def _wait_page_load(self: Self) -> None:
        """Wait for document.readyState to be options.page_load_state."""
        while True:
            result = await self.tab.execute_script("document.readyState")
            state: str | None = result["result"]["result"].get("value")
            if state == self._tg.fp.options.page_load_state.value:
                return
            await asyncio.sleep(0.1)

    async def _check_if_loaded(self: Self) -> bool:
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
        else:
            return self.response_found is not None and self.response_found
        finally:
            await self._cleanup()
            if self.response_found:
                logger.success(f"Response found set from interceptor [loaded]: {self.status_code}")
            else:
                logger.error(f"Response failed with possible status code: {self.status_code}")

    async def _on_request(self: Self, event: dict[str, Any]) -> None:  # noqa: C901
        """Intercepts requests using CDP for the page."""
        params = event["params"]
        _params = {"requestId": params["requestId"]}
        if self.response_found:
            # Don't intercept, just continue the request
            await self.tab.continue_request(_params["requestId"])
            return

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
                self.redirected_url = lheader["value"] if lheader else None
            await self.tab.continue_request(_params["requestId"])
            return

        ## Ref: https://github.com/ttlns/Selenium-Driverless/blob/eca2bd74c17f071ce84b3eae63de81b74877956b/README.md?plain=1#L131
        cmd = FetchCommands.get_response_body(_params["requestId"])
        _body = await self.tab._execute_command(cmd)  # noqa: SLF001
        body_response = cast("Mapping[str, Any]", _body)
        body = body_response.get("result", None)
        if not body:
            e = body_response["error"]
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
            await self._remove_network_listeners()
            self.status_code = status_code
            self.response_headers = _generate_headers(params.get("responseHeaders", []))
            self.response_found = True
            self._loaded.set()

        if _are_urls_equal(url, self.cf_encountered_on_url) and _status_code.startswith("2"):
            await self._remove_network_listeners()
            self.status_code = status_code
            self.response_headers = _generate_headers(params.get("responseHeaders", []))
            self.response_found = True
            self._loaded.set()

        return

    async def _add_network_listeners(self: Self) -> None:
        """Add network listeners to the browser session."""
        await self.tab.enable_fetch_events(request_stage=RequestStage.RESPONSE)
        self._on_request_callback_id = await self.tab.on(FetchEvent.REQUEST_PAUSED, self._on_request)

    async def _remove_network_listeners(self: Self) -> None:
        """Remove network listeners from the browser session."""
        if callback_id := self._on_request_callback_id:
            await self.tab.remove_callback(callback_id)
        self._on_request_callback_id = None
        await self.tab.disable_fetch_events()

    async def _check_cf_encounter(self: Self, url: str, body: dict[str, Any]) -> None:
        """Check if cf was encountered on the page."""
        try:
            body_decoded = body["body"]
            if body["base64Encoded"]:
                body_decoded = base64.b64decode(body_decoded).decode()
            doc = tb_parse(body_decoded)
            title = doc.select_one("title")
        except Exception as e:  # noqa: BLE001
            logger.warning(f"Exception occurred while checking for cf: {e}")
        else:
            if title and title.text.startswith("Just a moment") and not self.cf_encountered:
                self.cf_encountered = True
                self.cf_encountered_on_url = url
                logger.debug("[Cloudflare] encountered the checkbox challenge")
                if not self.cf_auto_solve_enabled:
                    logger.debug("[Cloudflare] enabled auto-solving the challenge")
                    await self.tab.enable_auto_solve_cloudflare_captcha(time_before_click=1, time_to_wait_captcha=30)
                    self.cf_auto_solve_enabled = True

    async def _find_and_click(self) -> bool:
        """Find and clicks the checkbox to complete cf challenge."""
        logger.debug("[Cloudflare] v1: XPATH find + click")
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

    async def build_dom_tree(self) -> Element:
        """Build full DOM tree as a turbohtml Element.

        Uses ``DOM.getDocument(depth=-1, pierce=True)`` to get the full
        node tree, then walks it recursively to build a turbohtml tree.
        It is because the directly accessing the document.outerHTML
        misses iframe contentDocument.

        Returns
        -------
            The ``<html>`` Element as the root of the document.
        """
        resp = await self.tab._execute_command(  # noqa: SLF001
            DomCommands.get_document(depth=-1, pierce=True),
        )
        root = resp.get("result", {}).get("root", {})
        if not root:
            logger.warning("The document root is not available!")
            return Element("html")
        result = await self._build_turbo_node(root)
        if result is None or isinstance(result, Text):
            return Element("html")
        return result

    # CDP nodeType constants (DOM standard)
    _ELEMENT_NODE = 1
    _TEXT_NODE = 3
    _DOCUMENT_NODE = 9
    _DOCUMENT_FRAGMENT_NODE = 11

    async def _build_turbo_node(self, node: PDNode) -> Element | Text | None:
        """Map a CDP Node dict to a turbohtml Element/Text tree."""
        node_type = node.get("nodeType")

        if node_type == self._TEXT_NODE:
            return self._build_text_node(node)
        if node_type == self._DOCUMENT_NODE:
            return await self._build_document_node(node)
        if node_type == self._ELEMENT_NODE:
            return await self._build_element_node(node)
        if node_type == self._DOCUMENT_FRAGMENT_NODE:
            return None

        return None

    @staticmethod
    def _build_text_node(node: PDNode) -> Text:
        """Create a Text node from a CDP text node."""
        return Text(node.get("nodeValue") or "")

    async def _build_document_node(self, node: PDNode) -> Element | None:
        """Build the <html> Element from a CDP document node."""
        children = node.get("children") or []
        for child in children:
            if child.get("nodeName") == "HTML":
                result = await self._build_turbo_node(child)
                if isinstance(result, Element):
                    return result
                if isinstance(result, Text):
                    logger.warning(f"Expected a document node to be '{type(Element)}' but got '{type(Text)}'")
                    return None
        # Fallback: wrap all children in an <html> element
        html_el = Element("html")
        await self._append_children(html_el, node)
        return html_el

    async def _build_element_node(self, node: PDNode) -> Element:
        """Build an Element node from a CDP element node."""
        tag = (node.get("localName") or node.get("nodeName", "")).lower()
        attrs_list = node.get("attributes") or []
        attrs = dict(zip(attrs_list[::2], attrs_list[1::2], strict=False))
        el = Element(tag, attrs=attrs)

        if tag == "iframe":
            return await self._build_iframe_element(el, node)

        await self._append_children(el, node)
        return el

    async def _build_iframe_element(
        self,
        el: Element,
        node: PDNode,
    ) -> Element:
        """Populate an iframe element with its inner document HTML."""
        content_document = node.get("contentDocument")
        if content_document or node.get("frameId"):
            inner = await (
                self._build_turbo_node(content_document) if content_document else self._build_oopif_subtree(node)
            )
            if inner is not None:
                el.set_inner_html(inner.serialize(Html()))
        return el

    async def _append_children(
        self,
        el: Element,
        node: PDNode,
    ) -> None:
        """Append regular children and shadow root children to an element."""
        for child in node.get("children") or []:
            child_node = await self._build_turbo_node(child)
            if child_node is not None:
                el.append(child_node)

        for sr in node.get("shadowRoots") or []:
            for sr_child in sr.get("children") or []:
                child_node = await self._build_turbo_node(sr_child)
                if child_node is not None:
                    el.append(child_node)

    async def _build_oopif_subtree(self, node: PDNode) -> Element | None:
        """Attach to an OOPIF target, build its DOM subtree, and fix CDP-truncated text nodes via a second fetch."""
        frame_id = node.get("frameId")
        if frame_id is None:
            logger.warning(f"Expected frame id is None for node {node}")
            return None
        try:
            attach_resp = await self.tab._execute_command(  # noqa: SLF001
                TargetCommands.attach_to_target(frame_id, flatten=True),
            )
            session_id = attach_resp["result"]["sessionId"]

            # Build the CDP tree (preserves shadow roots)
            get_doc = DomCommands.get_document(depth=-1, pierce=True)
            get_doc["sessionId"] = session_id
            doc_resp = await self.tab._execute_command(get_doc)  # noqa: SLF001

            # Also fetch full HTML for untruncated text
            eval_cmd = RuntimeCommands.evaluate(
                expression="document.documentElement.outerHTML",
                return_by_value=True,
            )
            eval_cmd["sessionId"] = session_id
            html_resp = await self.tab._execute_command(eval_cmd)  # noqa: SLF001
            full_html: str = html_resp.get("result", {}).get("result", {}).get("value", "")

            await self.tab._execute_command(  # noqa: SLF001
                TargetCommands.detach_from_target(session_id),
            )

            root = doc_resp.get("result", {}).get("root", {})
            if not root:
                return None

            result = await self._build_turbo_node(root)

            # Fix truncated text nodes using the full HTML
            if result is not None and full_html:
                self._fix_truncated_text(result, full_html)

            return result if not isinstance(result, Text) else None
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                f"OOPIF target attach failed for {frame_id}: {exc}",
            )
            return None

    @staticmethod
    def _fix_truncated_text(
        tree: Node,
        full_html: str,
    ) -> None:
        """Replace CDP-truncated text nodes with their full versions."""
        ref_doc = tb_parse(f"<!DOCTYPE html>{full_html}")
        # Collect all Text nodes from both trees in document order
        cdp_texts: list[Text] = []
        ref_texts: list[Text] = []

        def _collect_texts(
            el: Node,
            into: list[Text],
        ) -> None:
            if isinstance(el, Text):
                into.append(el)
            elif hasattr(el, "children"):
                for child in el.children:
                    _collect_texts(child, into)

        _collect_texts(tree, cdp_texts)
        _collect_texts(ref_doc, ref_texts)

        # Walk both lists in lockstep; replace any CDP text that looks
        # truncated (ends with ellipsis) with the matching ref text.
        for cdp_t, ref_t in zip(cdp_texts, ref_texts, strict=False):
            cdp_val = cdp_t.text or ""
            ref_val = ref_t.text or ""
            if cdp_val.endswith("\u2026") and len(ref_val) > len(cdp_val):
                cdp_t.replace_with(Text(ref_val))


def _are_urls_equal(current_url: str | None, target_url: str | None) -> bool:
    """Compare a current URL against a target URL configuration.

    Matches if the current_url contains all query parameters specified in target_url,
    allowing current_url to have additional parameters.
    """
    if current_url is None or target_url is None:
        return False

    try:
        current = urlsplit(current_url)
        target = urlsplit(target_url)

        if current.scheme.lower() != target.scheme.lower():
            return False
        if current.netloc.lower() != target.netloc.lower():
            return False

        current_path = current.path if current.path.endswith("/") else current.path + "/"
        target_path = target.path if target.path.endswith("/") else target.path + "/"
        if current_path != target_path:
            return False

        if not target.query:
            return True

        current_params = set(parse_qsl(current.query))
        target_params = set(parse_qsl(target.query))

        return target_params.issubset(current_params)

    except Exception as e:  # noqa: BLE001
        logger.warning(f"Error comparing URLs: {current_url} vs {target_url}. Error: {e}")
        return False


def _generate_headers(headers: list[dict[str, str]]) -> CaseInsensitiveDict:  # type: ignore[type-arg]
    gen_headers: CaseInsensitiveDict = CaseInsensitiveDict()  # type: ignore[type-arg]
    for _header in headers:
        gen_headers.update({_header["name"]: _header["value"]})
    return gen_headers


# Site resolution registry.
# Register domain-specific Site implementations with :func:`register_site`.
# Patterns are matched against the URL hostname; the first match wins.
# Sites registered earlier take priority (inserted at index 0).
_site_registry: list[tuple[str, type[Site]]] = []


def register_site(pattern: str, site_cls: type[Site]) -> None:
    """Register a site implementation for URLs whose hostname matches *pattern*.

    *pattern* is a bare domain (``"example.com"``).  It matches exact
    hostnames and subdomains (``"example.com"``, ``"www.example.com"``).

    Registrations are checked in insertion order - later registrations
    take priority over earlier ones.
    """
    _site_registry.insert(0, (pattern, site_cls))


def resolve_site(tab_group: TabGroup, url: str) -> Site:
    """Return the :class:`Site` instance responsible for *url*."""
    host = urlsplit(url).hostname
    if host:
        for pattern, site_cls in _site_registry:
            if host == pattern or host.endswith("." + pattern):
                return site_cls(tab_group)
    return Site(tab_group)


async def fetch(tab_group: TabGroup, url: str, timeout: int = 60) -> Source:  # noqa: ASYNC109
    """Load *url* in *tab_group* and return its :class:`Source`.

    Waits for the page to load until *timeout* is hit.
    Raises :class:`PageLoadError` on load failure.
    """
    site = resolve_site(tab_group, url)
    return await site.get(url, timeout)


async def source(url: str, timeout: int = 60) -> Source:  # noqa: ASYNC109
    """Wrapper to return html source of the url on successful loading.

    Waits for the page to load until timeout is hit.
    Raises `PageLoadError` on load failure.

    Still be prepared for any other exceptions for example, for now,
    setup won't run on Windows and you are responsible to download chrome,
    hence can error if they aren't detected when starting the Browser instance.
    """
    tg = None
    try:
        await Browser.start()
        tg = await Browser.create()
        source = await get_process_cancel_token().race(
            fetch(tg, url, timeout),
            poll_interval=1,
        )
        # Don't load any cookies into browser as it already loads in persistent ctx
        stored_cookies = Cookies()
        stored_cookies.update_cookies(cast("list[Cookie]", await tg.pd().get_cookies()))
        return source
    finally:
        await Browser.finally_cleanup(tg)


def load_page_in_browser(url: str, timeout: int) -> Source | None:
    """Load *url* in a browser via :func:`run_coroutine_sync`.

    Returns the page source, or ``None`` on failure.
    """
    try:
        return run_coroutine_sync(source(url, timeout))  # type: ignore[no-any-return]
    except Exception as e:  # noqa: BLE001
        logger.exception(f"failed to load url in the browser: {e}")
        return None


def _clear_stored_cookies() -> None:
    cookies = Cookies()
    cookies.delete_cookies()


atexit.register(_clear_stored_cookies)
