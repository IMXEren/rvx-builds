"""Concrete runtime state container for browser driver ownership."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Literal, cast

import curl_cffi
from cloakbrowser import launch_persistent_context_async
from loguru import logger
from playwright.async_api import async_playwright
from pydoll.browser import Chrome
from pydoll.browser.tab import Tab as PDTab

from src.browser.exceptions import BrowserError, BrowserStartError, BrowserTabError

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable, Coroutine

    from playwright.async_api import Browser as PWBrowser
    from playwright.async_api import BrowserContext as PWBrowserCtx
    from playwright.async_api import Page as PWPage
    from playwright.async_api import Playwright
    from pydoll.browser.options import ChromiumOptions

    from src.browser.browser import TabGroup


@dataclass(frozen=True, slots=True)
class DriverStartupConfig:
    """Explicit startup inputs passed from lifecycle to the concrete driver."""

    profile_dir: str
    user_data_dir: str
    cdp_port: int
    fingerprint_options: ChromiumOptions
    launch_arguments: list[str]
    viewport: dict[str, int]
    locale: str
    popup_handler: Callable[[PWPage], None | Coroutine[None, None, None]]
    headless: bool = False
    geoip: bool = True
    humanize: bool = True
    color_scheme: Literal["light", "dark", "no-preference"] = "dark"


@dataclass(frozen=True, slots=True)
class DriverRemoteAttachConfig:
    """Explicit inputs for attaching driver clients to a remote CDP websocket."""

    ws_url: str
    popup_handler: Callable[[PWPage], None | Coroutine[None, None, None]]
    main_ctx: PWBrowserCtx | None = None


async def resolve_cdp_ws_url(cdp_port: int) -> str:
    """Resolve the active DevTools websocket URL for *cdp_port*."""
    try:
        endpoint = f"http://127.0.0.1:{cdp_port}/json/version"
        async with curl_cffi.AsyncSession() as session:
            response = await session.get(endpoint, timeout=15)
            response.raise_for_status()
            data = response.json()
            return cast("str", data["webSocketDebuggerUrl"])
    except Exception as exc:
        msg = f"Failed to resolve WebSocket debugger URL from port {cdp_port}. Is CloakBrowser running?"
        raise RuntimeError(msg) from exc


@dataclass(slots=True)
class BrowserRuntimeState:
    """Concrete owner for live browser driver state."""

    max_groups: int
    main_ctx: PWBrowserCtx | None = None
    shared_pd: Chrome | None = None
    target_to_page_map: dict[str, PWPage] = field(default_factory=dict)
    target_page_owned: dict[str, bool] = field(default_factory=dict)
    page_to_group: dict[PWPage, TabGroup | None] = field(default_factory=dict)
    active_groups: set[TabGroup] = field(default_factory=set)
    spawn_lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    group_semaphore: asyncio.Semaphore = field(init=False)
    next_group_id: int = 1
    cdp_playwright: Playwright | None = None
    cdp_browser: PWBrowser | None = None
    main_ctx_owned: bool = False

    def __post_init__(self) -> None:
        """Initialize semaphore after max_groups is available."""
        self.group_semaphore = asyncio.Semaphore(self.max_groups)

    async def start_live(self, config: DriverStartupConfig) -> None:
        """Start concrete browser clients from explicit lifecycle-owned config."""
        # Reset the group id
        self.next_group_id = 1
        self.shared_pd = Chrome(options=config.fingerprint_options)
        self.shared_pd._set_browser_preferences_in_user_data_dir(config.user_data_dir)  # noqa: SLF001

        self.main_ctx = await launch_persistent_context_async(
            headless=config.headless,
            args=config.launch_arguments,
            viewport=config.viewport,
            locale=config.locale,
            geoip=config.geoip,
            humanize=config.humanize,
            color_scheme=config.color_scheme,
            user_data_dir=config.user_data_dir,
        )
        self.main_ctx = cast("PWBrowserCtx", self.main_ctx)
        self.main_ctx_owned = True
        self.main_ctx.on("page", config.popup_handler)
        await asyncio.sleep(0.5)

        ws_url = await resolve_cdp_ws_url(config.cdp_port)
        main_tab = await self.shared_pd.connect(ws_url)
        main_page = self.main_ctx.pages[0]
        if main_tab._target_id is None:  # noqa: SLF001
            msg = "Failed to resolve target ID for the main browser tab."
            raise BrowserTabError(msg)
        self.target_to_page_map[main_tab._target_id] = main_page  # noqa: SLF001
        self.target_page_owned[main_tab._target_id] = True  # noqa: SLF001
        self.page_to_group[main_page] = None
        await self.minimize_main_window()

    async def attach_remote(self, config: DriverRemoteAttachConfig) -> None:
        """Attach concrete browser clients to a caller-owned remote CDP websocket."""
        self.next_group_id = 1
        self.shared_pd = Chrome()
        try:
            if config.main_ctx is None:
                cdp_playwright = await async_playwright().start()
                cdp_browser = await cdp_playwright.chromium.connect_over_cdp(config.ws_url)
                self.cdp_playwright = cdp_playwright
                self.cdp_browser = cdp_browser
                contexts = cdp_browser.contexts
                if contexts:
                    self.main_ctx = contexts[0]
                    self.main_ctx_owned = False
                else:
                    self.main_ctx = await cdp_browser.new_context()
                    self.main_ctx_owned = True
            else:
                self.main_ctx = cast("PWBrowserCtx", config.main_ctx)
                self.main_ctx_owned = False
            self.main_ctx.on("page", config.popup_handler)

            main_tab = await self.shared_pd.connect(config.ws_url)
            page_owned = self.main_ctx_owned
            if self.main_ctx.pages:
                main_page = self.main_ctx.pages[0]
            else:
                main_page = await self.main_ctx.new_page()
                page_owned = True
            cdp = await self.main_ctx.new_cdp_session(main_page)
            try:
                result = await cdp.send("Target.getTargetInfo")
            finally:
                await cdp.detach()
            target_id = result["targetInfo"]["targetId"]
            if main_tab._target_id is None or target_id is None:  # noqa: SLF001
                msg = "Failed to resolve target ID for the remote browser tab."
                raise BrowserTabError(msg)
            self.target_to_page_map[target_id] = main_page
            self.target_page_owned[target_id] = page_owned
            self.page_to_group[main_page] = None
            await self.minimize_main_window()
        except BaseException as e:
            await self.rollback_start()
            msg = "failed to attach remote cdp"
            raise BrowserStartError(msg) from e

    async def rollback_start(self) -> None:
        """Close partially acquired driver resources and clear live maps."""
        if self.shared_pd is not None:
            try:
                await self.shared_pd.close()
            except BaseException:  # noqa: BLE001
                logger.error("Failed to close PyDoll during startup rollback")
            self.shared_pd = None
        if self.main_ctx is not None and self.main_ctx_owned:
            try:
                await self.main_ctx.close()
            except BaseException:  # noqa: BLE001
                logger.error("Failed to close Playwright context during startup rollback")
        self.main_ctx = None
        self.main_ctx_owned = False
        if self.cdp_browser is not None:
            try:
                await self.cdp_browser.close()
            except BaseException:  # noqa: BLE001
                logger.error("Failed to close Playwright CDP browser during startup rollback")
            self.cdp_browser = None
        if self.cdp_playwright is not None:
            try:
                await self.cdp_playwright.stop()
            except BaseException:  # noqa: BLE001
                logger.error("Failed to stop Playwright during startup rollback")
            self.cdp_playwright = None
        self.target_to_page_map.clear()
        self.target_page_owned.clear()
        self.page_to_group.clear()

    def allocate_group_id(self) -> int:
        """Return the next concrete group id and advance the sequence."""
        group_id = self.next_group_id
        self.next_group_id += 1
        return group_id

    def _require_main_ctx(self) -> PWBrowserCtx:
        """Return the live Playwright context or raise a concrete runtime error."""
        if self.main_ctx is None:
            msg = "Browser is not running - call Browser.start() first."
            raise BrowserError(msg)
        return self.main_ctx

    def is_running(self) -> bool:
        """Return whether concrete runtime clients are live."""
        return self.main_ctx is not None and not self.main_ctx.is_closed() and self.shared_pd is not None

    def get_pw_browser(self) -> PWBrowser:
        """Return the shared Playwright browser projection."""
        ctx = self._require_main_ctx()
        browser = ctx.browser
        if browser is None:
            msg = "Playwright browser disconnected."
            raise BrowserError(msg)
        return browser

    def get_pw_main_ctx(self) -> PWBrowserCtx:
        """Return the shared Playwright persistent context projection."""
        return self._require_main_ctx()

    def get_pd(self) -> Chrome:
        """Return the shared PyDoll Chrome projection."""
        if self.shared_pd is None:
            msg = "Browser is not running - call Browser.start() first."
            raise BrowserError(msg)
        return self.shared_pd

    def attach_page_to_group(self, page: PWPage, group: TabGroup) -> None:
        """Associate a concrete Playwright page projection with a tab group."""
        self.page_to_group[page] = group

    async def create_tab_group(
        self,
        group_factory: Callable[[str, int], TabGroup],
        ensure_running: Callable[[], Awaitable[None]],
        is_running: Callable[[], bool],
    ) -> TabGroup:
        """Own group semaphore admission and create a group after startup if needed."""
        await self.group_semaphore.acquire()

        try:
            if not is_running():
                await ensure_running()
            if not is_running():
                msg = "Failed to start from already running: Master browser process is not active."
                raise BrowserError(msg)
            return await self.create_group(group_factory)
        except Exception:
            self.group_semaphore.release()
            raise

    def _add_tab_to_pd(self, target_id: str) -> PDTab:
        """Add a PyDoll tab entry for *target_id* and return it."""
        if self.shared_pd is None:
            msg = "Browser is not running - call Browser.start() first."
            raise BrowserError(msg)
        tab = PDTab(
            self.shared_pd,
            **self.shared_pd._get_tab_kwargs(target_id, browser_context_id=None),  # noqa: SLF001
        )
        self.shared_pd._tabs_opened[target_id] = tab  # noqa: SLF001
        return tab

    def _remove_tab_from_pd(self, target_id: str) -> None:
        """Remove a PyDoll tab entry if the concrete client is present."""
        if self.shared_pd is None:
            return
        self.shared_pd._tabs_opened.pop(target_id, None)  # noqa: SLF001

    async def create_page(self) -> tuple[str, PWPage]:
        """Create a concrete Playwright page and track its target id."""
        main_ctx = self._require_main_ctx()
        async with self.spawn_lock:
            page = await main_ctx.new_page()
            cdp = await main_ctx.new_cdp_session(page)
            result = await cdp.send("Target.getTargetInfo")
            await cdp.detach()
            target_id = result["targetInfo"]["targetId"]
            self._add_tab_to_pd(target_id)
            self.target_to_page_map[target_id] = page
            self.target_page_owned[target_id] = True
        return (target_id, page)

    async def create_group(self, group_factory: Callable[[str, int], TabGroup]) -> TabGroup:
        """Create and register a concrete tab group from a new parent page."""
        target_id, page = await self.create_page()
        group = group_factory(target_id, self.allocate_group_id())
        self.page_to_group[page] = group
        async with self.spawn_lock:
            self.active_groups.add(group)
        return group

    async def get_pd_tab(self, target_id: str) -> PDTab | None:
        """Resolve the live PyDoll tab for *target_id*, or ``None``."""
        if self.shared_pd is None:
            msg = "Browser is not running - call Browser.start() first."
            raise BrowserError(msg)
        tabs = await self.shared_pd.get_opened_tabs()
        for tab in tabs:
            if tab._target_id == target_id:  # noqa: SLF001
                return tab
        return None

    def get_pw_page(self, target_id: str) -> PWPage | None:
        """Resolve the live Playwright page for *target_id*, or ``None``."""
        return self.target_to_page_map.get(target_id)

    async def minimize_main_window(self) -> None:
        """Minimize the browser window when a PyDoll client is connected."""
        if self.shared_pd is None:
            return
        await self.shared_pd.set_window_minimized()

    async def attach_popup_page(self, page: PWPage) -> None:
        """Attach an involuntary popup page to its opener's tab group."""
        opener = await page.opener()
        if opener is None:
            return
        group = self.page_to_group.get(opener)
        if group is None:
            return

        main_ctx = self._require_main_ctx()
        try:
            cdp = await main_ctx.new_cdp_session(page)
            result = await cdp.send("Target.getTargetInfo")
            await cdp.detach()
        except Exception:  # noqa: BLE001
            logger.debug("Failed to resolve target ID for popup page; discarding.")
            return

        target_id = result["targetInfo"]["targetId"]
        async with self.spawn_lock:
            self._add_tab_to_pd(target_id)
            self.target_to_page_map[target_id] = page
            self.target_page_owned[target_id] = True
        self.page_to_group[page] = group
        async with group._lock:  # noqa: SLF001
            group.child_target_ids.append(target_id)
        logger.debug(f"Popup tab {target_id} attached to group {group.gid}")

    async def close_group_target(self, group: TabGroup, target_id: str) -> None:
        """Close one target owned by a group, or the whole group for parent target."""
        if target_id == group.target_id:
            await self.close_group(group)
            return

        async with group._lock:  # noqa: SLF001
            if target_id not in group.child_target_ids:
                msg = f"Target {target_id} does not belong to this tab group."
                raise BrowserTabError(msg)

        target_page = self.get_pw_page(target_id)
        if target_page is not None and self.target_page_owned.get(target_id, True):
            await target_page.close()

        async with self.spawn_lock:
            self._remove_tab_from_pd(target_id)
            self.target_to_page_map.pop(target_id, None)
            self.target_page_owned.pop(target_id, None)
        async with group._lock:  # noqa: SLF001
            if target_id in group.child_target_ids:
                group.child_target_ids.remove(target_id)
        if target_page is not None:
            self.page_to_group.pop(target_page, None)

    async def close_group(self, group: TabGroup) -> None:
        """Close all targets for a group and release its concurrency slot once."""
        if group._quitting:  # noqa: SLF001
            return
        group._quitting = True  # noqa: SLF001
        try:
            async with group._lock:  # noqa: SLF001
                child_ids = list(group.child_target_ids)
            for child_id in child_ids:
                await self.close_group_target(group, child_id)

            parent_page = self.get_pw_page(group.target_id)
            if parent_page is not None and self.target_page_owned.get(group.target_id, True):
                await parent_page.close()
            async with self.spawn_lock:
                self._remove_tab_from_pd(group.target_id)
                self.target_to_page_map.pop(group.target_id, None)
                self.target_page_owned.pop(group.target_id, None)
                if parent_page is not None:
                    self.page_to_group.pop(parent_page, None)
        finally:
            async with self.spawn_lock:
                self.active_groups.discard(group)
                self.group_semaphore.release()

    async def close_all_groups_and_pages(self) -> None:
        """Close all registered groups and orphan pages, then clear runtime maps."""
        async with self.spawn_lock:
            running_groups = list(self.active_groups)

        if running_groups:
            logger.debug(f"Force-closing {len(running_groups)} dangling tab groups...")
            await asyncio.gather(*(self.close_group(group) for group in running_groups), return_exceptions=True)

        async with self.spawn_lock:
            self.active_groups.clear()
            active_pages = [
                page
                for target_id, page in self.target_to_page_map.items()
                if self.target_page_owned.get(target_id, True)
            ]

        if active_pages:
            logger.debug("Closing orphan tabs...")
            await asyncio.gather(*(page.close() for page in active_pages), return_exceptions=True)

        async with self.spawn_lock:
            self.target_to_page_map.clear()
            self.target_page_owned.clear()
            self.page_to_group.clear()
