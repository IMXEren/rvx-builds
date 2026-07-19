"""Browser process manager, tab group abstraction, and utilities."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, ClassVar, Self

from loguru import logger

from src.browser.driver.runtime import BrowserRuntimeState, resolve_cdp_ws_url
from src.browser.exceptions import BrowserError, BrowserStartError, BrowserTabError
from src.browser.lifecycle.startup import BrowserLifecycle, BrowserShutdownState

if TYPE_CHECKING:
    from pathlib import Path

    from playwright.async_api import Browser as PWBrowser
    from playwright.async_api import BrowserContext as PWBrowserCtx
    from playwright.async_api import Page as PWPage
    from pydoll.browser import Chrome
    from pydoll.browser.tab import Tab as PDTab

    from src.browser.fingerprint import FingerprintManager


class Browser:
    """Singleton process manager for the shared browser instance.

    Manages the browser lifecycle (start, shutdown), CDP WebSocket connection,
    fingerprint configuration, shared Playwright persistent context, and pydoll
    Chrome instance. All methods are classmethods - there is only one browser
    process.

    Tab groups (concurrent browsing sessions) are created via :meth:`create`,
    which returns a :class:`TabGroup` instance.
    """

    _cdp_port: ClassVar[int] = 9222

    _MAX_GROUPS: ClassVar[int] = 3
    _runtime: ClassVar[BrowserRuntimeState] = BrowserRuntimeState(max_groups=_MAX_GROUPS)
    _lifecycle: ClassVar[BrowserLifecycle] = BrowserLifecycle(_runtime)

    @classmethod
    def _ensure_lifecycle(cls: type[Self]) -> None:
        """Ensure concrete runtime and lifecycle composition roots exist."""
        if cls._lifecycle is None:
            cls._lifecycle = BrowserLifecycle(cls._runtime)

    @classmethod
    def _webdata_path(cls: type[Self]) -> Path:
        return cls._lifecycle.webdata_path()

    @classmethod
    def unpack_profile(cls: type[Self], archive: str | Path | None = None) -> bool:
        """Restore ``_profile_dir`` from *archive* (zip)."""
        return cls._lifecycle.unpack_profile(archive)

    @classmethod
    def pack_profile(cls: type[Self], archive: str | Path | None = None) -> Path | None:
        """Zip ``_profile_dir`` into *archive*, skipping caches and journals."""
        return cls._lifecycle.pack_profile(archive)

    def __repr__(self: Self) -> str:
        """Return a human-readable representation of the browser state."""
        cls = type(self)
        state = "running" if cls.is_running() else "stopped"
        return f"<Browser({state}) port={cls._cdp_port} groups={len(cls._runtime.active_groups)}>"

    @classmethod
    def pw(cls: type[Self]) -> PWBrowser:
        """Shared Playwright Browser instance.

        Only use when the browser is already running.
        """
        return cls._runtime.get_pw_browser()

    @classmethod
    def pw_main_ctx(cls: type[Self]) -> PWBrowserCtx:
        """Shared Playwright Browser persistent ctx instance.

        Only use when the browser is already running.
        """
        return cls._runtime.get_pw_main_ctx()

    @classmethod
    def pd(cls: type[Self]) -> Chrome:
        """Shared pydoll Chrome instance.

        Only use when the browser is already running.
        """
        return cls._runtime.get_pd()

    @classmethod
    async def _get_cdp_ws_url(cls: type[Self]) -> str:
        """Queries the local debugging endpoint to fetch the active DevTools WebSocket URL."""
        return await resolve_cdp_ws_url(cls._lifecycle.cdp_port)

    @classmethod
    def is_running(cls: type[Self]) -> bool:
        """Is browser running."""
        runtime_is_running = getattr(cls._runtime, "is_running", None)
        if callable(runtime_is_running):
            return bool(runtime_is_running())
        return (
            cls._runtime.main_ctx is not None
            and not cls._runtime.main_ctx.is_closed()
            and cls._runtime.shared_pd is not None
        )

    @classmethod
    async def start(
        cls: type[Self],
    ) -> None:
        """Start the browser with a persistent ctx.

        Restores a cached profile package if available, primes a fresh profile
        if needed, injects Google as the default search engine, then launches.
        """
        await cls._lifecycle.start(
            is_running=cls.is_running,
            popup_handler=cls._handle_popup_page,
        )
        cls._cdp_port = cls._lifecycle.cdp_port

    @classmethod
    async def connect(cls: type[Self], ws_url: str) -> None:
        """Attach this process's drivers to a caller-owned remote CDP websocket."""
        if not isinstance(ws_url, str) or not ws_url.strip():
            msg = "Browser.connect requires a non-empty ws_url."
            raise BrowserStartError(msg)
        await cls._lifecycle.connect(
            is_running=cls.is_running,
            ws_url=ws_url,
            popup_handler=cls._handle_popup_page,
        )

    @classmethod
    async def create(cls: type[Self]) -> TabGroup:
        """Create a new :class:`TabGroup` in the shared browser process.

        Acquires a semaphore slot (max *MAX_GROUPS* concurrent groups).
        Starts the browser automatically if not already running.

        :raises BrowserStartError: if the browser is shutting down
            or group creation fails.
        """
        if cls._lifecycle.shutdown_state is BrowserShutdownState.IN_PROGRESS:
            msg = "Browser is shutting down - cannot create new tab groups."
            raise BrowserStartError(msg)

        try:
            instance = await cls._runtime.create_tab_group(TabGroup, cls.start, cls.is_running)
        except Exception as e:
            msg = f"Failed to start the browser due to {e}"
            raise BrowserStartError(msg) from e
        else:
            return instance

    @classmethod
    async def _create_from_running(cls: type[Self]) -> TabGroup:
        """Create a tab group in the running browser."""
        return await cls._runtime.create_group(TabGroup)

    @classmethod
    async def _new_page(cls: type[Self]) -> tuple[str, PWPage]:
        """Create a new tab using PW and add it to page map."""
        if cls._lifecycle.shutdown_state is BrowserShutdownState.IN_PROGRESS:
            msg = "Browser is shutting down - cannot create new pages."
            raise BrowserTabError(msg)

        return await cls._runtime.create_page()

    @classmethod
    def _add_tab_to_pd(cls: type[Self], target_id: str) -> PDTab:
        return cls._runtime._add_tab_to_pd(target_id)  # noqa: SLF001

    @classmethod
    def _remove_tab_from_pd(cls: type[Self], target_id: str) -> None:
        cls._runtime._remove_tab_from_pd(target_id)  # noqa: SLF001

    @classmethod
    async def get_pd_tab(cls: type[Self], target_id: str) -> PDTab | None:
        """Resolve the live Pydoll Tab for *target_id*, or ``None``."""
        return await cls._runtime.get_pd_tab(target_id)

    @classmethod
    def get_pw_page(cls: type[Self], target_id: str) -> PWPage | None:
        """Resolve the live Playwright Page for *target_id*, or ``None``."""
        return cls._runtime.get_pw_page(target_id)

    @classmethod
    async def minimize_main_window(cls: type[Self]) -> None:
        """Uses the active PyDoll CDP connection to minimize the browser window."""
        await cls._runtime.minimize_main_window()

    @classmethod
    async def _handle_popup_page(cls: type[Self], page: PWPage) -> None:
        """Handle involuntary popup pages (window.open, target=_blank).

        Attaches the new page to the :class:`TabGroup` that owns the opener,
        so it is tracked and cleaned up on quit/shutdown.
        """
        await cls._runtime.attach_popup_page(page)

    @classmethod
    async def _cleanup_resources(cls: type[Self]) -> None:
        """Compatibility facade for lifecycle-owned cleanup."""
        await cls._lifecycle._cleanup_resources()  # noqa: SLF001

    @classmethod
    async def _do_shutdown(cls: type[Self]) -> None:
        """Compatibility facade for lifecycle-owned shutdown finalization."""
        await cls._lifecycle._do_shutdown()  # noqa: SLF001

    @classmethod
    async def shutdown(cls: type[Self]) -> None:
        """Gracefully tear down all browser resources via lifecycle."""
        await cls._lifecycle.shutdown()

    @classmethod
    async def finally_cleanup(cls: type[Self], tg: TabGroup | None = None) -> None:
        """As the name suggests, use in finally blocks to quit as well as shutdown the Browser."""
        if tg is not None:
            try:
                await tg.quit()
            except Exception as e:  # noqa: BLE001
                logger.error(f"TabGroup quit failed during source cleanup: {e}")
        await cls.shutdown()

    @classmethod
    def _do_sync_chores_before_exit(cls: type[Self]) -> None:
        """The left out synchronous chores that need to be done before exiting."""
        cls._lifecycle.do_sync_chores_before_exit()

    @classmethod
    def _sync_atexit_fallback(cls) -> None:
        """Compatibility facade for lifecycle-owned synchronous fallback."""
        cls._lifecycle.sync_atexit_fallback()


class TabGroup:
    """Instance-level tab group.

    Represents a group of tabs (1 parent + n children) within the shared browser process.
    Created via Browser.create(). Holds per-group state and delegates to Browser classmethods
    for browser-level operations.
    """

    def __init__(self: Self, target_id: str, gid: int) -> None:
        """Initialize tab group with a parent tab.

        Private constructor. Always use Browser.create() to instantiate.
        """
        self.gid: int = gid
        self.target_id: str = target_id
        self.child_target_ids: list[str] = []
        self._lock: asyncio.Lock = asyncio.Lock()
        self._quitting: bool = False

    def __repr__(self: Self) -> str:
        """Return a human-readable representation of the tab group."""
        return f"<TabGroup #{self.gid} ({len(self.child_target_ids)} children)>"

    def pd(self: Self) -> Chrome:
        """Delegates to Browser.pd()."""
        return Browser.pd()

    @property
    def fp(self: Self) -> FingerprintManager:
        """Delegates to Browser lifecycle fingerprint state."""
        fp = Browser._lifecycle.fingerprint  # noqa: SLF001
        if fp is None:
            msg = "Browser fingerprint is not configured - call Browser.start() first."
            raise BrowserError(msg)
        return fp

    async def new_tab(self: Self) -> PDTab:
        """Spawns a dependent sub-tab and links it to this tab group."""
        target_id, page = await Browser._new_page()  # noqa: SLF001
        Browser._runtime.attach_page_to_group(page, self)  # noqa: SLF001
        async with self._lock:
            self.child_target_ids.append(target_id)
        tab = await Browser.get_pd_tab(target_id)
        if tab is None:
            msg = f"Failed to resolve newly created tab {target_id} in group #{self.gid}."
            raise BrowserTabError(msg)
        return tab

    @property
    def ppage(self: Self) -> PWPage:
        """Access to the parent Playwright Page for this group."""
        page = Browser._runtime.target_to_page_map.get(self.target_id)  # noqa: SLF001
        if page is None:
            msg = f"Parent page {self.target_id} in group #{self.gid} is no longer available."
            raise BrowserTabError(msg)
        return page

    @property
    async def ptab(self: Self) -> PDTab:
        """Access to the parent Pydoll Tab for this group."""
        tab = await Browser.get_pd_tab(self.target_id)
        if tab is None:
            msg = f"Parent tab {self.target_id} in group #{self.gid} is no longer available."
            raise BrowserTabError(msg)
        return tab

    async def close(self: Self, target_id: str) -> None:
        """Tears down a page associated with `target_id`.

        If the parent tab is targeted, the entire group is torn down
        via :meth:`quit`. Child tabs are closed individually and removed
        from the child list.
        """
        await Browser._runtime.close_group_target(self, target_id)  # noqa: SLF001

    async def quit(self: Self) -> None:
        """Tears down all pages linked to this tab group and returns the pool slot."""
        await Browser._runtime.close_group(self)  # noqa: SLF001
