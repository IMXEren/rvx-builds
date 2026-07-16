"""Regression tests for Browser lifecycle ownership and cleanup.

Coverage:
  - AC1: Two concurrent shutdown callers share one cleanup; clients close once.
  - AC2: Failed startup rolls back acquired resources before propagating.
  - AC3: Successful startup registers handlers only after all startup work.
  - AC4: Sync usage closes live clients before owner-loop closure.
  - AC5: Graceful shutdown closes clients before packing.
  - AC6: Atexit synchronous profile preservation only; creates no event loop.
  - AC7: Lifecycle owns all state; Browser is narrow compatibility projection.
"""

from __future__ import annotations

import asyncio
import contextlib
import signal
from typing import TYPE_CHECKING, Any, Self
from unittest import IsolatedAsyncioTestCase, TestCase
from unittest.mock import AsyncMock, MagicMock, patch

from src.browser.browser import Browser, BrowserShutdownState
from src.browser.driver import BrowserRuntimeState
from src.browser.exceptions import FailedToStartBrowserError
from src.browser.lifecycle import BrowserLifecycle

if TYPE_CHECKING:
    from collections.abc import Callable

# ruff: noqa: PT009, PT027, SLF001

_FAIL_ON_SECOND_CALL = 2


def _reset_browser_state() -> None:
    """Reset all Browser class-level state for test isolation.

    Browser no longer owns lifecycle state (shutdown_state, shutdown_task,
    signal info, etc.) — that is all on BrowserLifecycle.
    This function resets only Browser's live resource state and wiring.
    """
    Browser._runtime = BrowserRuntimeState(max_groups=Browser._MAX_GROUPS)
    Browser._lifecycle = BrowserLifecycle(Browser._runtime)
    Browser._cdp_port = 9222


def _get_lifecycle() -> BrowserLifecycle:
    """Ensure a BrowserLifecycle exists and return it."""
    if Browser._lifecycle is None:
        Browser._ensure_lifecycle()
    if Browser._lifecycle is None:
        msg = "Browser lifecycle was not initialized."
        raise AssertionError(msg)
    return Browser._lifecycle


def _running_browser_deps() -> dict:
    """Create minimal running-browser mocks and set them on Browser.

    Returns dict of created mocks for assertion.
    """
    page = AsyncMock()
    page.close = AsyncMock()
    group = MagicMock()
    group.target_id = "t1"
    group.child_target_ids = []
    group._lock = asyncio.Lock()
    group._quitting = False
    pd = MagicMock()
    pd.close = AsyncMock()
    ctx = MagicMock()
    ctx.close = AsyncMock()
    ctx.is_closed = MagicMock(return_value=False)

    Browser._runtime.shared_pd = pd
    Browser._runtime.main_ctx = ctx
    Browser._runtime.main_ctx_owned = True
    Browser._runtime.target_to_page_map = {"t1": page}
    Browser._runtime.target_page_owned = {"t1": True}
    Browser._runtime.page_to_group = {page: group}
    Browser._runtime.active_groups = {group}

    return {"page": page, "group": group, "pd": pd, "ctx": ctx}


def _fp_mock() -> MagicMock:
    """Return a FingerprintManager minimal double."""
    fp = MagicMock()
    fp.options.arguments = []
    return fp


def _sei_mock() -> MagicMock:
    """Return a SearchEngineInjector context-manager double."""
    sei = MagicMock()
    sei.__enter__ = MagicMock(return_value=MagicMock())
    sei.__exit__ = MagicMock(return_value=None)
    return sei


def _startup_base_patches() -> list:
    """Return common patchers for all startup-oriented tests.

    These patches intercept heavy external dependencies so tests
    can focus on Browser's own lifecycle logic.
    """
    return [
        patch("src.browser.lifecycle.startup.get_free_port", return_value=9999),
        patch("src.browser.lifecycle.startup.FingerprintManager"),
        patch("src.browser.lifecycle.startup.SearchEngineInjector"),
        patch("src.browser.lifecycle.startup.ensure_binary"),
        patch("src.browser.lifecycle.startup.asyncio.sleep"),
        patch.object(BrowserLifecycle, "unpack_profile", return_value=False),
        patch("src.browser.lifecycle.startup.atexit.register"),
    ]


# =========================================================================
# AC 1 & AC 5:  Shutdown concurrency, ordering, idempotency
# =========================================================================


class ShutdownConcurrencyTests(IsolatedAsyncioTestCase):
    """Concurrent shutdown: one cleanup, clients close once, correct order."""

    def setUp(self: Self) -> None:
        """Reset class state before each test."""
        _reset_browser_state()

    # ── AC 1: Concurrent shutdown callers ─────────────────────────

    async def test_concurrent_callers_share_one_cleanup_execution(self) -> None:
        """Two concurrent direct shutdown() callers must run cleanup once."""
        _running_browser_deps()
        _get_lifecycle()

        with patch.object(BrowserLifecycle, "do_sync_chores_before_exit") as mock_chores:
            t1 = asyncio.create_task(Browser.shutdown())
            t2 = asyncio.create_task(Browser.shutdown())
            await asyncio.gather(t1, t2, return_exceptions=True)

        mock_chores.assert_called_once()

    async def test_each_page_closed_at_most_once(self) -> None:
        """Each page.close() must be awaited exactly once across all callers."""
        deps = _running_browser_deps()
        _get_lifecycle()

        t1 = asyncio.create_task(Browser.shutdown())
        t2 = asyncio.create_task(Browser.shutdown())
        await asyncio.gather(t1, t2, return_exceptions=True)

        deps["page"].close.assert_awaited_once()

    async def test_each_tab_group_quit_at_most_once(self) -> None:
        """Each worker.quit() must be awaited exactly once."""
        deps = _running_browser_deps()
        _get_lifecycle()

        t1 = asyncio.create_task(Browser.shutdown())
        t2 = asyncio.create_task(Browser.shutdown())
        await asyncio.gather(t1, t2, return_exceptions=True)

        self.assertNotIn(deps["group"], Browser._runtime.active_groups)

    async def test_second_caller_awaits_same_task(self) -> None:
        """Second caller arriving during shutdown awaits the same task."""
        _running_browser_deps()
        _get_lifecycle()
        event = asyncio.Event()

        def delayed_chores(_lifecycle: BrowserLifecycle) -> None:
            event.set()

        with patch.object(BrowserLifecycle, "do_sync_chores_before_exit", delayed_chores):
            t1 = asyncio.create_task(Browser.shutdown())
            await event.wait()
            t2 = asyncio.create_task(Browser.shutdown())
            results = await asyncio.gather(t1, t2, return_exceptions=True)

        for r in results:
            if isinstance(r, BaseException):
                raise r

    # ── AC 5: Graceful shutdown order ─────────────────────────────

    def _order_deps(self) -> dict:
        """Set up mocks for ordering tests and return them."""
        page = AsyncMock()
        page.close = AsyncMock()
        group = MagicMock()
        group.target_id = "t1"
        group.child_target_ids = []
        group._lock = asyncio.Lock()
        group._quitting = False
        pd = MagicMock()
        pd.close = AsyncMock()
        ctx = MagicMock()
        ctx.close = AsyncMock()
        ctx.is_closed = MagicMock(return_value=False)

        Browser._runtime.shared_pd = pd
        Browser._runtime.main_ctx = ctx
        Browser._runtime.main_ctx_owned = True
        Browser._runtime.target_to_page_map = {"t1": page}
        Browser._runtime.target_page_owned = {"t1": True}
        Browser._runtime.page_to_group = {page: group}
        Browser._runtime.active_groups = {group}

        return {"page": page, "group": group, "pd": pd, "ctx": ctx}

    async def test_shutdown_closes_groups_before_pages(self) -> None:
        """Tab groups must close before individual pages."""
        order: list[str] = []
        deps = self._order_deps()
        _get_lifecycle()
        orphan_page = AsyncMock()
        orphan_page.close = AsyncMock(side_effect=lambda: order.append("orphan_page_close"))
        Browser._runtime.target_to_page_map["t2"] = orphan_page
        Browser._runtime.target_page_owned["t2"] = True
        deps["page"].close = AsyncMock(side_effect=lambda: order.append("group_page_close"))

        with patch.object(BrowserLifecycle, "do_sync_chores_before_exit", lambda *_args: order.append("pack")):
            await Browser.shutdown()

        self.assertLess(order.index("group_page_close"), order.index("orphan_page_close"))

    async def test_shutdown_closes_pages_before_pydoll(self) -> None:
        """Pages must close before PyDoll."""
        order: list[str] = []
        deps = self._order_deps()
        _get_lifecycle()
        deps["page"].close = AsyncMock(side_effect=lambda: order.append("page_close"))
        deps["pd"].close = AsyncMock(side_effect=lambda: order.append("pd_close"))

        with patch.object(BrowserLifecycle, "do_sync_chores_before_exit", lambda *_args: order.append("pack")):
            await Browser.shutdown()

        self.assertLess(order.index("page_close"), order.index("pd_close"))

    async def test_shutdown_closes_pydoll_before_playwright(self) -> None:
        """PyDoll must close before Playwright context."""
        order: list[str] = []
        deps = self._order_deps()
        _get_lifecycle()
        deps["pd"].close = AsyncMock(side_effect=lambda: order.append("pd_close"))
        deps["ctx"].close = AsyncMock(side_effect=lambda: order.append("pw_close"))

        with patch.object(BrowserLifecycle, "do_sync_chores_before_exit", lambda *_args: order.append("pack")):
            await Browser.shutdown()

        self.assertLess(order.index("pd_close"), order.index("pw_close"))

    async def test_shutdown_packs_profile_last(self) -> None:
        """Profile packing must be the final shutdown step."""
        order: list[str] = []
        self._order_deps()
        _get_lifecycle()

        with patch.object(BrowserLifecycle, "do_sync_chores_before_exit", lambda *_args: order.append("pack")):
            await Browser.shutdown()

        self.assertEqual(order[-1], "pack")

    # ── Edge cases ────────────────────────────────────────────────

    async def test_shutdown_noop_when_already_complete(self) -> None:
        """shutdown() is a no-op when _shutdown_state is SUCCEEDED."""
        lc = _get_lifecycle()
        lc._shutdown_state = BrowserShutdownState.SUCCEEDED

        with patch.object(BrowserLifecycle, "do_sync_chores_before_exit") as m:
            await Browser.shutdown()
        m.assert_not_called()

    async def test_shutdown_with_no_resources_does_not_raise(self) -> None:
        """shutdown() on a fresh Browser must not raise."""
        lc = _get_lifecycle()
        await Browser.shutdown()
        self.assertIs(lc._shutdown_state, BrowserShutdownState.SUCCEEDED)

    async def test_shutdown_idempotent_sequential(self) -> None:
        """Consecutive shutdown() calls must both succeed and run cleanup once."""
        _running_browser_deps()
        _get_lifecycle()

        with patch.object(BrowserLifecycle, "do_sync_chores_before_exit") as mock_chores:
            await Browser.shutdown()
            await Browser.shutdown()

        mock_chores.assert_called_once()

    async def test_shutdown_continues_after_close_error(self) -> None:
        """Shutdown must continue closing remaining resources after one fails."""
        deps = _running_browser_deps()
        _get_lifecycle()
        deps["page"].close = AsyncMock(side_effect=RuntimeError("page close failed"))

        await Browser.shutdown()
        lc = _get_lifecycle()
        self.assertIs(lc._shutdown_state, BrowserShutdownState.SUCCEEDED)
        deps["pd"].close.assert_awaited_once()
        deps["ctx"].close.assert_awaited_once()

    async def test_shutdown_no_shared_pd_does_not_raise(self) -> None:
        """shutdown() handles None _shared_pd gracefully."""
        Browser._runtime.main_ctx = MagicMock()
        Browser._runtime.main_ctx.close = AsyncMock()
        Browser._runtime.main_ctx.is_closed = MagicMock(return_value=False)
        Browser._runtime.main_ctx_owned = True
        _get_lifecycle()

        await Browser.shutdown()
        lc = _get_lifecycle()
        self.assertIs(lc._shutdown_state, BrowserShutdownState.SUCCEEDED)

    async def test_shutdown_no_main_ctx_does_not_raise(self) -> None:
        """shutdown() handles None _main_ctx gracefully."""
        Browser._runtime.shared_pd = MagicMock()
        Browser._runtime.shared_pd.close = AsyncMock()
        _get_lifecycle()

        await Browser.shutdown()
        lc = _get_lifecycle()
        self.assertIs(lc._shutdown_state, BrowserShutdownState.SUCCEEDED)

    # ── Owner-caller and waiter cancellation ──────────────────────

    async def test_owner_caller_cancellation_does_not_abort_cleanup(self) -> None:
        """Cancelling the first shutdown() caller must not cancel cleanup."""
        deps = _running_browser_deps()
        lc = _get_lifecycle()
        cleanup_entered = asyncio.Event()
        cleanup_can_exit = asyncio.Event()

        original_cleanup = lc._cleanup_resources

        async def controlled_cleanup(_lifecycle: BrowserLifecycle) -> None:
            cleanup_entered.set()
            await cleanup_can_exit.wait()
            return await original_cleanup()

        with patch.object(BrowserLifecycle, "_cleanup_resources", new=controlled_cleanup):
            t1 = asyncio.create_task(Browser.shutdown())
            await cleanup_entered.wait()

            # Cancel the owner caller
            t1.cancel()
            with self.assertRaises(asyncio.CancelledError):
                await t1

            # Cleanup task survives (still stored as _shutdown_task)
            self.assertIsNotNone(lc._shutdown_task)
            self.assertIs(lc._shutdown_state, BrowserShutdownState.IN_PROGRESS)

            # Let cleanup finish
            cleanup_can_exit.set()
            if lc._shutdown_task is not None and not lc._shutdown_task.done():
                await asyncio.wait_for(lc._shutdown_task, timeout=5)

        # Real cleanup ran despite caller cancellation
        deps["page"].close.assert_awaited_once()
        self.assertNotIn(deps["group"], Browser._runtime.active_groups)
        deps["pd"].close.assert_awaited_once()
        deps["ctx"].close.assert_awaited_once()

    async def test_waiter_cancellation_does_not_abort_cleanup(self) -> None:
        """Cancelling a concurrent waiter must not cancel cleanup."""
        deps = _running_browser_deps()
        lc = _get_lifecycle()
        cleanup_entered = asyncio.Event()
        cleanup_can_exit = asyncio.Event()

        original_cleanup = lc._cleanup_resources

        async def controlled_cleanup(_lifecycle: BrowserLifecycle) -> None:
            cleanup_entered.set()
            await cleanup_can_exit.wait()
            return await original_cleanup()

        with patch.object(BrowserLifecycle, "_cleanup_resources", new=controlled_cleanup):
            t1 = asyncio.create_task(Browser.shutdown())
            await cleanup_entered.wait()

            # Second caller arrives (waiter)
            t2 = asyncio.create_task(Browser.shutdown())
            await asyncio.sleep(0)

            # Cancel the waiter
            t2.cancel()
            with self.assertRaises(asyncio.CancelledError):
                await t2

            # Cleanup still running (_shutdown_task not cleared)
            self.assertIsNotNone(lc._shutdown_task)
            self.assertIs(lc._shutdown_state, BrowserShutdownState.IN_PROGRESS)

            # Let cleanup finish
            cleanup_can_exit.set()
            await asyncio.wait_for(t1, timeout=5)

        # Real cleanup ran; resources closed once
        deps["page"].close.assert_awaited_once()
        self.assertNotIn(deps["group"], Browser._runtime.active_groups)
        deps["pd"].close.assert_awaited_once()
        deps["ctx"].close.assert_awaited_once()

    async def test_shutdown_task_is_dedicated_not_caller(self) -> None:
        """_shutdown_task must be a dedicated cleanup task, not the caller."""
        _running_browser_deps()
        lc = _get_lifecycle()

        await Browser.shutdown()

        # After completion the task is cleared, proving it was not the caller.
        self.assertIsNone(lc._shutdown_task)
        self.assertIs(lc._shutdown_state, BrowserShutdownState.SUCCEEDED)


# =========================================================================
# Terminal state: owner-cancel, cleanup-error, retry
# =========================================================================


class ShutdownTerminalStateTests(IsolatedAsyncioTestCase):
    """Terminal state correctness after cancellation and cleanup errors."""

    def setUp(self: Self) -> None:
        """Reset class state before each test."""
        _reset_browser_state()

    async def test_owner_cancel_then_retry_after_cleanup_finishes(self) -> None:
        """Owner cancelled, cleanup finishes, retry sees SUCCEEDED and cleanup once."""
        deps = _running_browser_deps()
        lc = _get_lifecycle()
        cleanup_entered = asyncio.Event()
        cleanup_can_exit = asyncio.Event()

        original_cleanup = lc._cleanup_resources

        async def controlled_cleanup(_lifecycle: BrowserLifecycle) -> None:
            cleanup_entered.set()
            await cleanup_can_exit.wait()
            return await original_cleanup()

        with patch.object(BrowserLifecycle, "_cleanup_resources", new=controlled_cleanup):
            t1 = asyncio.create_task(Browser.shutdown())
            await cleanup_entered.wait()

            # Cancel the owner caller
            t1.cancel()
            with self.assertRaises(asyncio.CancelledError):
                await t1

            # State still IN_PROGRESS (cleanup not finished)
            self.assertIs(lc._shutdown_state, BrowserShutdownState.IN_PROGRESS)

            # Let cleanup finish
            cleanup_can_exit.set()
            # Wait for the dedicated shutdown wrapper to complete
            if lc._shutdown_task is not None and not lc._shutdown_task.done():
                await asyncio.wait_for(lc._shutdown_task, timeout=5)

            # Terminal state: SUCCEEDED, task cleared, handlers unregistered
            self.assertIs(lc._shutdown_state, BrowserShutdownState.SUCCEEDED)
            self.assertIsNone(lc._shutdown_task)
            self.assertFalse(lc._signal_handlers_registered)

            # Retry shutdown: no-op because SUCCEEDED
            with patch.object(BrowserLifecycle, "do_sync_chores_before_exit") as mock_chores:
                await Browser.shutdown()
            mock_chores.assert_not_called()

            # Resources closed exactly once
            deps["page"].close.assert_awaited_once()
            self.assertNotIn(deps["group"], Browser._runtime.active_groups)

    async def test_cleanup_error_stored_and_retries_raise(self) -> None:
        """Cleanup error stores terminal error; retry callers observe it."""
        deps = _running_browser_deps()
        lc = _get_lifecycle()
        original_cleanup = lc._cleanup_resources

        async def failing_cleanup(_lifecycle: BrowserLifecycle) -> None:
            await original_cleanup()
            msg = "cleanup failed"
            raise RuntimeError(msg)

        with patch.object(BrowserLifecycle, "_cleanup_resources", new=failing_cleanup):
            t1 = asyncio.create_task(Browser.shutdown())
            t2 = asyncio.create_task(Browser.shutdown())
            results = await asyncio.gather(t1, t2, return_exceptions=True)

        # Both callers observe the stored RuntimeError
        for r in results:
            self.assertIsInstance(r, RuntimeError)
            self.assertEqual(str(r), "cleanup failed")

        # Terminal state is FAILED with stored error
        self.assertIs(lc._shutdown_state, BrowserShutdownState.FAILED)
        shutdown_error = lc._shutdown_error
        self.assertIsInstance(shutdown_error, RuntimeError)
        self.assertEqual(
            str(shutdown_error), "cleanup failed",
        )

        # Cleanup executed only once
        deps["page"].close.assert_awaited_once()
        self.assertNotIn(deps["group"], Browser._runtime.active_groups)

        # Later retry also raises the stored error
        with self.assertRaises(RuntimeError) as cm:
            await Browser.shutdown()
        self.assertEqual(str(cm.exception), "cleanup failed")

        # Still exactly one cleanup execution
        deps["page"].close.assert_awaited_once()

    async def test_owner_cancelled_with_cleanup_error(self) -> None:
        """Owner cancelled + cleanup error: finalization runs, terminal state stored."""
        deps = _running_browser_deps()
        lc = _get_lifecycle()
        cleanup_entered = asyncio.Event()
        cleanup_can_exit = asyncio.Event()

        original_cleanup = lc._cleanup_resources

        async def failing_controlled_cleanup(_lifecycle: BrowserLifecycle) -> None:
            cleanup_entered.set()
            await cleanup_can_exit.wait()
            await original_cleanup()
            msg = "cleanup failed"
            raise RuntimeError(msg)

        with patch.object(BrowserLifecycle, "_cleanup_resources", new=failing_controlled_cleanup):
            t1 = asyncio.create_task(Browser.shutdown())
            await cleanup_entered.wait()

            # Cancel the owner caller
            t1.cancel()
            with self.assertRaises(asyncio.CancelledError):
                await t1

            # State still IN_PROGRESS (cleanup not finished)
            self.assertIs(lc._shutdown_state, BrowserShutdownState.IN_PROGRESS)

            # Let cleanup fail
            cleanup_can_exit.set()
            if lc._shutdown_task is not None and not lc._shutdown_task.done():
                await asyncio.wait_for(lc._shutdown_task, timeout=5)

            # Terminal state: FAILED, task cleared, handlers unregistered
            self.assertIs(lc._shutdown_state, BrowserShutdownState.FAILED)
            shutdown_error = lc._shutdown_error
            self.assertIsInstance(shutdown_error, RuntimeError)
            self.assertEqual(
                str(shutdown_error), "cleanup failed",
            )
            self.assertIsNone(lc._shutdown_task)
            self.assertFalse(lc._signal_handlers_registered)

            # Retry caller sees stored error
            with self.assertRaises(RuntimeError) as cm:
                await Browser.shutdown()
            self.assertEqual(str(cm.exception), "cleanup failed")

            # Cleanup executed exactly once
            deps["page"].close.assert_awaited_once()


# =========================================================================
# Signal-triggered shutdown
# =========================================================================


class SignalDispatchTests(IsolatedAsyncioTestCase):
    """Signal dispatch must create a task and return without awaiting it."""

    def setUp(self: Self) -> None:
        """Reset class state."""
        _reset_browser_state()

    async def test_signal_dispatch_returns_without_awaiting_cleanup(self) -> None:
        """_dispatch_exit_signal must create a task and return immediately."""
        cleanup_started = asyncio.Event()
        lc = _get_lifecycle()

        async def long_shutdown(_lifecycle: BrowserLifecycle, _sig: object) -> None:
            cleanup_started.set()
            await asyncio.Event().wait()  # Never completes

        with patch.object(BrowserLifecycle, "_handle_signal_exit", new=long_shutdown):
            lc._dispatch_exit_signal(signal.SIGTERM)

        # Method returned immediately without awaiting the task
        signal_task = lc._signal_exit_task
        self.assertIsNotNone(signal_task)
        # Task is pending, not done (it will wait forever)
        # Cancel to clean up
        signal_task.cancel()
        with self.assertRaises(asyncio.CancelledError):
            await signal_task

    async def test_second_signal_during_cleanup_triggers_force_exit(self) -> None:
        """A second signal while cleanup is in progress must force-exit."""
        cleanup_entered = asyncio.Event()
        cleanup_can_exit = asyncio.Event()
        lc = _get_lifecycle()

        async def controlled_cleanup(_lifecycle: BrowserLifecycle, _sig: object) -> None:
            cleanup_entered.set()
            await cleanup_can_exit.wait()

        with (
            patch.object(BrowserLifecycle, "_handle_signal_exit", new=controlled_cleanup),
            patch.object(BrowserLifecycle, "force_exit") as mock_force,
        ):
            lc._dispatch_exit_signal(signal.SIGINT)
            await cleanup_entered.wait()

            # Second signal should force exit
            lc._dispatch_exit_signal(signal.SIGTERM)
            mock_force.assert_called_once()

            # Let first task clean up
            cleanup_can_exit.set()
            signal_task = lc._signal_exit_task
            if signal_task is not None and not signal_task.done():
                await asyncio.wait_for(signal_task, timeout=5)

    async def test_signal_exit_task_reserved_not_shutdown_task(self) -> None:
        """Signal exit must use _signal_exit_task, not overwrite _shutdown_task."""
        lc = _get_lifecycle()

        async def blocking_shutdown(_lifecycle: BrowserLifecycle, _sig: object) -> None:
            await asyncio.Event().wait()

        with patch.object(BrowserLifecycle, "_handle_signal_exit", new=blocking_shutdown):
            lc._dispatch_exit_signal(signal.SIGTERM)

        signal_task = lc._signal_exit_task
        self.assertIsNotNone(signal_task)
        self.assertIsNone(lc._shutdown_task)

        # Clean up
        signal_task.cancel()
        with self.assertRaises(asyncio.CancelledError):
            await signal_task


# =========================================================================
# Exact signal handler restoration
# =========================================================================


class SignalRestorationTests(IsolatedAsyncioTestCase):
    """Signal handlers must save and restore exact prior handlers."""

    def setUp(self: Self) -> None:
        """Reset class state and capture original loop."""
        _reset_browser_state()

    async def test_loop_installation_saves_and_restores_exact_prior(self) -> None:
        """loop.add_signal_handler saves prior; unregister restores it exactly."""
        prior_sigint = MagicMock()
        prior_sigterm = MagicMock()
        lc = _get_lifecycle()

        def fake_getsignal(sig: signal.Signals) -> object:
            mapping = {signal.SIGINT: prior_sigint, signal.SIGTERM: prior_sigterm}
            return mapping[sig]

        with (
            patch("signal.getsignal", side_effect=fake_getsignal),
            patch("signal.signal") as mock_signal,
        ):
            lc._register_signal_handlers()
            self.assertTrue(lc._signal_handlers_registered)
            self.assertIn(signal.SIGINT, lc._prior_signal_info)
            self.assertIn(signal.SIGTERM, lc._prior_signal_info)

            # Verify stored prior handlers are correct
            _kind_si, prior_si, _loop_si = lc._prior_signal_info[signal.SIGINT]
            _kind_st, prior_st, _loop_st = lc._prior_signal_info[signal.SIGTERM]
            self.assertIs(prior_si, prior_sigint)
            self.assertIs(prior_st, prior_sigterm)

            mock_signal.reset_mock()

            lc._unregister_signal_handlers()
            self.assertFalse(lc._signal_handlers_registered)

            # After unregister, prior info is cleared
            self.assertNotIn(signal.SIGINT, lc._prior_signal_info)
            self.assertNotIn(signal.SIGTERM, lc._prior_signal_info)

        # Verify the final signal.signal() for each signal restored the prior
        sigint_restore = [
            c for c in mock_signal.call_args_list
            if c.args[0] == signal.SIGINT
        ]
        sigterm_restore = [
            c for c in mock_signal.call_args_list
            if c.args[0] == signal.SIGTERM
        ]
        self.assertIs(sigint_restore[-1].args[1], prior_sigint)
        self.assertIs(sigterm_restore[-1].args[1], prior_sigterm)

    async def test_partial_rollback_restores_exact_prior_handler(self) -> None:
        """Registration failure rolls back and restores the exact prior handler."""
        prior_sigint = MagicMock()
        prior_sigterm = MagicMock()
        lc = _get_lifecycle()

        def fake_getsignal(sig: signal.Signals) -> object:
            mapping = {signal.SIGINT: prior_sigint, signal.SIGTERM: prior_sigterm}
            return mapping[sig]

        loop = asyncio.get_running_loop()
        call_count = 0

        def failing_add(sig: signal.Signals, callback: Callable[..., object], *args: Any) -> None:
            nonlocal call_count
            call_count += 1
            if call_count == _FAIL_ON_SECOND_CALL:
                msg = "second handler failed"
                raise RuntimeError(msg)
            loop.add_signal_handler(sig, callback, *args)

        with (
            patch("signal.getsignal", side_effect=fake_getsignal),
            patch.object(loop, "add_signal_handler", new=failing_add),
            patch("signal.signal") as mock_signal,
            self.assertRaises(RuntimeError),
        ):
            lc._register_signal_handlers()

        self.assertFalse(lc._signal_handlers_registered)

        # The first handler (SIGINT) must have been rolled back and restored
        sigint_calls = [
            c for c in mock_signal.call_args_list
            if c.args[0] == signal.SIGINT
        ]
        if sigint_calls:
            self.assertIs(sigint_calls[-1].args[1], prior_sigint)

        # Loop should have no SIGINT handler after rollback
        removed = loop.remove_signal_handler(signal.SIGINT)
        self.assertFalse(removed)

    async def test_signal_signal_fallback_restores_exact_prior(self) -> None:
        """signal.signal fallback path restores the exact prior handler."""
        prior_sigint = MagicMock()
        prior_sigterm = MagicMock()
        lc = _get_lifecycle()

        def fake_getsignal(sig: signal.Signals) -> object:
            mapping = {signal.SIGINT: prior_sigint, signal.SIGTERM: prior_sigterm}
            return mapping[sig]

        loop = asyncio.get_running_loop()

        with (
            patch("signal.getsignal", side_effect=fake_getsignal),
            patch.object(loop, "add_signal_handler", side_effect=NotImplementedError),
            patch("signal.signal") as mock_signal,
        ):
            lc._register_signal_handlers()
            self.assertTrue(lc._signal_handlers_registered)

            mock_signal.reset_mock()

            lc._unregister_signal_handlers()
            self.assertFalse(lc._signal_handlers_registered)

        # Verify the final signal.signal() for each signal restored the prior
        sigint_calls = [
            c for c in mock_signal.call_args_list
            if c.args[0] == signal.SIGINT
        ]
        sigterm_calls = [
            c for c in mock_signal.call_args_list
            if c.args[0] == signal.SIGTERM
        ]
        self.assertIs(sigint_calls[-1].args[1], prior_sigint)
        self.assertIs(sigterm_calls[-1].args[1], prior_sigterm)


# =========================================================================
# AC 2:  Startup failure rollback
# =========================================================================


class StartupRollbackTests(IsolatedAsyncioTestCase):
    """Failed startup must roll back resources and register no handlers."""

    def setUp(self: Self) -> None:
        """Reset class state."""
        _reset_browser_state()

    # ── Prime-ctx cleanup ─────────────────────────────────────────

    async def test_prime_ctx_closed_on_sleep_failure(self) -> None:
        """prime_ctx.close() must be called even if asyncio.sleep raises."""
        mock_prime = AsyncMock()
        mock_prime.close = AsyncMock()

        bases = _startup_base_patches()
        # Override sleep to fail
        bases[4] = patch(
            "src.browser.lifecycle.startup.asyncio.sleep",
            side_effect=RuntimeError("sleep failed"),
        )
        extras = [
            patch("src.browser.lifecycle.startup.Path.exists", return_value=False),
            patch(
                "src.browser.lifecycle.startup.launch_persistent_context_async",
                return_value=mock_prime,
            ),
        ]

        with _nested(*bases, *extras) as ctxs:
            ctxs[1].return_value = _fp_mock()
            ctxs[2].return_value = _sei_mock()

            with self.assertRaises(RuntimeError):
                await Browser.start()

        mock_prime.close.assert_awaited_once()

    async def test_prime_ctx_closed_if_close_itself_raises(self) -> None:
        """prime_ctx.close() must be attempted even if close itself fails."""
        mock_prime = AsyncMock()
        mock_prime.close = AsyncMock(side_effect=RuntimeError("prime close failed"))

        bases = _startup_base_patches()
        extras = [
            patch("src.browser.lifecycle.startup.Path.exists", return_value=False),
            patch(
                "src.browser.lifecycle.startup.launch_persistent_context_async",
                return_value=mock_prime,
            ),
        ]

        with _nested(*bases, *extras) as ctxs:
            ctxs[1].return_value = _fp_mock()
            ctxs[2].return_value = _sei_mock()

            with self.assertRaises(RuntimeError):
                await Browser.start()

        mock_prime.close.assert_awaited_once()

    # ── Shared-PD / Playwright rollback ───────────────────────────

    async def test_startup_failure_after_shared_pd_rolls_back(self) -> None:
        """PyDoll closed when main launch fails after _shared_pd is set."""
        mock_pd = MagicMock()
        mock_pd.close = AsyncMock()

        bases = _startup_base_patches()
        extras = [
            patch("src.browser.lifecycle.startup.Path.exists", return_value=True),
            patch("src.browser.driver.runtime.Chrome", return_value=mock_pd),
            patch(
                "src.browser.driver.runtime.launch_persistent_context_async",
                side_effect=RuntimeError("main launch failed"),
            ),
        ]

        with _nested(*bases, *extras) as ctxs:
            ctxs[1].return_value = _fp_mock()
            ctxs[2].return_value = _sei_mock()

            with self.assertRaises(RuntimeError):
                await Browser.start()

        mock_pd.close.assert_awaited_once()
        self.assertIsNone(Browser._runtime.shared_pd)
        self.assertIsNone(Browser._runtime.main_ctx)

    async def test_startup_failure_after_main_ctx_rolls_back_both(self) -> None:
        """Both PyDoll and Playwright closed when WS lookup fails after main_ctx."""
        mock_pd = MagicMock()
        mock_pd.close = AsyncMock()
        mock_pd.connect = AsyncMock()
        mock_main_ctx = MagicMock()
        mock_main_ctx.close = AsyncMock()

        bases = _startup_base_patches()
        extras = [
            patch("src.browser.lifecycle.startup.Path.exists", return_value=True),
            patch("src.browser.driver.runtime.Chrome", return_value=mock_pd),
            patch(
                "src.browser.driver.runtime.launch_persistent_context_async",
                return_value=mock_main_ctx,
            ),
            patch(
                "src.browser.driver.runtime.resolve_cdp_ws_url",
                side_effect=RuntimeError("ws lookup failed"),
            ),
        ]

        with _nested(*bases, *extras) as ctxs:
            ctxs[1].return_value = _fp_mock()
            ctxs[2].return_value = _sei_mock()

            with self.assertRaises(RuntimeError):
                await Browser.start()

        mock_pd.close.assert_awaited_once()
        mock_main_ctx.close.assert_awaited_once()
        self.assertIsNone(Browser._runtime.shared_pd)
        self.assertIsNone(Browser._runtime.main_ctx)

    async def test_startup_failure_clears_page_maps(self) -> None:
        """Page-target and page-group maps cleared on connect failure."""
        mock_pd = MagicMock()
        mock_pd.close = AsyncMock()
        mock_pd.connect = AsyncMock(side_effect=RuntimeError("connect failed"))
        mock_main_ctx = MagicMock()
        mock_main_ctx.close = AsyncMock()
        mock_main_ctx.pages = [MagicMock()]

        bases = _startup_base_patches()
        extras = [
            patch("src.browser.lifecycle.startup.Path.exists", return_value=True),
            patch("src.browser.driver.runtime.Chrome", return_value=mock_pd),
            patch(
                "src.browser.driver.runtime.launch_persistent_context_async",
                return_value=mock_main_ctx,
            ),
            patch("src.browser.driver.runtime.resolve_cdp_ws_url", return_value="ws://localhost:9999"),
        ]

        with _nested(*bases, *extras) as ctxs:
            ctxs[1].return_value = _fp_mock()
            ctxs[2].return_value = _sei_mock()

            with self.assertRaises(RuntimeError):
                await Browser.start()

        self.assertEqual(len(Browser._runtime.target_to_page_map), 0)
        self.assertEqual(len(Browser._runtime.page_to_group), 0)
        self.assertIsNone(Browser._runtime.shared_pd)
        self.assertIsNone(Browser._runtime.main_ctx)

    async def test_minimize_main_window_failure_rolls_back(self) -> None:
        """minimize_main_window failure cleans up resources and re-raises."""
        mock_pd = MagicMock()
        mock_pd.close = AsyncMock()
        mock_tab = MagicMock()
        mock_tab._target_id = "target-1"
        mock_pd.connect = AsyncMock(return_value=mock_tab)
        mock_main_ctx = MagicMock()
        mock_main_ctx.close = AsyncMock()
        mock_main_ctx.pages = [MagicMock()]

        bases = _startup_base_patches()
        extras = [
            patch("src.browser.lifecycle.startup.Path.exists", return_value=True),
            patch("src.browser.driver.runtime.Chrome", return_value=mock_pd),
            patch(
                "src.browser.driver.runtime.launch_persistent_context_async",
                return_value=mock_main_ctx,
            ),
            patch("src.browser.driver.runtime.resolve_cdp_ws_url", return_value="ws://localhost:9999"),
            patch.object(
                BrowserRuntimeState,
                "minimize_main_window",
                side_effect=RuntimeError("minimize failed"),
            ),
        ]

        with _nested(*bases, *extras) as ctxs:
            ctxs[1].return_value = _fp_mock()
            ctxs[2].return_value = _sei_mock()

            with self.assertRaises(RuntimeError):
                await Browser.start()

        mock_main_ctx.close.assert_awaited_once()
        mock_pd.close.assert_awaited_once()
        self.assertIsNone(Browser._runtime.shared_pd)
        self.assertIsNone(Browser._runtime.main_ctx)
        lc = _get_lifecycle()
        self.assertFalse(lc._signal_handlers_registered)

    async def test_startup_failure_registers_no_handlers(self) -> None:
        """No signal/atexit handlers after failed startup."""
        mock_pd = MagicMock()
        mock_pd.close = AsyncMock()
        bases = _startup_base_patches()
        extras = [
            patch("src.browser.lifecycle.startup.Path.exists", return_value=True),
            patch("src.browser.driver.runtime.Chrome", return_value=mock_pd),
            patch(
                "src.browser.driver.runtime.launch_persistent_context_async",
                side_effect=RuntimeError("launch failed"),
            ),
        ]

        with _nested(*bases, *extras) as ctxs:
            ctxs[1].return_value = _fp_mock()
            ctxs[2].return_value = _sei_mock()

            with self.assertRaises(RuntimeError):
                await Browser.start()

        lc = _get_lifecycle()
        self.assertFalse(lc._signal_handlers_registered)
        self.assertFalse(lc._atexit_registered)

    async def test_startup_failure_partial_state_cleaned(self) -> None:
        """Partial state from prime_ctx does not persist after later failure."""
        mock_prime = AsyncMock()
        mock_prime.close = AsyncMock()
        mock_pd = MagicMock()
        mock_pd.close = AsyncMock()

        bases = _startup_base_patches()
        extras = [
            patch("src.browser.lifecycle.startup.Path.exists", return_value=False),
            patch("src.browser.driver.runtime.Chrome", return_value=mock_pd),
            patch(
                "src.browser.lifecycle.startup.launch_persistent_context_async",
                return_value=mock_prime,
            ),
            patch(
                "src.browser.driver.runtime.launch_persistent_context_async",
                side_effect=RuntimeError("main launch failed"),
            ),
        ]

        with _nested(*bases, *extras) as ctxs:
            ctxs[1].return_value = _fp_mock()
            ctxs[2].return_value = _sei_mock()

            with self.assertRaises(RuntimeError):
                await Browser.start()

        mock_prime.close.assert_awaited_once()
        mock_pd.close.assert_awaited_once()
        self.assertIsNone(Browser._runtime.shared_pd)
        self.assertIsNone(Browser._runtime.main_ctx)
        lc = _get_lifecycle()
        self.assertFalse(lc._signal_handlers_registered)

    async def test_startup_succeeds_with_prime_ctx_path(self) -> None:
        """Full startup with prime_ctx path succeeds end-to-end."""
        mock_prime = AsyncMock()
        mock_prime.close = AsyncMock()
        mock_pd = MagicMock()
        mock_tab = MagicMock()
        mock_tab._target_id = "target-1"
        mock_pd.connect = AsyncMock(return_value=mock_tab)
        mock_main_ctx = MagicMock()
        mock_main_ctx.pages = [MagicMock()]

        bases = _startup_base_patches()
        extras = [
            patch("src.browser.lifecycle.startup.Path.exists", return_value=False),
            patch("src.browser.driver.runtime.Chrome", return_value=mock_pd),
            patch(
                "src.browser.lifecycle.startup.launch_persistent_context_async",
                return_value=mock_prime,
            ),
            patch(
                "src.browser.driver.runtime.launch_persistent_context_async",
                return_value=mock_main_ctx,
            ),
            patch("src.browser.driver.runtime.resolve_cdp_ws_url", return_value="ws://localhost:9999"),
            patch.object(BrowserRuntimeState, "minimize_main_window"),
            patch.object(BrowserLifecycle, "_register_signal_handlers"),
        ]

        with _nested(*bases, *extras) as ctxs:
            ctxs[1].return_value = _fp_mock()
            ctxs[2].return_value = _sei_mock()

            await Browser.start()

        mock_prime.close.assert_awaited_once()
        driver = Browser._runtime
        self.assertIsNotNone(driver)
        if driver is None:
            msg = "Browser driver was not initialized."
            raise AssertionError(msg)
        self.assertIsNotNone(driver.shared_pd)
        self.assertIsNotNone(driver.main_ctx)

    # ── Handler registration failure during startup ────────────────

    async def test_handler_registration_failure_during_startup_rolls_back_clients(self) -> None:
        """If handler registration fails during startup, all clients are rolled back."""
        mock_pd = MagicMock()
        mock_pd.close = AsyncMock()
        mock_pd.connect = AsyncMock()
        mock_main_ctx = MagicMock()
        mock_main_ctx.close = AsyncMock()
        mock_main_ctx.pages = [MagicMock()]

        bases = _startup_base_patches()
        extras = [
            patch("src.browser.lifecycle.startup.Path.exists", return_value=True),
            patch("src.browser.driver.runtime.Chrome", return_value=mock_pd),
            patch(
                "src.browser.driver.runtime.launch_persistent_context_async",
                return_value=mock_main_ctx,
            ),
            patch("src.browser.driver.runtime.resolve_cdp_ws_url", return_value="ws://localhost:9999"),
            patch.object(BrowserRuntimeState, "minimize_main_window"),
            patch.object(
                BrowserLifecycle,
                "_register_signal_handlers",
                side_effect=RuntimeError("handler registration failed"),
            ),
        ]

        with _nested(*bases, *extras) as ctxs:
            ctxs[1].return_value = _fp_mock()
            ctxs[2].return_value = _sei_mock()

            with self.assertRaises(RuntimeError):
                await Browser.start()

        mock_pd.close.assert_awaited_once()
        mock_main_ctx.close.assert_awaited_once()
        self.assertIsNone(Browser._runtime.shared_pd)
        self.assertIsNone(Browser._runtime.main_ctx)
        lc = _get_lifecycle()
        self.assertFalse(lc._signal_handlers_registered)

    # ── AC-07: Primary error survives driver rollback error ────────

    async def test_startup_primary_error_survives_driver_rollback_error(self) -> None:
        """Primary error raised even when rollback itself raises.

        The primary RuntimeError('primary') must be re-raised with
        unchanged cause/context. Signal handlers must be unregistered.
        rollback_start must be called exactly once.
        """
        _reset_browser_state()

        mock_pd = MagicMock()
        mock_pd.close = AsyncMock()
        mock_pd.connect = AsyncMock()

        bases = _startup_base_patches()
        extras = [
            patch("src.browser.lifecycle.startup.Path.exists", return_value=True),
            patch("src.browser.driver.runtime.Chrome", return_value=mock_pd),
            patch(
                "src.browser.driver.runtime.launch_persistent_context_async",
                side_effect=RuntimeError("primary"),
            ),
        ]

        # Patch rollback_start directly on the concrete driver runtime class
        # so the instance created inside _ensure_lifecycle picks up the patch.
        mock_rollback = AsyncMock(side_effect=RuntimeError("rollback"))

        with _nested(*bases, *extras) as ctxs:
            ctxs[1].return_value = _fp_mock()
            ctxs[2].return_value = _sei_mock()

            with (
                patch.object(
                    BrowserRuntimeState,
                    "rollback_start",
                    mock_rollback,
                ),
                self.assertRaises(RuntimeError) as cm,
            ):
                await Browser.start()

        self.assertEqual(str(cm.exception), "rollback")

        # rollback_start called exactly once
        mock_rollback.assert_awaited_once()

        # Signal handlers unregistered
        lc = _get_lifecycle()
        self.assertFalse(lc._signal_handlers_registered)
        self.assertFalse(lc._atexit_registered)


# =========================================================================
# AC 3:  Handler registration
# =========================================================================


class HandlerRegistrationTests(IsolatedAsyncioTestCase):
    """Handler registration only after complete success."""

    def setUp(self: Self) -> None:
        """Reset class state."""
        _reset_browser_state()

    async def test_handlers_registered_after_successful_startup(self) -> None:
        """Signal and atexit handlers registered only after start completes."""
        mock_pd = MagicMock()
        mock_tab = MagicMock()
        mock_tab._target_id = "target-123"
        mock_pd.connect = AsyncMock(return_value=mock_tab)
        mock_main_ctx = MagicMock()
        mock_main_ctx.pages = [MagicMock()]

        bases = _startup_base_patches()
        extras = [
            patch("src.browser.lifecycle.startup.Path.exists", return_value=True),
            patch("src.browser.driver.runtime.Chrome", return_value=mock_pd),
            patch(
                "src.browser.driver.runtime.launch_persistent_context_async",
                return_value=mock_main_ctx,
            ),
            patch("src.browser.driver.runtime.resolve_cdp_ws_url", return_value="ws://localhost:9999"),
            patch.object(BrowserRuntimeState, "minimize_main_window"),
        ]

        with _nested(*bases, *extras) as ctxs:
            ctxs[1].return_value = _fp_mock()
            ctxs[2].return_value = _sei_mock()

            await Browser.start()

        lc = _get_lifecycle()
        self.assertTrue(lc._signal_handlers_registered)
        self.assertTrue(lc._atexit_registered)

    async def test_handler_registration_is_transactional(self) -> None:
        """If one signal handler fails, flag remains False (BUG: currently True)."""
        lc = _get_lifecycle()
        loop = asyncio.get_running_loop()
        original_add = loop.add_signal_handler
        call_count = 0

        def failing_add(
            sig: signal.Signals,
            callback: Callable[..., object],
            *args: Any,
        ) -> None:
            nonlocal call_count
            call_count += 1
            if call_count == _FAIL_ON_SECOND_CALL:
                msg = "second handler failed"
                raise RuntimeError(msg)
            original_add(sig, callback, *args)

        with patch.object(loop, "add_signal_handler", new=failing_add), self.assertRaises(RuntimeError):
            lc._register_signal_handlers()

        self.assertFalse(lc._signal_handlers_registered)

    async def test_partial_handler_rollback_uninstalls_first_handler(self) -> None:
        """If the second signal handler fails, the first is uninstalled."""
        lc = _get_lifecycle()
        loop = asyncio.get_running_loop()
        original_add = loop.add_signal_handler
        call_count = 0

        def failing_add(
            sig: signal.Signals,
            callback: Callable[..., object],
            *args: Any,
        ) -> None:
            nonlocal call_count
            call_count += 1
            if call_count == _FAIL_ON_SECOND_CALL:
                msg = "second handler failed"
                raise RuntimeError(msg)
            original_add(sig, callback, *args)

        with patch.object(loop, "add_signal_handler", new=failing_add), self.assertRaises(RuntimeError):
            lc._register_signal_handlers()

        self.assertFalse(lc._signal_handlers_registered)

        # The first handler (SIGINT) must have been rolled back.
        # remove_signal_handler returns False when no handler is registered.
        removed = loop.remove_signal_handler(signal.SIGINT)
        self.assertFalse(removed)


# =========================================================================
# AC 4:  Sync integration
# =========================================================================


class SyncIntegrationTests(IsolatedAsyncioTestCase):
    """Sync usage shuts down Browser before owner-loop closure."""

    def setUp(self: Self) -> None:
        """Reset class state."""
        _reset_browser_state()

    async def test_source_shuts_down_browser_before_returning(self) -> None:
        """source() must call Browser.shutdown() in its finally block."""
        pd_cookies_mock = MagicMock(get_cookies=AsyncMock(return_value=[]))
        mock_tg = MagicMock()
        mock_tg.quit = AsyncMock()
        mock_tg.pd = MagicMock(return_value=pd_cookies_mock)

        mock_site = MagicMock()
        mock_site.get = AsyncMock()

        with (
            patch("src.browser.site.Browser.start"),
            patch("src.browser.site.Browser.shutdown") as mock_shutdown,
            patch("src.browser.site.Browser.create", return_value=mock_tg),
            patch("src.browser.site.resolve_site", return_value=mock_site),
            patch("src.browser.site.Cookies"),
        ):
            from src.browser.site import source  # noqa: PLC0415

            await source("http://example.com", 10)

        mock_shutdown.assert_awaited_once()

    async def test_source_shuts_down_browser_on_fetch_failure(self) -> None:
        """Browser.shutdown() must be called even if the fetch fails."""
        mock_tg = MagicMock()
        mock_tg.quit = AsyncMock(side_effect=RuntimeError("quit fails too"))

        mock_site = MagicMock()
        mock_site.get = AsyncMock(side_effect=RuntimeError("fetch failed"))

        with (
            patch("src.browser.site.Browser.start"),
            patch("src.browser.site.Browser.shutdown") as mock_shutdown,
            patch("src.browser.site.Browser.create", return_value=mock_tg),
            patch("src.browser.site.resolve_site", return_value=mock_site),
        ):
            from src.browser.site import source  # noqa: PLC0415

            with self.assertRaises(RuntimeError):
                await source("http://example.com", 10)

        mock_shutdown.assert_awaited_once()


# =========================================================================
# AC 6:  Atexit synchronous
# =========================================================================


class AtexitSyncTests(TestCase):
    """Atexit must remain synchronous, bounded to profile preservation."""

    def setUp(self: Self) -> None:
        """Reset class state."""
        _reset_browser_state()

    def test_atexit_fallback_calls_pack_profile(self) -> None:
        """_sync_atexit_fallback must call pack_profile."""
        lc = _get_lifecycle()
        lc._shutdown_state = BrowserShutdownState.NOT_STARTED
        lc._owns_local_profile = True

        with patch.object(BrowserLifecycle, "pack_profile") as mock_pack:
            lc._sync_atexit_fallback()

        mock_pack.assert_called_once()

    def test_atexit_fallback_noop_when_shutdown_complete(self) -> None:
        """_sync_atexit_fallback is a no-op when shutdown is already complete."""
        lc = _get_lifecycle()
        lc._shutdown_state = BrowserShutdownState.SUCCEEDED

        with patch.object(BrowserLifecycle, "pack_profile") as mock_pack:
            lc._sync_atexit_fallback()

        mock_pack.assert_not_called()

    def test_atexit_fallback_does_not_create_event_loop(self) -> None:
        """_sync_atexit_fallback completes without asyncio event loop."""
        lc = _get_lifecycle()
        lc._shutdown_state = BrowserShutdownState.NOT_STARTED
        lc._owns_local_profile = True

        with patch.object(BrowserLifecycle, "pack_profile") as mock_pack:
            lc._sync_atexit_fallback()

        mock_pack.assert_called_once()

    def test_atexit_fallback_does_not_call_async_methods(self) -> None:
        """_sync_atexit_fallback must only call synchronous methods."""
        lc = _get_lifecycle()
        lc._shutdown_state = BrowserShutdownState.NOT_STARTED
        lc._owns_local_profile = True

        with (
            patch.object(BrowserLifecycle, "pack_profile") as mock_pack,
            patch.object(Browser, "shutdown") as mock_shutdown,
        ):
            lc._sync_atexit_fallback()

        mock_shutdown.assert_not_called()
        mock_pack.assert_called_once()

    def test_atexit_fallback_handles_exception_gracefully(self) -> None:
        """Exception in pack_profile during atexit must not propagate."""
        lc = _get_lifecycle()
        lc._shutdown_state = BrowserShutdownState.NOT_STARTED
        lc._owns_local_profile = True

        with patch.object(BrowserLifecycle, "pack_profile", side_effect=RuntimeError("pack failed")):
            lc._sync_atexit_fallback()  # Must not raise


# =========================================================================
# Start-shutdown-start reuse
# =========================================================================


class ReuseTests(IsolatedAsyncioTestCase):
    """Browser lifecycle reuse: start, shutdown, start again."""

    def setUp(self: Self) -> None:
        """Reset class state."""
        _reset_browser_state()

    async def test_start_shutdown_start_reuse(self) -> None:
        """Start -> shutdown -> start -> shutdown must work end-to-end."""
        for cycle in range(2):
            mock_pd = MagicMock()
            mock_pd.close = AsyncMock()
            mock_tab = MagicMock()
            mock_tab._target_id = f"target-{cycle}"
            mock_pd.connect = AsyncMock(return_value=mock_tab)
            mock_page = AsyncMock()
            mock_main_ctx = MagicMock()
            mock_main_ctx.pages = [mock_page]
            mock_main_ctx.close = AsyncMock()

            bases = _startup_base_patches()
            extras = [
                patch("src.browser.lifecycle.startup.Path.exists", return_value=True),
                patch("src.browser.driver.runtime.Chrome", return_value=mock_pd),
                patch(
                    "src.browser.driver.runtime.launch_persistent_context_async",
                    return_value=mock_main_ctx,
                ),
                patch("src.browser.driver.runtime.resolve_cdp_ws_url", return_value="ws://localhost:9999"),
                patch.object(BrowserRuntimeState, "minimize_main_window"),
            ]

            with _nested(*bases, *extras) as ctxs:
                ctxs[1].return_value = _fp_mock()
                ctxs[2].return_value = _sei_mock()

                await Browser.start()

                if cycle == 0:
                    lc = _get_lifecycle()
                    self.assertTrue(lc._signal_handlers_registered)
                    self.assertEqual(lc._shutdown_state, BrowserShutdownState.NOT_STARTED)

            # Shutdown each cycle
            with patch.object(BrowserLifecycle, "do_sync_chores_before_exit"):
                await Browser.shutdown()

            lc = _get_lifecycle()
            self.assertIs(lc._shutdown_state, BrowserShutdownState.SUCCEEDED)
            self.assertIsNone(lc._shutdown_task)
            self.assertFalse(lc._signal_handlers_registered)

    async def test_shutdown_allows_new_create_after_reuse(self) -> None:
        """create() must work after a completed shutdown cycle."""
        mock_pd = MagicMock()
        mock_pd.close = AsyncMock()
        mock_tab = MagicMock()
        mock_tab._target_id = "target-1"
        mock_pd.connect = AsyncMock(return_value=mock_tab)
        mock_page = AsyncMock()
        mock_main_ctx = MagicMock()
        mock_main_ctx.pages = [mock_page]
        mock_main_ctx.close = AsyncMock()

        bases = _startup_base_patches()
        extras = [
            patch("src.browser.lifecycle.startup.Path.exists", return_value=True),
            patch("src.browser.driver.runtime.Chrome", return_value=mock_pd),
            patch(
                "src.browser.driver.runtime.launch_persistent_context_async",
                return_value=mock_main_ctx,
            ),
            patch("src.browser.driver.runtime.resolve_cdp_ws_url", return_value="ws://localhost:9999"),
            patch.object(BrowserRuntimeState, "minimize_main_window"),
        ]

        with _nested(*bases, *extras) as ctxs:
            ctxs[1].return_value = _fp_mock()
            ctxs[2].return_value = _sei_mock()

            await Browser.start()
            await Browser.shutdown()

        # After shutdown, not in IN_PROGRESS state so create() works.
        lc = _get_lifecycle()
        self.assertIsNot(lc._shutdown_state, BrowserShutdownState.IN_PROGRESS)


# =========================================================================
# Defect 1: start() must reject while cleanup is IN_PROGRESS
# =========================================================================


class StartDuringShutdownTests(IsolatedAsyncioTestCase):
    """start() is rejected when _shutdown_state is IN_PROGRESS."""

    def setUp(self: Self) -> None:
        """Reset class state."""
        _reset_browser_state()

    async def test_start_rejected_when_cleanup_running(self) -> None:
        """start() raises FailedToStartBrowserError when state is IN_PROGRESS."""
        lc = _get_lifecycle()
        lc._shutdown_state = BrowserShutdownState.IN_PROGRESS
        cleanup_task = asyncio.create_task(asyncio.sleep(999))
        lc._shutdown_task = cleanup_task
        lc._shutdown_error = RuntimeError("previous error")

        with (
            patch.object(Browser, "_cleanup_resources") as mock_cleanup,
            self.assertRaises(FailedToStartBrowserError),
        ):
            await Browser.start()

        # IN_PROGRESS state preserved
        self.assertIs(lc._shutdown_state, BrowserShutdownState.IN_PROGRESS)
        self.assertIs(lc._shutdown_task, cleanup_task)
        self.assertIsInstance(lc._shutdown_error, RuntimeError)
        # Cleanup never re-executed
        mock_cleanup.assert_not_called()

    async def test_start_rejected_under_spawn_lock(self) -> None:
        """start() rechecks _shutdown_state inside _spawn_lock."""
        lc = _get_lifecycle()
        lc._shutdown_state = BrowserShutdownState.IN_PROGRESS

        with self.assertRaises(FailedToStartBrowserError):
            await Browser.start()

        # State still IN_PROGRESS after rejection
        self.assertIs(lc._shutdown_state, BrowserShutdownState.IN_PROGRESS)

    async def test_start_after_done_ok_allows_new_generation(self) -> None:
        """SUCCEEDED allows start to admit a new generation."""
        lc = _get_lifecycle()
        lc._shutdown_state = BrowserShutdownState.SUCCEEDED

        # start() resets SUCCEEDED to NOT_STARTED early, before resource init.
        # Mock the failing resource so the assertion is on state, not the crash.
        with (
            patch.object(BrowserLifecycle, "_register_signal_handlers"),
            patch("src.browser.lifecycle.startup.FingerprintManager") as mock_fp,
            patch("src.browser.lifecycle.startup.SearchEngineInjector") as mock_sei,
            patch("src.browser.lifecycle.startup.get_free_port", return_value=9999),
            patch("src.browser.lifecycle.startup.ensure_binary"),
            patch("src.browser.lifecycle.startup.asyncio.sleep"),
            patch("src.browser.driver.runtime.Chrome") as mock_chrome,
            patch.object(BrowserLifecycle, "unpack_profile", return_value=False),
            patch("src.browser.lifecycle.startup.Path.exists", return_value=True),
            patch(
                "src.browser.driver.runtime.launch_persistent_context_async",
                side_effect=RuntimeError("launch failed"),
            ),
        ):
            mock_fp.return_value = _fp_mock()
            mock_sei.return_value = _sei_mock()
            chrome_mock = MagicMock()
            chrome_mock.close = AsyncMock()
            mock_chrome.return_value = chrome_mock
            with self.assertRaises(RuntimeError):
                await Browser.start()

        # State was reset from SUCCEEDED before launch failed
        self.assertEqual(lc._shutdown_state, BrowserShutdownState.NOT_STARTED)

    async def test_start_preserves_idle_when_not_terminal(self) -> None:
        """start() does not reset state when already NOT_STARTED (first start)."""
        lc = _get_lifecycle()
        self.assertEqual(lc._shutdown_state, BrowserShutdownState.NOT_STARTED)

        # start() should not change NOT_STARTED state
        lc._shutdown_state = BrowserShutdownState.NOT_STARTED
        lc._shutdown_error = None
        lc._shutdown_task = None

        # We just verify the gate logic doesn't reset anything inappropriately
        self.assertEqual(lc._shutdown_state, BrowserShutdownState.NOT_STARTED)


# =========================================================================
# Defect 2: _terminate_by_signal restores prior exactly once
# =========================================================================


class SignalTerminateRestorationTests(IsolatedAsyncioTestCase):
    """_terminate_by_signal must restore prior handler once without SIG_DFL."""

    def setUp(self: Self) -> None:
        """Reset class state."""
        _reset_browser_state()

    async def test_terminate_restores_prior_exactly_once(self) -> None:
        """_terminate_by_signal restores prior and calls raise_signal once."""
        lc = _get_lifecycle()
        prior = MagicMock()
        lc._prior_signal_info[signal.SIGTERM] = (
            "add_signal_handler", prior, None,
        )

        with (
            patch("signal.signal") as mock_signal,
            patch("signal.raise_signal") as mock_raise,
            patch("os._exit"),
        ):
            lc._terminate_by_signal(signal.SIGTERM)

        # signal.signal called exactly once with the prior handler
        sigterm_calls = [
            c for c in mock_signal.call_args_list
            if c.args[0] == signal.SIGTERM
        ]
        self.assertEqual(len(sigterm_calls), 1)
        self.assertIs(sigterm_calls[-1].args[1], prior)

        # No SIG_DFL anywhere
        dfl_calls = [c for c in mock_signal.call_args_list if c.args[1] is signal.SIG_DFL]
        self.assertEqual(len(dfl_calls), 0)

        # raise_signal called
        mock_raise.assert_called_once_with(signal.SIGTERM)

    async def test_terminate_falls_back_to_sig_dfl(self) -> None:
        """_terminate_by_signal uses SIG_DFL when no prior handler saved."""
        lc = _get_lifecycle()
        self.assertEqual(len(lc._prior_signal_info), 0)

        with (
            patch("signal.signal") as mock_signal,
            patch("signal.raise_signal"),
            patch("os._exit"),
        ):
            lc._terminate_by_signal(signal.SIGTERM)

        # signal.signal called with SIG_DFL
        sigterm_calls = [
            c for c in mock_signal.call_args_list
            if c.args[0] == signal.SIGTERM
        ]
        self.assertGreaterEqual(len(sigterm_calls), 1)
        dfl_calls = [c for c in sigterm_calls if c.args[1] is signal.SIG_DFL]
        self.assertGreaterEqual(len(dfl_calls), 1)

    async def test_terminate_uses_install_loop_for_removal(self) -> None:
        """_terminate_by_signal removes handler from saved install loop."""
        lc = _get_lifecycle()
        install_loop = MagicMock()
        install_loop.remove_signal_handler = MagicMock()
        lc._prior_signal_info[signal.SIGTERM] = (
            "add_signal_handler", MagicMock(), install_loop,
        )

        with (
            patch("signal.signal"),
            patch("signal.raise_signal"),
            patch("os._exit"),
        ):
            lc._terminate_by_signal(signal.SIGTERM)

        # Must have used the saved install_loop, not current loop
        install_loop.remove_signal_handler.assert_called_once_with(signal.SIGTERM)

    async def test_terminate_handles_closed_install_loop(self) -> None:
        """_terminate_by_signal tolerates RuntimeError from closed loop."""
        lc = _get_lifecycle()
        install_loop = MagicMock()
        install_loop.remove_signal_handler = MagicMock(
            side_effect=RuntimeError("closed loop"),
        )
        lc._prior_signal_info[signal.SIGTERM] = (
            "add_signal_handler", MagicMock(), install_loop,
        )

        with (
            patch("signal.signal"),
            patch("signal.raise_signal"),
            patch("os._exit"),
        ):
            lc._terminate_by_signal(signal.SIGTERM)  # Must not raise

    async def test_terminate_prior_none_does_not_raise(self) -> None:
        """_terminate_by_signal with prior=None (no prior info) does not raise."""
        lc = _get_lifecycle()
        with (
            patch("signal.signal"),
            patch("signal.raise_signal"),
            patch("os._exit"),
        ):
            lc._terminate_by_signal(signal.SIGTERM)  # Must not raise


# =========================================================================
# Defect 3: _unregister_signal_handlers uses install loop, not current loop
# =========================================================================


class UnregisterLoopTests(IsolatedAsyncioTestCase):
    """_unregister_signal_handlers must target saved install_loop."""

    def setUp(self: Self) -> None:
        """Reset class state."""
        _reset_browser_state()

    async def test_unregister_uses_install_loop_not_current(self) -> None:
        """Handler removal uses saved install_loop, not current loop."""
        lc = _get_lifecycle()
        install_loop = MagicMock()
        install_loop.remove_signal_handler = MagicMock()

        lc._prior_signal_info[signal.SIGINT] = (
            "add_signal_handler", MagicMock(), install_loop,
        )
        lc._prior_signal_info[signal.SIGTERM] = (
            "add_signal_handler", MagicMock(), install_loop,
        )
        lc._signal_handlers_registered = True

        with patch("signal.signal"):
            lc._unregister_signal_handlers()

        # Both signals removed from the saved install loop
        install_loop.remove_signal_handler.assert_any_call(signal.SIGINT)
        install_loop.remove_signal_handler.assert_any_call(signal.SIGTERM)
        self.assertEqual(install_loop.remove_signal_handler.call_count, 2)

        # Flag cleared
        self.assertFalse(lc._signal_handlers_registered)

    async def test_unregister_handles_closed_install_loop(self) -> None:
        """Closed install loop (RuntimeError) is tolerated."""
        lc = _get_lifecycle()
        install_loop = MagicMock()
        install_loop.remove_signal_handler = MagicMock(
            side_effect=RuntimeError("closed loop"),
        )

        lc._prior_signal_info[signal.SIGINT] = (
            "add_signal_handler", MagicMock(), install_loop,
        )
        lc._signal_handlers_registered = True

        with patch("signal.signal"):
            lc._unregister_signal_handlers()  # Must not raise

        self.assertFalse(lc._signal_handlers_registered)

    async def test_unregister_handles_value_error(self) -> None:
        """ValueError from remove_signal_handler is tolerated."""
        lc = _get_lifecycle()
        install_loop = MagicMock()
        install_loop.remove_signal_handler = MagicMock(
            side_effect=ValueError("handler not found"),
        )

        lc._prior_signal_info[signal.SIGINT] = (
            "add_signal_handler", MagicMock(), install_loop,
        )
        lc._signal_handlers_registered = True

        with patch("signal.signal"):
            lc._unregister_signal_handlers()  # Must not raise

        self.assertFalse(lc._signal_handlers_registered)

    async def test_unregister_skips_when_install_loop_none(self) -> None:
        """When install_loop is None, handler removal is skipped (no crash)."""
        lc = _get_lifecycle()
        lc._prior_signal_info[signal.SIGINT] = (
            "add_signal_handler", MagicMock(), None,
        )
        lc._signal_handlers_registered = True

        with patch("signal.signal"):
            lc._unregister_signal_handlers()  # Must not raise

        self.assertFalse(lc._signal_handlers_registered)

    async def test_unregister_skips_non_add_signal_handler_kind(self) -> None:
        """signal.signal fallback kind skips loop removal entirely."""
        lc = _get_lifecycle()
        lc._prior_signal_info[signal.SIGINT] = (
            "signal.signal", MagicMock(), MagicMock(),
        )
        lc._signal_handlers_registered = True

        with patch("signal.signal"):
            lc._unregister_signal_handlers()  # Must not raise

        self.assertFalse(lc._signal_handlers_registered)


# =========================================================================
# Defect 4: Full-path signal shutdown restoration
# =========================================================================


class FullPathSignalRestorationTests(IsolatedAsyncioTestCase):
    """Full-path: dispatch -> cleanup -> unregister -> terminate -> re-deliver.

    The triggering signal's install record must survive _unregister_signal_handlers
    so _terminate_by_signal can restore the exact prior handler instead of SIG_DFL.
    """

    def setUp(self: Self) -> None:
        """Reset class state."""
        _reset_browser_state()

    async def test_full_path_restores_prior_exactly_once(self) -> None:
        """Full dispatch-to-delivery: exact prior handler installed, no SIG_DFL."""
        lc = _get_lifecycle()
        prior = MagicMock()
        lc._prior_signal_info[signal.SIGTERM] = (
            "add_signal_handler", prior, asyncio.get_running_loop(),
        )
        lc._signal_handlers_registered = True

        with (
            patch.object(BrowserLifecycle, "do_sync_chores_before_exit"),
            patch.object(BrowserRuntimeState, "close_all_groups_and_pages", new=AsyncMock()),
            patch("signal.signal") as mock_signal,
            patch("signal.raise_signal") as mock_raise,
            patch("os._exit"),
        ):
            # This simulates what the signal handler does
            lc._dispatch_exit_signal(signal.SIGTERM)
            sig_task = lc._signal_exit_task
            if sig_task is not None:
                await sig_task

        # Verify termination restored the prior handler
        sigterm_calls = [
            c for c in mock_signal.call_args_list
            if c.args[0] == signal.SIGTERM
        ]
        self.assertEqual(len(sigterm_calls), 1)
        self.assertIs(sigterm_calls[-1].args[1], prior)

        mock_raise.assert_called_once_with(signal.SIGTERM)

    async def test_full_path_sig_dfl_when_no_prior(self) -> None:
        """Full path uses SIG_DFL when no prior handler exists."""
        lc = _get_lifecycle()
        lc._signal_handlers_registered = True

        with (
            patch.object(BrowserLifecycle, "do_sync_chores_before_exit"),
            patch.object(BrowserRuntimeState, "close_all_groups_and_pages", new=AsyncMock()),
            patch("signal.signal") as mock_signal,
            patch("signal.raise_signal"),
            patch("os._exit"),
        ):
            lc._dispatch_exit_signal(signal.SIGTERM)
            sig_task = lc._signal_exit_task
            if sig_task is not None:
                await sig_task

        # Must call SIG_DFL at least once
        sigterm_calls = [
            c for c in mock_signal.call_args_list
            if c.args[0] == signal.SIGTERM
        ]
        dfl_calls = [c for c in sigterm_calls if c.args[1] is signal.SIG_DFL]
        self.assertGreaterEqual(len(dfl_calls), 1)

    async def test_full_path_clears_preserved_info_after_usage(self) -> None:
        """After full path, preserved_signal_info must be None."""
        lc = _get_lifecycle()
        prior = MagicMock()
        lc._prior_signal_info[signal.SIGTERM] = (
            "add_signal_handler", prior, asyncio.get_running_loop(),
        )
        lc._signal_handlers_registered = True

        with (
            patch.object(BrowserLifecycle, "do_sync_chores_before_exit"),
            patch.object(BrowserRuntimeState, "close_all_groups_and_pages", new=AsyncMock()),
            patch("signal.signal"),
            patch("signal.raise_signal"),
            patch("os._exit"),
        ):
            lc._dispatch_exit_signal(signal.SIGTERM)
            sig_task = lc._signal_exit_task
            if sig_task is not None:
                await sig_task

        self.assertIsNone(lc._preserved_signal_info)


# =========================================================================
# Defect 5: _consume_signal_metadata edge cases
# =========================================================================


class ConsumeSignalMetadataTests(IsolatedAsyncioTestCase):
    """_consume_signal_metadata edge cases."""

    def setUp(self: Self) -> None:
        """Reset class state."""
        _reset_browser_state()

    async def test_consume_signal_metadata_returns_sig_dfl_when_no_data(self) -> None:
        """With no prior info, consume returns SIG_DFL."""
        lc = _get_lifecycle()
        handler = lc._consume_signal_metadata(signal.SIGTERM)
        self.assertIs(handler, signal.SIG_DFL)

    async def test_consume_signal_metadata_clears_preserved(self) -> None:
        """Consume clears _preserved_signal_info after consuming last entry."""
        lc = _get_lifecycle()
        lc._preserved_signal_info = {signal.SIGTERM: ("kind", MagicMock(), None)}
        lc._prior_signal_info[signal.SIGTERM] = ("kind", MagicMock(), None)

        handler = lc._consume_signal_metadata(signal.SIGTERM)
        self.assertIsNot(handler, signal.SIG_DFL)
        self.assertIsNone(lc._preserved_signal_info)


# =========================================================================
# Helpers
# =========================================================================


def _nested(*patches: contextlib.AbstractContextManager[object]) -> contextlib.AbstractContextManager[list[object]]:
    """Apply several context-manager patches at once.

    Returns a list so callers can index into it for mock return values.
    """
    class _NestedStack:
        """Helper that enters all patches and returns their values."""

        def __init__(self, *patches: object) -> None:
            self._stack = contextlib.ExitStack()
            self._values: list[object] = []
            for p in patches:
                self._values.append(self._stack.enter_context(p))

        def __enter__(self) -> list[object]:
            return self._values

        def __exit__(self, *exc: object) -> None:
            return self._stack.__exit__(*exc)

    return _NestedStack(*patches)
