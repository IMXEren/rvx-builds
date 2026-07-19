"""Concrete owner for browser startup, profile, and launch configuration."""

from __future__ import annotations

import asyncio
import atexit
import enum
import shutil
import socket
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, ClassVar

from cloakbrowser import ensure_binary, launch_persistent_context_async
from loguru import logger

from src.browser.driver import (
    BrowserRuntimeState,
    DriverRemoteAttachConfig,
    DriverStartupConfig,
)
from src.browser.exceptions import BrowserShutdownError, BrowserStartError
from src.browser.fingerprint import FingerprintManager
from src.browser.profile import SearchEngineInjector
from src.signals import CoordinatorStateError, RegistrationToken, get_coordinator

if TYPE_CHECKING:
    from collections.abc import Callable, Coroutine

    from playwright.async_api import Page as PWPage
    from pydoll.browser.options import ChromiumOptions


class BrowserShutdownState(enum.Enum):
    """Shutdown state machine for the concrete browser lifecycle."""

    NOT_STARTED = enum.auto()
    IN_PROGRESS = enum.auto()
    SUCCEEDED = enum.auto()
    FAILED = enum.auto()


def get_free_port(preferred: int, fallback_range: range | None = None) -> int:
    """Return *preferred* if available, else the first free port in *fallback_range*."""
    candidates = (preferred, *(fallback_range or range(0)))
    for port in candidates:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            try:
                sock.bind(("127.0.0.1", port))
            except OSError:
                continue
            return sock.getsockname()[1]
    msg = "No free TCP port found for browser CDP."
    raise RuntimeError(msg)


@dataclass(slots=True)
class BrowserLifecycle:
    """Concrete lifecycle owner for startup and profile configuration."""

    driver: BrowserRuntimeState
    profile_dir: str = "/tmp/browser-profile"  # noqa: S108
    profile_archive: Path = Path("browser-profile.zip")
    checked_binary: bool = False
    cdp_port: int = 9222
    fingerprint: FingerprintManager | None = None
    fingerprint_options: ChromiumOptions | None = None
    viewport: dict[str, int] = field(default_factory=lambda: {"width": 1920, "height": 980})
    locale: str = "en-US,en"
    _startup_lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    _shutdown_lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    _shutdown_state: BrowserShutdownState = BrowserShutdownState.NOT_STARTED
    _shutdown_error: BrowserShutdownError | None = None
    _shutdown_task: asyncio.Task[None] | None = None
    _atexit_registered: bool = False
    _owns_local_profile: bool = False
    _signal_registration: RegistrationToken | None = None

    _SKIP_PROFILE_DIRS: ClassVar[set[str]] = {
        "Cache",
        "Code Cache",
        "GPUCache",
        "DawnCache",
        "DawnGraphiteCache",
        "DawnWebGPUCache",
        "blob_storage",
        "ShaderCache",
        "GrShaderCache",
    }

    # -- Profile helpers ------------------------------------------------------------

    def webdata_path(self) -> Path:
        """Return the Chrome Web Data path in the owned profile directory."""
        return Path(self.profile_dir) / "Default" / "Web Data"

    def unpack_profile(self, archive: str | Path | None = None) -> bool:
        """Restore the owned profile directory from *archive* when available."""
        pkg = Path(archive) if archive else self.profile_archive
        if not pkg.exists():
            return False
        target = Path(self.profile_dir)
        if target.exists():
            shutil.rmtree(target)
        logger.info(f"Extracting profile from {pkg} ...")
        shutil.unpack_archive(str(pkg), str(target))
        return True

    def pack_profile(self, archive: str | Path | None = None) -> Path | None:
        """Zip the owned profile directory into *archive*, skipping caches."""
        profile_dir = Path(self.profile_dir)
        if not profile_dir.exists():
            return None

        pkg = (Path(archive) if archive else self.profile_archive).resolve()
        profile_dir = profile_dir.resolve()

        if pkg.is_relative_to(profile_dir):
            pkg = profile_dir.parent / pkg.name

        stale = profile_dir / pkg.name
        stale.unlink(missing_ok=True)
        pkg.unlink(missing_ok=True)

        files: list[Path] = []
        for entry in profile_dir.rglob("*"):
            if not entry.is_file():
                continue
            if any(part in self._SKIP_PROFILE_DIRS for part in entry.parts):
                continue
            if entry.name.endswith("-journal"):
                continue
            if entry.resolve() == pkg.resolve():
                continue
            files.append(entry)

        with zipfile.ZipFile(str(pkg), "w", zipfile.ZIP_DEFLATED) as zf:
            for file_path in files:
                zf.write(file_path, file_path.relative_to(profile_dir))
        logger.info(f"Profile archived to {pkg} ({len(files)} files).")
        return pkg

    @property
    def shutdown_state(self) -> BrowserShutdownState:
        """Return the current shutdown state for facade admission checks."""
        return self._shutdown_state

    # -- Admission helpers ----------------------------------------------------------

    def _reset_after_shutdown(self) -> None:
        """Reset terminal shutdown state before a new lifecycle generation."""
        self._shutdown_state = BrowserShutdownState.NOT_STARTED
        self._shutdown_error = None
        self._shutdown_task = None

    def _admit_start(self) -> None:
        """Validate and normalize shutdown state before startup side effects."""
        if self._shutdown_state is BrowserShutdownState.IN_PROGRESS:
            msg = "Browser is shutting down - cannot start."
            raise BrowserStartError(msg)
        if self._shutdown_state in {BrowserShutdownState.SUCCEEDED, BrowserShutdownState.FAILED}:
            self._reset_after_shutdown()

    # -- Start / connect ------------------------------------------------------------

    async def start(
        self,
        *,
        is_running: Callable[[], bool],
        popup_handler: Callable[[PWPage], Coroutine[None, None, None]],
    ) -> None:
        """Run concrete startup sequencing and delegate live launch to the driver.

        OS signal installation is owned by src.signals; this method only
        performs browser-specific launch and atexit registration.
        """
        self._admit_start()
        if is_running():
            self._register_signal_cleanup()
            return

        async with self._startup_lock:
            self._admit_start()
            if is_running():
                self._register_signal_cleanup()
                return

            self.unpack_profile()
            if not self.checked_binary:
                ensure_binary()
                self.checked_binary = True

            self.cdp_port = get_free_port(self.cdp_port, range(9223, 9323))
            profile = {
                "screen": self.viewport,
                "user_data_dir": self.profile_dir,
                "port": self.cdp_port,
            }
            self.fingerprint = FingerprintManager(profile)
            self.fingerprint_options = self.fingerprint.options
            launch_arguments = list(self.fingerprint.options.arguments)

            if not self.webdata_path().exists():
                await self._prime_profile(launch_arguments)

            self._inject_search_engine()

            try:
                await self.driver.start_live(
                    DriverStartupConfig(
                        profile_dir=self.profile_dir,
                        user_data_dir=self.profile_dir,
                        cdp_port=self.cdp_port,
                        fingerprint_options=self.fingerprint.options,
                        launch_arguments=launch_arguments,
                        viewport=dict(self.viewport),
                        locale=self.locale,
                        popup_handler=popup_handler,
                    ),
                )

                self._owns_local_profile = True

                self._register_signal_cleanup()
                self._register_atexit()
            except BaseException as e:
                self._unregister_atexit()
                self._unregister_signal_cleanup()
                await self.driver.rollback_start()
                msg = "failed to start the browser"
                raise BrowserStartError(msg) from e

    async def connect(
        self,
        *,
        is_running: Callable[[], bool],
        ws_url: str,
        popup_handler: Callable[[PWPage], Coroutine[None, None, None]],
    ) -> None:
        """Attach concrete drivers to a caller-owned remote CDP websocket.

        OS signal installation is owned by src.signals; this method only
        performs remote driver attach and atexit registration.
        """
        self._admit_start()

        async with self._startup_lock:
            self._admit_start()
            if is_running():
                self._register_signal_cleanup()
                return

            try:
                await self.driver.attach_remote(DriverRemoteAttachConfig(ws_url=ws_url, popup_handler=popup_handler))
                self._register_signal_cleanup()
            except BaseException as e:
                self._unregister_signal_cleanup()
                await self.driver.rollback_start()
                msg = "failed to connect browser"
                raise BrowserStartError(msg) from e
            self._owns_local_profile = False

    # -- Cleanup resources ----------------------------------------------------------

    async def _cleanup_resources(self) -> None:
        """Close browser resources and run final synchronous profile chores."""
        try:
            await self.driver.close_all_groups_and_pages()
        except BaseException:  # noqa: BLE001
            logger.error("Failed to close browser groups and pages")

        if self.driver.shared_pd is not None:
            logger.debug("Closing the pydoll connection...")
            try:
                await self.driver.shared_pd.close()
            except BaseException:  # noqa: BLE001
                logger.error("Failed to close PyDoll during cleanup")
            finally:
                self.driver.shared_pd = None

        if self.driver.main_ctx is not None and self.driver.main_ctx_owned:
            logger.debug("Closing main persistent context...")
            try:
                await self.driver.main_ctx.close()
            except BaseException:  # noqa: BLE001
                logger.error("Failed to close Playwright context during cleanup")
        self.driver.main_ctx = None
        self.driver.main_ctx_owned = False

        if self.driver.cdp_browser is not None:
            logger.debug("Closing Playwright CDP browser...")
            try:
                await self.driver.cdp_browser.close()
            except BaseException:  # noqa: BLE001
                logger.error("Failed to close Playwright CDP browser during cleanup")
            self.driver.cdp_browser = None

        if self.driver.cdp_playwright is not None:
            logger.debug("Stopping Playwright CDP owner...")
            try:
                await self.driver.cdp_playwright.stop()
            except BaseException:  # noqa: BLE001
                logger.error("Failed to stop Playwright during cleanup")
            self.driver.cdp_playwright = None

        self.do_sync_chores_before_exit()

    async def _do_shutdown(self) -> None:
        """Own cleanup execution and terminal state finalization."""
        try:
            await self._cleanup_resources()
        except BaseException as exc:  # noqa: BLE001
            self._shutdown_state = BrowserShutdownState.FAILED
            self._shutdown_error = BrowserShutdownError(exc)
        else:
            self._shutdown_state = BrowserShutdownState.SUCCEEDED
        finally:
            self._unregister_signal_cleanup()
            self._unregister_atexit()
            self._shutdown_task = None

    # -- Signal cleanup ownership ---------------------------------------------------

    def _register_signal_cleanup(self) -> None:
        """Register asynchronous browser cleanup when coordination is available."""
        token = self._signal_registration

        if token is not None and token.active:
            return

        coordinator = get_coordinator()
        if not coordinator.guarantees_cleanup:
            return

        try:
            self._signal_registration = coordinator.register(
                self.shutdown,
                owner_loop=asyncio.get_running_loop(),
                name="browser",
            )
        except CoordinatorStateError:
            # A signal may have started shutdown between the availability check
            # and registration. Browser remains usable without coordination.
            logger.debug(
                "Browser signal cleanup was not registered because "
                "the coordinator is no longer accepting registrations.",
            )

    def _unregister_signal_cleanup(self) -> None:
        """Remove the browser cleanup registration after a normal shutdown."""
        token = self._signal_registration
        self._signal_registration = None

        if token is not None:
            token.unregister()

    def _register_atexit(self) -> None:
        """Register the lifecycle-owned synchronous fallback once."""
        if not self._atexit_registered:
            atexit.register(self.sync_atexit_fallback)
            self._atexit_registered = True

    def _unregister_atexit(self) -> None:
        """Unregister the lifecycle-owned synchronous fallback once."""
        if self._atexit_registered:
            atexit.unregister(self.sync_atexit_fallback)
            self._atexit_registered = False

    # -- Shutdown with cancellation resilience --------------------------------------

    async def shutdown(self) -> None:
        """Gracefully tear down all browser resources once per generation.

        The owner must tolerate repeated CancelledError while awaiting the
        same shielded cleanup task to terminal SUCCEEDED / FAILED state.
        Cancellation is immediately propagated; the shielded cleanup task
        continues independently to its terminal outcome.
        """
        shutdown_state = self._shutdown_state
        if shutdown_state is BrowserShutdownState.SUCCEEDED:
            return
        if shutdown_state is BrowserShutdownState.FAILED:
            if self._shutdown_error is None:
                msg = "Invariant: FAILED without _shutdown_error"
                raise BrowserShutdownError(msg)
            raise self._shutdown_error

        async with self._shutdown_lock:
            # Re-check terminal states after acquiring the lock.
            shutdown_state = self._shutdown_state
            if shutdown_state is BrowserShutdownState.SUCCEEDED:
                return
            if shutdown_state is BrowserShutdownState.FAILED:
                if self._shutdown_error is None:
                    msg = "Invariant: FAILED without _shutdown_error"
                    raise BrowserShutdownError(msg)
                raise self._shutdown_error

            existing_task = self._shutdown_task
            if existing_task is not None and not existing_task.done():
                # Capture reference for awaiting outside the lock.
                cleanup_to_await: asyncio.Task[None] = existing_task
            else:
                self._shutdown_state = BrowserShutdownState.IN_PROGRESS
                cleanup_to_await = asyncio.get_running_loop().create_task(
                    self._do_shutdown(), name="browser-cleanup",
                )
                self._shutdown_task = cleanup_to_await

        # Await the shielded cleanup outside the lock so waiters can enter.
        # Cancellation propagates immediately; the shielded cleanup task
        # survives and will reach terminal independently.
        await asyncio.shield(cleanup_to_await)

        if self._shutdown_state is BrowserShutdownState.FAILED:
            if self._shutdown_error is None:  # pragma: no cover
                msg = "Invariant: FAILED without _shutdown_error"
                raise BrowserShutdownError(msg)
            raise self._shutdown_error

    # -- Synchronous chores ---------------------------------------------------------

    def do_sync_chores_before_exit(self) -> None:
        """Run bounded synchronous cleanup needed before process exit."""
        if self._owns_local_profile:
            self.pack_profile()
            self._owns_local_profile = False

    def sync_atexit_fallback(self) -> None:
        """Last synchronous safety net for profile preservation."""
        if self._shutdown_state in (BrowserShutdownState.SUCCEEDED, BrowserShutdownState.FAILED):
            return

        logger.warning(
            "Process exited before asynchronous browser cleanup completed. "
            "Running synchronous preservation fallback.",
        )

        try:
            self.do_sync_chores_before_exit()
        except BaseException:  # noqa: BLE001
            logger.error("Sync last-minute chores failed!")

    # -- Profile priming ------------------------------------------------------------

    async def _prime_profile(self, launch_arguments: list[str]) -> None:
        """Launch and close a headless context before Web Data injection."""
        logger.debug("Priming fresh profile to generate User Data...")
        prime_ctx = await launch_persistent_context_async(
            headless=True,
            args=launch_arguments,
            viewport=self.viewport,
            locale=self.locale,
            geoip=True,
            humanize=True,
            user_data_dir=self.profile_dir,
        )
        try:
            await asyncio.sleep(1)
        finally:
            await prime_ctx.close()

    def _inject_search_engine(self) -> None:
        """Inject Google after Web Data exists in the primed Chrome profile."""
        with SearchEngineInjector(self.profile_dir) as injector:
            injector.inject(
                short_name="Google",
                keyword="google.com",
                url="https://www.google.com/search?q={searchTerms}",
                suggest_url="https://www.google.com/complete/search?client=chrome&q={searchTerms}",
            )
