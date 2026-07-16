"""Tests for Browser as a thin concrete composition facade."""

from __future__ import annotations

import asyncio
from typing import Self, cast
from unittest import IsolatedAsyncioTestCase, TestCase
from unittest.mock import AsyncMock, MagicMock

from src.browser import Browser as PackageBrowser
from src.browser import TabGroup as PackageTabGroup
from src.browser.browser import Browser, BrowserShutdownState, TabGroup
from src.browser.driver.runtime import BrowserRuntimeState
from src.browser.exceptions import FailedToStartBrowserError
from src.browser.lifecycle.startup import BrowserLifecycle

# ruff: noqa: PT009, PT027, SLF001


class BrowserFacadeProjectionTests(TestCase):
    """Synchronous facade projections delegate to concrete owners."""

    def setUp(self: Self) -> None:
        """Preserve global Browser composition for isolation."""
        self.original_runtime = Browser._runtime
        self.original_lifecycle = Browser._lifecycle

    def tearDown(self: Self) -> None:
        """Restore global Browser composition after each test."""
        Browser._runtime = self.original_runtime
        Browser._lifecycle = self.original_lifecycle

    def test_happy_path_public_facade_imports_and_callables_remain_stable(self: Self) -> None:
        """Happy path: Browser keeps public imports, enum order, and required callable facade."""
        self.assertIs(PackageBrowser, Browser)
        self.assertIs(PackageTabGroup, TabGroup)
        self.assertEqual(
            [state.name for state in BrowserShutdownState],
            ["NOT_STARTED", "IN_PROGRESS", "SUCCEEDED", "FAILED"],
        )
        for name in ["start", "shutdown", "create", "pd", "pw", "pw_main_ctx", "pack_profile", "unpack_profile"]:
            self.assertTrue(callable(getattr(Browser, name)), name)

    def test_invariant_runtime_projection_methods_own_three_driver_values(self: Self) -> None:
        """Invariant: Browser.pw, pw_main_ctx, pd, and is_running are runtime projections only."""
        runtime = MagicMock()
        values = [object(), object(), object()]
        runtime.get_pw_browser.return_value = values[0]
        runtime.get_pw_main_ctx.return_value = values[1]
        runtime.get_pd.return_value = values[2]
        runtime.is_running.return_value = True
        Browser._runtime = cast("BrowserRuntimeState", runtime)

        self.assertIs(Browser.pw(), values[0])
        self.assertIs(Browser.pw_main_ctx(), values[1])
        self.assertIs(Browser.pd(), values[2])
        self.assertTrue(Browser.is_running())
        runtime.get_pw_browser.assert_called_once_with()
        runtime.get_pw_main_ctx.assert_called_once_with()
        runtime.get_pd.assert_called_once_with()
        runtime.is_running.assert_called_once_with()

    def test_boundary_runtime_projection_error_message_is_preserved(self: Self) -> None:
        """Boundary/error path: stopped browser error is raised by runtime, not Browser state checks."""
        Browser._runtime = BrowserRuntimeState(max_groups=1)

        with self.assertRaisesRegex(RuntimeError, "Browser is not running - call Browser.start"):
            Browser.pd()

    def test_input_variation_connect_rejects_empty_or_non_string_ws_urls(self: Self) -> None:
        """Input variation: remote attach requires explicit websocket text at the facade boundary."""
        for value in ["", "   ", cast("str", None)]:
            with self.assertRaisesRegex(ValueError, "ws_url"):
                asyncio.run(Browser.connect(value))


class BrowserFacadeCreateTests(IsolatedAsyncioTestCase):
    """Async create/connect facade behavior delegates to concrete owners."""

    def setUp(self: Self) -> None:
        """Preserve global Browser composition for isolation."""
        self.original_runtime = Browser._runtime
        self.original_lifecycle = Browser._lifecycle

    def tearDown(self: Self) -> None:
        """Restore global Browser composition after each test."""
        Browser._runtime = self.original_runtime
        Browser._lifecycle = self.original_lifecycle

    async def test_state_transition_create_delegates_group_ownership_to_runtime(self: Self) -> None:
        """State transition: Browser wires lifecycle admission then runtime owns group creation."""
        group = TabGroup("target", 7)
        runtime = MagicMock()
        runtime.create_tab_group = AsyncMock(return_value=group)
        Browser._runtime = cast("BrowserRuntimeState", runtime)
        Browser._lifecycle = BrowserLifecycle(cast("BrowserRuntimeState", runtime))

        created = await Browser.create()

        self.assertIs(created, group)
        runtime.create_tab_group.assert_awaited_once()
        args = runtime.create_tab_group.await_args.args
        self.assertIs(args[0], TabGroup)
        self.assertTrue(callable(args[1]))
        self.assertTrue(callable(args[2]))

    async def test_error_path_create_rejects_lifecycle_shutdown_before_runtime_mutation(self: Self) -> None:
        """Error path: lifecycle shutdown admission blocks driver runtime mutation."""
        runtime = MagicMock()
        runtime.create_tab_group = AsyncMock()
        Browser._runtime = cast("BrowserRuntimeState", runtime)
        Browser._lifecycle = BrowserLifecycle(cast("BrowserRuntimeState", runtime))
        Browser._lifecycle._shutdown_state = BrowserShutdownState.IN_PROGRESS

        with self.assertRaisesRegex(FailedToStartBrowserError, "shutting down"):
            await Browser.create()

        runtime.create_tab_group.assert_not_awaited()

    async def test_happy_path_connect_delegates_remote_websocket_to_lifecycle(self: Self) -> None:
        """Happy path: Browser.connect keeps remote attach explicit and bypasses local start."""
        runtime = BrowserRuntimeState(max_groups=1)
        lifecycle = MagicMock()
        lifecycle.connect = AsyncMock()
        lifecycle.start = AsyncMock()
        Browser._runtime = runtime
        Browser._lifecycle = cast("BrowserLifecycle", lifecycle)

        await Browser.connect(ws_url="wss://remote.example/devtools/browser/123")

        lifecycle.connect.assert_awaited_once()
        lifecycle.start.assert_not_awaited()
        self.assertEqual(lifecycle.connect.await_args.kwargs["ws_url"], "wss://remote.example/devtools/browser/123")
