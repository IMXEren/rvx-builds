"""Concrete driver/lifecycle boundary tests for simple browser split."""

from __future__ import annotations

import ast
from pathlib import Path
from typing import Any, Self
from unittest import IsolatedAsyncioTestCase, TestCase
from unittest.mock import ANY, AsyncMock, MagicMock, patch

import src.browser.driver as driver_pkg
from src.browser import Browser as PublicBrowser
from src.browser import TabGroup as PublicTabGroup
from src.browser.browser import Browser, BrowserShutdownState, TabGroup
from src.browser.driver import BrowserRuntimeState, DriverRemoteAttachConfig, DriverStartupConfig
from src.browser.exceptions import FailedToStartBrowserError
from src.browser.lifecycle import BrowserLifecycle

# ruff: noqa: PT009, PT027, SLF001, S108


_ROOT = Path(__file__).resolve().parents[1]


def _source(path: str) -> str:
    return (_ROOT / path).read_text(encoding="utf-8")


class ConcreteBoundaryShapeTests(TestCase):
    """Concrete split forbids resurrecting protocol or adapter boundaries."""

    def test_happy_path_public_imports_expose_browser_and_tab_group(self) -> None:
        """Happy path: public package imports preserve Browser and TabGroup compatibility."""
        self.assertIs(PublicBrowser, Browser)
        self.assertIs(PublicTabGroup, TabGroup)

    def test_happy_path_driver_exports_only_concrete_runtime_symbols(self) -> None:
        """Happy path: driver package exposes concrete runtime classes only."""
        self.assertIs(driver_pkg.BrowserRuntimeState, BrowserRuntimeState)
        self.assertIs(driver_pkg.DriverStartupConfig, DriverStartupConfig)
        self.assertIs(driver_pkg.DriverRemoteAttachConfig, DriverRemoteAttachConfig)
        for stale in ("LifecycleDriver", "BrowserDriver", "DriverStartRequest", "LegacyCompatibilityDriverAdapter"):
            self.assertFalse(hasattr(driver_pkg, stale), stale)

    def test_invariant_no_interface_or_adapter_imports_in_concrete_files(self) -> None:
        """Invariant: production split contains no stale interface or adapter imports."""
        for path in ("src/browser/browser.py", "src/browser/lifecycle/startup.py", "src/browser/driver/runtime.py"):
            src = _source(path)
            self.assertNotIn("src.browser.driver.interfaces", src)
            self.assertNotIn("src.browser.lifecycle.adapter", src)
            self.assertNotIn("Protocol", src)

    def test_boundary_startup_config_has_cdp_port_not_ws_url(self) -> None:
        """Boundary: lifecycle passes launch input, not a pre-resolved websocket."""
        fields = set(DriverStartupConfig.__dataclass_fields__)

        self.assertIn("cdp_port", fields)
        self.assertNotIn("ws_url", fields)

    def test_boundary_remote_attach_config_has_ws_url_not_lifecycle_inputs(self) -> None:
        """Boundary: remote attach passes websocket input, not local launch/profile fields."""
        fields = set(DriverRemoteAttachConfig.__dataclass_fields__)

        self.assertIn("ws_url", fields)
        self.assertIn("popup_handler", fields)
        self.assertNotIn("cdp_port", fields)
        self.assertNotIn("profile_dir", fields)
        self.assertNotIn("user_data_dir", fields)

    def test_error_path_browser_start_does_not_define_admission_callback(self) -> None:
        """Error path: Browser.start delegates shutdown admission to lifecycle."""
        src = _source("src/browser/browser.py")
        tree = ast.parse(src)
        browser = next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == "Browser")
        start = next(
            node
            for node in browser.body
            if isinstance(node, ast.AsyncFunctionDef) and node.name == "start"
        )
        segment = ast.get_source_segment(src, start) or ""

        self.assertNotIn("def can_start", segment)
        self.assertNotIn("can_start=", segment)

    def test_input_variation_driver_config_accepts_three_distinct_ports(self) -> None:
        """Input variation: typical, atypical, and high CDP ports are launch inputs."""
        ports = [9222, 0, 65535]
        configs = [
            DriverStartupConfig(
                profile_dir="/tmp/p",
                user_data_dir="/tmp/p",
                cdp_port=port,
                fingerprint_options=object(),
                launch_arguments=[],
                viewport={"width": 1, "height": 1},
                locale="en-US,en",
                popup_handler=lambda _page: None,
            )
            for port in ports
        ]

        self.assertEqual([config.cdp_port for config in configs], ports)

    def test_state_transition_browser_keeps_runtime_and_lifecycle_owners(self) -> None:
        """State transition: Browser composition root holds concrete owner objects."""
        self.assertIsInstance(Browser._runtime, BrowserRuntimeState)
        self.assertIsInstance(Browser._lifecycle, BrowserLifecycle)

    def test_invariant_shutdown_state_fields_live_on_lifecycle_not_browser_or_driver(self) -> None:
        """Invariant: shutdown state, signal metadata, and atexit flags are lifecycle-owned."""
        lifecycle_fields = set(BrowserLifecycle.__dataclass_fields__)
        runtime_fields = set(BrowserRuntimeState.__dataclass_fields__)
        owned_fields = {
            "_shutdown_state",
            "_shutdown_error",
            "_shutdown_task",
            "_signal_exit_task",
            "_signal_handlers_registered",
            "_atexit_registered",
            "_prior_signal_info",
            "_preserved_signal_info",
            "_owns_local_profile",
        }

        self.assertLessEqual(owned_fields, lifecycle_fields)
        self.assertTrue(owned_fields.isdisjoint(runtime_fields))
        for field in owned_fields:
            self.assertNotIn(field, Browser.__dict__)

    def test_happy_path_browser_shutdown_delegates_to_lifecycle(self) -> None:
        """Happy path: Browser exposes shutdown as a facade over concrete lifecycle."""
        src = _source("src/browser/browser.py")
        tree = ast.parse(src)
        browser = next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == "Browser")
        shutdown = next(
            node
            for node in browser.body
            if isinstance(node, ast.AsyncFunctionDef) and node.name == "shutdown"
        )
        segment = ast.get_source_segment(src, shutdown) or ""

        self.assertIn("cls._lifecycle.shutdown()", segment)
        self.assertNotIn("create_task", segment)
        self.assertNotIn("_shutdown_state =", segment)

    def test_boundary_browser_sync_fallback_delegates_to_lifecycle(self) -> None:
        """Boundary: atexit profile preservation state is not finalized on Browser."""
        src = _source("src/browser/browser.py")
        tree = ast.parse(src)
        browser = next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == "Browser")
        fallback = next(
            node
            for node in browser.body
            if isinstance(node, ast.FunctionDef) and node.name == "_sync_atexit_fallback"
        )
        segment = ast.get_source_segment(src, fallback) or ""

        self.assertIn("cls._lifecycle.sync_atexit_fallback()", segment)
        self.assertNotIn("_shutdown_state", segment)
        self.assertNotIn("pack_profile()", segment)


class RuntimeStartupOrderingTests(IsolatedAsyncioTestCase):
    """Driver launches Chrome before resolving and connecting CDP websocket."""

    async def test_happy_path_launches_then_resolves_then_connects(self: Self) -> None:
        """Happy path: no websocket lookup happens before persistent context launch."""
        events: list[str] = []
        context = MagicMock()
        page = MagicMock()
        context.pages = [page]
        context.on = MagicMock(side_effect=lambda *_args: events.append("page-handler"))
        chrome = MagicMock()
        chrome._set_browser_preferences_in_user_data_dir = MagicMock(side_effect=lambda _path: events.append("prefs"))
        chrome.connect = AsyncMock(side_effect=lambda _ws: events.append("connect") or _tab("main"))
        chrome.set_window_minimized = AsyncMock(side_effect=lambda: events.append("minimize"))

        async def launch(**_kwargs: Any) -> object:
            events.append("launch")
            return context

        async def resolve(_port: int) -> str:
            events.append("resolve")
            return "ws://resolved"

        runtime = BrowserRuntimeState(max_groups=1)
        with (
            patch("src.browser.driver.runtime.Chrome", return_value=chrome),
            patch("src.browser.driver.runtime.launch_persistent_context_async", side_effect=launch),
            patch("src.browser.driver.runtime.resolve_cdp_ws_url", side_effect=resolve),
            patch("src.browser.driver.runtime.asyncio.sleep", AsyncMock()),
        ):
            await runtime.start_live(_config())

        self.assertEqual(events, ["prefs", "launch", "page-handler", "resolve", "connect", "minimize"])
        chrome.connect.assert_awaited_once_with("ws://resolved")
        self.assertEqual(runtime.target_to_page_map, {"main": page})

    async def test_error_path_resolver_failure_rolls_back_partial_runtime(self: Self) -> None:
        """Error path: caller rollback closes launched context after resolver failure."""
        context = AsyncMock()
        context.pages = [MagicMock()]
        context.on = MagicMock()
        chrome = AsyncMock()
        chrome._set_browser_preferences_in_user_data_dir = MagicMock()

        runtime = BrowserRuntimeState(max_groups=1)
        with (
            patch("src.browser.driver.runtime.Chrome", return_value=chrome),
            patch("src.browser.driver.runtime.launch_persistent_context_async", AsyncMock(return_value=context)),
            patch("src.browser.driver.runtime.resolve_cdp_ws_url", AsyncMock(side_effect=RuntimeError("no ws"))),
            patch("src.browser.driver.runtime.asyncio.sleep", AsyncMock()),
        ):
            with self.assertRaisesRegex(RuntimeError, "no ws"):
                await runtime.start_live(_config(cdp_port=9333))
            await runtime.rollback_start()

        context.close.assert_awaited_once()
        chrome.close.assert_awaited_once()
        self.assertIsNone(runtime.main_ctx)
        self.assertIsNone(runtime.shared_pd)

    async def test_happy_path_remote_attach_connects_without_launch_or_resolve(self: Self) -> None:
        """Happy path: remote attach uses supplied websocket and bypasses local launch."""
        context = MagicMock()
        page = MagicMock()
        context.pages = [page]
        context.on = MagicMock()
        cdp = AsyncMock()
        cdp.send = AsyncMock(return_value={"targetInfo": {"targetId": "pw-remote-main"}})
        cdp.detach = AsyncMock()
        context.new_cdp_session = AsyncMock(return_value=cdp)
        chrome = MagicMock()
        chrome.connect = AsyncMock(return_value=_tab("remote-main"))
        chrome.set_window_minimized = AsyncMock()

        runtime = BrowserRuntimeState(max_groups=1)
        with (
            patch("src.browser.driver.runtime.Chrome", return_value=chrome),
            patch("src.browser.driver.runtime.launch_persistent_context_async", AsyncMock()) as launch,
            patch("src.browser.driver.runtime.resolve_cdp_ws_url", AsyncMock()) as resolve,
        ):
            await runtime.attach_remote(
                DriverRemoteAttachConfig(
                    ws_url="wss://cloud.example/devtools/browser/123",
                    main_ctx=context,
                    popup_handler=lambda _page: None,
                ),
            )

        launch.assert_not_awaited()
        resolve.assert_not_awaited()
        chrome.connect.assert_awaited_once_with("wss://cloud.example/devtools/browser/123")
        context.on.assert_called_once_with("page", ANY)
        self.assertEqual(runtime.target_to_page_map, {"pw-remote-main": page})

    async def test_happy_path_remote_attach_initializes_playwright_and_pydoll_clients(self: Self) -> None:
        """Happy path: remote attach creates both local CDP clients for one remote browser."""
        page = MagicMock()
        context = MagicMock()
        context.pages = [page]
        context.on = MagicMock()
        cdp = AsyncMock()
        cdp.send = AsyncMock(return_value={"targetInfo": {"targetId": "pw-main"}})
        cdp.detach = AsyncMock()
        context.new_cdp_session = AsyncMock(return_value=cdp)
        cdp_browser = MagicMock()
        cdp_browser.contexts = [context]
        cdp_browser.chromium.connect_over_cdp = AsyncMock(return_value=cdp_browser)
        playwright = MagicMock()
        playwright.chromium.connect_over_cdp = AsyncMock(return_value=cdp_browser)
        playwright.stop = AsyncMock()
        playwright_owner = MagicMock()
        playwright_owner.start = AsyncMock(return_value=playwright)
        chrome = MagicMock()
        chrome.connect = AsyncMock(return_value=_tab("remote-main"))
        chrome.set_window_minimized = AsyncMock()

        runtime = BrowserRuntimeState(max_groups=1)
        with (
            patch("src.browser.driver.runtime.Chrome", return_value=chrome),
            patch("src.browser.driver.runtime.async_playwright", return_value=playwright_owner),
            patch("src.browser.driver.runtime.launch_persistent_context_async", AsyncMock()) as launch,
            patch("src.browser.driver.runtime.resolve_cdp_ws_url", AsyncMock()) as resolve,
        ):
            await runtime.attach_remote(
                DriverRemoteAttachConfig(
                    ws_url="wss://cloud.example/devtools/browser/both",
                    popup_handler=lambda _page: None,
                ),
            )

        launch.assert_not_awaited()
        resolve.assert_not_awaited()
        playwright.chromium.connect_over_cdp.assert_awaited_once_with("wss://cloud.example/devtools/browser/both")
        chrome.connect.assert_awaited_once_with("wss://cloud.example/devtools/browser/both")
        self.assertIs(runtime.cdp_playwright, playwright)
        self.assertIs(runtime.cdp_browser, cdp_browser)
        self.assertIs(runtime.main_ctx, context)
        self.assertEqual(runtime.target_to_page_map, {"pw-main": page})

    async def test_boundary_remote_attach_creates_page_for_empty_existing_context(self: Self) -> None:
        """Boundary: an empty borrowed CDP context gets one owned page without owning the context."""
        page = AsyncMock()
        cdp = AsyncMock()
        cdp.send = AsyncMock(return_value={"targetInfo": {"targetId": "created-target"}})
        cdp.detach = AsyncMock()
        context = MagicMock()
        context.pages = []
        context.on = MagicMock()
        context.new_page = AsyncMock(return_value=page)
        context.new_cdp_session = AsyncMock(return_value=cdp)
        cdp_browser = MagicMock()
        cdp_browser.contexts = [context]
        playwright = MagicMock()
        playwright.chromium.connect_over_cdp = AsyncMock(return_value=cdp_browser)
        playwright.stop = AsyncMock()
        playwright_owner = MagicMock()
        playwright_owner.start = AsyncMock(return_value=playwright)
        chrome = MagicMock()
        chrome.connect = AsyncMock(return_value=_tab("pydoll-browser-target"))
        chrome.set_window_minimized = AsyncMock()

        runtime = BrowserRuntimeState(max_groups=1)
        with (
            patch("src.browser.driver.runtime.Chrome", return_value=chrome),
            patch("src.browser.driver.runtime.async_playwright", return_value=playwright_owner),
        ):
            await runtime.attach_remote(
                DriverRemoteAttachConfig(
                    ws_url="wss://cloud.example/devtools/browser/empty-context",
                    popup_handler=lambda _page: None,
                ),
            )

        self.assertIs(runtime.main_ctx, context)
        self.assertFalse(runtime.main_ctx_owned)
        context.new_page.assert_awaited_once_with()
        context.new_cdp_session.assert_awaited_once_with(page)
        cdp.detach.assert_awaited_once_with()
        chrome.connect.assert_awaited_once_with("wss://cloud.example/devtools/browser/empty-context")
        self.assertEqual(runtime.target_to_page_map, {"created-target": page})
        self.assertEqual(runtime.target_page_owned, {"created-target": True})
        self.assertEqual(runtime.page_to_group, {page: None})

    async def test_state_transition_remote_attach_no_context_creates_owned_context_and_page(self: Self) -> None:
        """State transition: remote attach owns the context only when it creates it."""
        page = AsyncMock()
        cdp = AsyncMock()
        cdp.send = AsyncMock(return_value={"targetInfo": {"targetId": "owned-target"}})
        cdp.detach = AsyncMock()
        context = MagicMock()
        context.pages = []
        context.on = MagicMock()
        context.new_page = AsyncMock(return_value=page)
        context.new_cdp_session = AsyncMock(return_value=cdp)
        cdp_browser = MagicMock()
        cdp_browser.contexts = []
        cdp_browser.new_context = AsyncMock(return_value=context)
        playwright = MagicMock()
        playwright.chromium.connect_over_cdp = AsyncMock(return_value=cdp_browser)
        playwright_owner = MagicMock()
        playwright_owner.start = AsyncMock(return_value=playwright)
        chrome = MagicMock()
        chrome.connect = AsyncMock(return_value=_tab("pydoll-browser-target"))
        chrome.set_window_minimized = AsyncMock()

        runtime = BrowserRuntimeState(max_groups=1)
        with (
            patch("src.browser.driver.runtime.Chrome", return_value=chrome),
            patch("src.browser.driver.runtime.async_playwright", return_value=playwright_owner),
        ):
            await runtime.attach_remote(
                DriverRemoteAttachConfig(
                    ws_url="wss://cloud.example/devtools/browser/no-context",
                    popup_handler=lambda _page: None,
                ),
            )

        cdp_browser.new_context.assert_awaited_once_with()
        context.new_page.assert_awaited_once_with()
        self.assertTrue(runtime.main_ctx_owned)
        self.assertEqual(runtime.target_to_page_map, {"owned-target": page})
        self.assertEqual(runtime.target_page_owned, {"owned-target": True})

    async def test_boundary_remote_shutdown_keeps_borrowed_context_and_page_open(self: Self) -> None:
        """Boundary: remote shutdown releases local clients but not borrowed Playwright objects."""
        context = AsyncMock()
        page = AsyncMock()
        context.pages = [page]
        context.on = MagicMock()
        chrome = AsyncMock()
        chrome.connect = AsyncMock(return_value=_tab("remote-main"))
        cdp_browser = AsyncMock()
        playwright = AsyncMock()

        original_runtime = Browser._runtime
        original_lifecycle = Browser._lifecycle
        try:
            runtime = BrowserRuntimeState(max_groups=1)
            Browser._runtime = runtime
            Browser._lifecycle = BrowserLifecycle(runtime)
            runtime.shared_pd = chrome
            runtime.main_ctx = context
            runtime.main_ctx_owned = False
            runtime.target_to_page_map = {"remote-main": page}
            runtime.target_page_owned = {"remote-main": False}
            runtime.page_to_group = {page: None}
            runtime.cdp_browser = cdp_browser
            runtime.cdp_playwright = playwright
            await Browser.shutdown()
        finally:
            Browser._runtime = original_runtime
            Browser._lifecycle = original_lifecycle

        page.close.assert_not_awaited()
        context.close.assert_not_awaited()
        chrome.close.assert_awaited_once()
        cdp_browser.close.assert_awaited_once()
        playwright.stop.assert_awaited_once()

    async def test_error_path_remote_rollback_keeps_borrowed_context_open(self: Self) -> None:
        """Error path: remote rollback closes local clients without closing borrowed context."""
        context = AsyncMock()
        context.pages = [MagicMock()]
        context.on = MagicMock()
        chrome = AsyncMock()
        chrome.connect = AsyncMock(side_effect=RuntimeError("remote refused"))

        runtime = BrowserRuntimeState(max_groups=1)
        with (
            patch("src.browser.driver.runtime.Chrome", return_value=chrome),
            self.assertRaisesRegex(RuntimeError, "remote refused"),
        ):
            await runtime.attach_remote(
                DriverRemoteAttachConfig(
                    ws_url="wss://cloud.example/devtools/browser/borrowed",
                    main_ctx=context,
                    popup_handler=lambda _page: None,
                ),
            )

        chrome.close.assert_awaited_once()
        context.close.assert_not_awaited()
        self.assertIsNone(runtime.main_ctx)
        self.assertIsNone(runtime.shared_pd)

    async def test_error_path_remote_attach_failure_rolls_back_partial_runtime(self: Self) -> None:
        """Error path: remote attach failure closes only live driver resources it opened."""
        context = AsyncMock()
        context.pages = [MagicMock()]
        context.on = MagicMock()
        chrome = AsyncMock()
        chrome.connect = AsyncMock(side_effect=RuntimeError("remote refused"))

        runtime = BrowserRuntimeState(max_groups=1)
        with (
            patch("src.browser.driver.runtime.Chrome", return_value=chrome),
            self.assertRaisesRegex(RuntimeError, "remote refused"),
        ):
            await runtime.attach_remote(
                DriverRemoteAttachConfig(
                    ws_url="wss://cloud.example/devtools/browser/456",
                    main_ctx=context,
                    popup_handler=lambda _page: None,
                ),
            )

        chrome.close.assert_awaited_once()
        context.close.assert_not_awaited()
        self.assertIsNone(runtime.main_ctx)
        self.assertIsNone(runtime.shared_pd)


class LifecycleAdmissionTests(IsolatedAsyncioTestCase):
    """Lifecycle owns shutdown admission state transitions."""

    async def test_illegal_start_while_shutdown_in_progress_raises(self: Self) -> None:
        """State transition: IN_PROGRESS blocks startup before side effects."""
        lifecycle = BrowserLifecycle(_driver_double())
        lifecycle._shutdown_state = BrowserShutdownState.IN_PROGRESS

        with self.assertRaisesRegex(FailedToStartBrowserError, "shutting down"):
            await lifecycle.start(
                is_running=lambda: False,
                popup_handler=lambda _page: None,
            )

    async def test_idempotent_terminal_shutdown_state_is_reset_before_start(self: Self) -> None:
        """State transition: terminal shutdown state resets once before startup."""
        lifecycle = BrowserLifecycle(_driver_double())
        lifecycle._shutdown_state = BrowserShutdownState.SUCCEEDED
        lifecycle._shutdown_error = RuntimeError("stored")
        lifecycle._shutdown_task = MagicMock()

        await lifecycle.start(
            is_running=lambda: True,
            popup_handler=lambda _page: None,
        )

        self.assertIs(lifecycle._shutdown_state, BrowserShutdownState.NOT_STARTED)
        self.assertIsNone(lifecycle._shutdown_error)
        self.assertIsNone(lifecycle._shutdown_task)


class BrowserRemoteFacadeTests(IsolatedAsyncioTestCase):
    """Browser.connect is the explicit public facade for remote CDP ownership."""

    async def test_happy_path_connect_forwards_explicit_ws_url(self: Self) -> None:
        """Happy path: Browser.connect forwards ws_url to lifecycle without local startup."""
        lifecycle = MagicMock(spec=BrowserLifecycle)
        lifecycle.connect = AsyncMock()

        with patch.object(Browser, "_lifecycle", lifecycle):
            await Browser.connect("wss://cloud.example/devtools/browser/facade")

        lifecycle.connect.assert_awaited_once()
        kwargs = lifecycle.connect.await_args.kwargs
        self.assertEqual(kwargs["ws_url"], "wss://cloud.example/devtools/browser/facade")
        self.assertIs(kwargs["is_running"].__func__, Browser.is_running.__func__)

    async def test_boundary_connect_rejects_empty_ws_url_values(self: Self) -> None:
        """Boundary: empty, whitespace, and non-string ws_url values fail before lifecycle."""
        lifecycle = MagicMock(spec=BrowserLifecycle)
        lifecycle.connect = AsyncMock()

        with patch.object(Browser, "_lifecycle", lifecycle):
            for value in ("", "   ", None):
                with self.subTest(value=value), self.assertRaisesRegex(ValueError, "non-empty ws_url"):
                    await Browser.connect(value)  # type: ignore[arg-type]  # reason: exercise runtime guard

        lifecycle.connect.assert_not_awaited()

    async def test_invariant_remote_connect_bypasses_local_lifecycle_hooks(self: Self) -> None:
        """Invariant: remote ws_url attach does not run local profile or binary startup hooks."""
        original_runtime = Browser._runtime
        original_lifecycle = Browser._lifecycle
        driver = _driver_double()
        driver.is_running = MagicMock(return_value=False)
        lifecycle = BrowserLifecycle(driver)
        Browser._runtime = driver
        Browser._lifecycle = lifecycle
        try:
            with (
                patch.object(BrowserLifecycle, "unpack_profile") as unpack,
                patch.object(BrowserLifecycle, "_prime_profile", new=AsyncMock()) as prime,
                patch.object(BrowserLifecycle, "_inject_search_engine") as inject,
                patch("src.browser.lifecycle.startup.ensure_binary") as ensure,
                patch("src.browser.lifecycle.startup.get_free_port") as port,
                patch("src.browser.driver.runtime.resolve_cdp_ws_url", new=AsyncMock()) as resolve,
                patch.object(BrowserLifecycle, "_register_signal_handlers"),
                patch.object(BrowserLifecycle, "_register_atexit"),
            ):
                await Browser.connect("wss://cloud.example/devtools/browser/no-local")
        finally:
            Browser._runtime = original_runtime
            Browser._lifecycle = original_lifecycle

        driver.attach_remote.assert_awaited_once()
        attach_config = driver.attach_remote.await_args.args[0]
        self.assertEqual(attach_config.ws_url, "wss://cloud.example/devtools/browser/no-local")
        unpack.assert_not_called()
        prime.assert_not_awaited()
        inject.assert_not_called()
        ensure.assert_not_called()
        port.assert_not_called()
        resolve.assert_not_awaited()
        self.assertFalse(lifecycle._owns_local_profile)

    async def test_boundary_remote_shutdown_has_no_local_profile_archive_side_effect(self: Self) -> None:
        """Boundary: remote shutdown disconnects owned clients without packing local profile."""
        original_runtime = Browser._runtime
        original_lifecycle = Browser._lifecycle
        try:
            runtime = BrowserRuntimeState(max_groups=1)
            lifecycle = BrowserLifecycle(runtime)
            shared_pd = AsyncMock()
            main_ctx = AsyncMock()
            cdp_browser = AsyncMock()
            cdp_playwright = AsyncMock()
            Browser._runtime = runtime
            Browser._lifecycle = lifecycle
            runtime.shared_pd = shared_pd
            runtime.main_ctx = main_ctx
            runtime.main_ctx_owned = False
            runtime.cdp_browser = cdp_browser
            runtime.cdp_playwright = cdp_playwright
            lifecycle._owns_local_profile = False

            with patch.object(BrowserLifecycle, "pack_profile") as pack:
                await Browser.shutdown()
        finally:
            Browser._runtime = original_runtime
            Browser._lifecycle = original_lifecycle

        shared_pd.close.assert_awaited_once()
        main_ctx.close.assert_not_awaited()
        cdp_browser.close.assert_awaited_once()
        cdp_playwright.stop.assert_awaited_once()
        pack.assert_not_called()


def _config(*, cdp_port: int = 9222) -> DriverStartupConfig:
    return DriverStartupConfig(
        profile_dir="/tmp/profile",
        user_data_dir="/tmp/profile",
        cdp_port=cdp_port,
        fingerprint_options=object(),
        launch_arguments=["--remote-debugging-port=9222"],
        viewport={"width": 1920, "height": 980},
        locale="en-US,en",
        popup_handler=lambda _page: None,
    )


def _tab(target_id: str) -> MagicMock:
    tab = MagicMock()
    tab._target_id = target_id
    return tab


def _driver_double() -> MagicMock:
    driver = MagicMock(spec=BrowserRuntimeState)
    driver.start_live = AsyncMock()
    driver.rollback_start = AsyncMock()
    return driver
