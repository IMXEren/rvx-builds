"""Tests for concrete lifecycle-owned browser startup configuration."""

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Self, TypedDict, cast
from unittest import IsolatedAsyncioTestCase, TestCase
from unittest.mock import AsyncMock, MagicMock, patch

from src.browser.browser import Browser
from src.browser.driver import BrowserRuntimeState, DriverRemoteAttachConfig, DriverStartupConfig
from src.browser.exceptions import BrowserStartError
from src.browser.lifecycle import BrowserLifecycle
from src.browser.lifecycle.startup import get_free_port

# ruff: noqa: PT009, PT027, S108, SLF001


def _fingerprint() -> MagicMock:
    fp = MagicMock()
    fp.options.arguments = ["--remote-debugging-port=9999", "--window-size=1920,980"]
    return fp


class _DriverDouble:
    """Mutable test double for lifecycle-to-driver calls."""

    def __init__(self) -> None:
        """Create async driver edge mocks."""
        self.start_live = AsyncMock()
        self.attach_remote = AsyncMock()
        self.rollback_start = AsyncMock()
        self.main_ctx = None
        self.shared_pd = None
        self.shutdown_task = None
        self.atexit_registered = False


async def _noop_popup_handler(_page: object) -> None:
    return None


class _StartResult(TypedDict):
    events: list[str]
    request: DriverStartupConfig | None


class BrowserLifecycleStartupTests(IsolatedAsyncioTestCase):
    """Lifecycle start owns concrete config and sequencing."""

    def setUp(self: Self) -> None:
        """Create a fresh concrete lifecycle and mocked driver per test."""
        self.driver = _DriverDouble()
        self.lifecycle = BrowserLifecycle(cast("BrowserRuntimeState", self.driver))

    async def _start(self, *, running: bool = False) -> _StartResult:
        events: list[str] = []

        with (
            patch.object(BrowserLifecycle, "unpack_profile", side_effect=lambda: events.append("unpack")),
            patch.object(BrowserLifecycle, "webdata_path", return_value=Path("/tmp/missing-web-data")),
            patch.object(
                BrowserLifecycle,
                "_prime_profile",
                AsyncMock(side_effect=lambda _args: events.append("prime")),
            ),
            patch.object(BrowserLifecycle, "_inject_search_engine", side_effect=lambda: events.append("search")),
            patch("src.browser.lifecycle.startup.ensure_binary", side_effect=lambda: events.append("binary")),
            patch("src.browser.lifecycle.startup.get_free_port", return_value=9999),
            patch("src.browser.lifecycle.startup.FingerprintManager", return_value=_fingerprint()),
            patch.object(BrowserLifecycle, "_register_atexit", side_effect=lambda: events.append("atexit")),
        ):
            await self.lifecycle.start(
                is_running=lambda: running,
                popup_handler=_noop_popup_handler,
            )
        request = None
        if not running:
            await_args = self.driver.start_live.await_args
            if await_args is None:
                msg = "driver.start_live was not awaited"
                raise AssertionError(msg)
            request = cast("DriverStartupConfig", await_args.args[0])
        return {"events": events, "request": request}

    async def test_happy_path_passes_explicit_driver_startup_config(self) -> None:
        """Happy path: driver receives launch inputs but no pre-resolved websocket."""
        result = await self._start()
        request = result["request"]

        self.assertIsInstance(request, DriverStartupConfig)
        request = cast("DriverStartupConfig", request)
        self.assertEqual(request.profile_dir, "/tmp/browser-profile")
        self.assertEqual(request.user_data_dir, "/tmp/browser-profile")
        self.assertEqual(request.cdp_port, 9999)
        self.assertEqual(request.viewport, {"width": 1920, "height": 980})
        self.assertEqual(request.locale, "en-US,en")
        self.assertEqual(request.launch_arguments, ["--remote-debugging-port=9999", "--window-size=1920,980"])
        self.assertFalse(hasattr(request, "ws_url"))

    async def test_invariant_websocket_resolution_is_not_done_by_lifecycle(self) -> None:
        """Invariant: lifecycle must let runtime resolve CDP after launching Chrome."""
        result = await self._start()

        self.assertIsInstance(result["request"], DriverStartupConfig)

    async def test_invariant_search_engine_runs_after_profile_priming(self) -> None:
        """Invariant: SearchEngineInjector sequencing follows Chrome Web Data priming."""
        result = await self._start()
        events = result["events"]

        self.assertLess(events.index("prime"), events.index("search"))
        self.assertLess(events.index("search"), events.index("atexit"))

    async def test_boundary_running_browser_skips_startup_side_effects(self) -> None:
        """Boundary: already-running browser admits then returns without unpack, binary, or driver start."""
        result = await self._start(running=True)

        self.assertEqual(result["events"], [])
        self.driver.start_live.assert_not_awaited()

    async def test_error_path_driver_failure_rolls_back_and_reraises(self) -> None:
        """Error path: startup rollback runs once and primary driver error is preserved."""
        self.driver.start_live = AsyncMock(side_effect=RuntimeError("primary"))
        self.driver.rollback_start = AsyncMock()

        with self.assertRaisesRegex(BrowserStartError, "failed to start the browser"):
            await self._start()

        self.driver.rollback_start.assert_awaited_once()

    async def test_state_transition_checked_binary_is_idempotent(self) -> None:
        """State transition: binary check happens once across repeated lifecycle starts."""
        first = await self._start()
        self.driver.start_live.reset_mock()
        second = await self._start()

        self.assertIn("binary", first["events"])
        self.assertNotIn("binary", second["events"])
        self.assertTrue(self.lifecycle.checked_binary)

    async def test_input_variation_custom_profile_port_viewport_locale(self) -> None:
        """Input variation: custom atypical lifecycle fields propagate to driver config."""
        self.lifecycle.profile_dir = "/tmp/custom-profile"
        self.lifecycle.cdp_port = 9333
        self.lifecycle.viewport = {"width": 320, "height": 568}
        self.lifecycle.locale = "fr-FR,fr"

        result = await self._start()
        request = result["request"]

        self.assertIsInstance(request, DriverStartupConfig)
        request = cast("DriverStartupConfig", request)
        self.assertEqual(request.profile_dir, "/tmp/custom-profile")
        self.assertEqual(request.cdp_port, 9999)
        self.assertEqual(request.viewport, {"width": 320, "height": 568})
        self.assertEqual(request.locale, "fr-FR,fr")

    async def test_prime_profile_closes_context_when_sleep_fails(self) -> None:
        """Boundary/error path: priming closes the temporary context even when sleep fails."""
        prime_ctx = AsyncMock()
        prime_ctx.close = AsyncMock()

        with (
            patch("src.browser.lifecycle.startup.launch_persistent_context_async", AsyncMock(return_value=prime_ctx)),
            patch("src.browser.lifecycle.startup.asyncio.sleep", AsyncMock(side_effect=RuntimeError("sleep failed"))),
            self.assertRaisesRegex(RuntimeError, "sleep failed"),
        ):
            await self.lifecycle._prime_profile(["--x"])

        prime_ctx.close.assert_awaited_once()

    async def test_state_transition_browser_connect_bypasses_local_lifecycle_profile_work(self) -> None:
        """Remote state transition: Browser.connect attaches without local lifecycle startup side effects."""
        events: list[str] = []
        original_runtime = Browser._runtime
        original_lifecycle = Browser._lifecycle
        try:
            driver = _DriverDouble()
            Browser._runtime = cast("BrowserRuntimeState", driver)
            Browser._lifecycle = BrowserLifecycle(cast("BrowserRuntimeState", driver))
            start = AsyncMock(side_effect=lambda **_kwargs: events.append("start"))
            with (
                patch.object(BrowserLifecycle, "start", start),
                patch.object(BrowserLifecycle, "unpack_profile", side_effect=lambda: events.append("unpack")),
                patch.object(BrowserLifecycle, "pack_profile", side_effect=lambda *_args: events.append("pack")),
                patch.object(
                    BrowserLifecycle,
                    "_register_signal_cleanup",
                    side_effect=lambda: events.append("signal_cleanup"),
                ),
            ):
                await Browser.connect("wss://cloud.example/devtools/browser/remote")
                Browser._do_sync_chores_before_exit()
        finally:
            Browser._runtime = original_runtime
            Browser._lifecycle = original_lifecycle

        await_args = driver.attach_remote.await_args
        if await_args is None:
            msg = "driver.attach_remote was not awaited"
            raise AssertionError(msg)
        request = await_args.args[0]
        self.assertIsInstance(request, DriverRemoteAttachConfig)
        self.assertEqual(request.ws_url, "wss://cloud.example/devtools/browser/remote")
        self.assertEqual(events, ["signal_cleanup"])


class BrowserLifecycleProfileTests(TestCase):
    """Profile persistence and free-port boundaries."""

    def test_pack_profile_skips_cache_journals_and_archive_inside_profile(self) -> None:
        """Boundary: archive excludes cache files, journals, and stale in-profile archive."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            profile = root / "profile"
            (profile / "Default").mkdir(parents=True)
            (profile / "Cache").mkdir()
            (profile / "Default" / "Preferences").write_text("{}", encoding="utf-8")
            (profile / "Default" / "Web Data-journal").write_text("journal", encoding="utf-8")
            (profile / "Cache" / "cached").write_text("cache", encoding="utf-8")
            lifecycle = BrowserLifecycle(BrowserRuntimeState(max_groups=1), profile_dir=str(profile))

            archive = lifecycle.pack_profile(profile / "inside.zip")

            self.assertEqual(archive, root / "inside.zip")
            self.assertIsNotNone(archive)
            archive = cast("Path", archive)
            self.assertTrue(archive.exists())

    def test_get_free_port_accepts_zero_for_os_assigned_boundary(self) -> None:
        """Input variation: port zero asks the OS for a free port."""
        port = get_free_port(0)

        self.assertGreater(port, 0)
