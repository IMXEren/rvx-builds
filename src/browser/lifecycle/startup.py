"""Concrete owner for browser startup, profile, and launch configuration."""

from __future__ import annotations

import asyncio
import atexit
import contextlib
import enum
import shutil
import signal
import socket
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any, ClassVar, cast

from cloakbrowser import ensure_binary, launch_persistent_context_async
from loguru import logger

from src.browser.driver import (
    BrowserRuntimeState,
    DriverRemoteAttachConfig,
    DriverStartupConfig,
    resolve_cdp_ws_url,
)
from src.browser.exceptions import FailedToStartBrowserError
from src.browser.fingerprint import FingerprintManager
from src.browser.profile import SearchEngineInjector

if TYPE_CHECKING:
    from collections.abc import Callable

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
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                sock.bind(("127.0.0.1", port))
            except OSError:
                continue
            return cast("int", sock.getsockname()[1])
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
    _shutdown_state: BrowserShutdownState = BrowserShutdownState.NOT_STARTED
    _shutdown_error: BaseException | None = None
    _shutdown_task: asyncio.Task[None] | None = None
    _signal_exit_task: asyncio.Task[None] | None = None
    _signal_handlers_registered: bool = False
    _atexit_registered: bool = False
    _prior_signal_info: dict[signal.Signals, tuple[str, Any, Any]] = field(default_factory=dict)
    _preserved_signal_info: dict[signal.Signals, tuple[str, Any, Any]] | None = None
    _owns_local_profile: bool = False

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

    async def get_cdp_ws_url(self) -> str:
        """Deprecated facade for Browser compatibility; runtime owns resolution."""
        return await resolve_cdp_ws_url(self.cdp_port)

    @property
    def shutdown_state(self) -> BrowserShutdownState:
        """Return the current shutdown state for facade admission checks."""
        return self._shutdown_state

    def _reset_after_shutdown(self) -> None:
        """Reset terminal shutdown state before a new lifecycle generation."""
        self._shutdown_state = BrowserShutdownState.NOT_STARTED
        self._shutdown_error = None
        self._shutdown_task = None

    def _admit_start(self) -> None:
        """Validate and normalize shutdown state before startup side effects."""
        if self._shutdown_state is BrowserShutdownState.IN_PROGRESS:
            msg = "Browser is shutting down - cannot start."
            raise FailedToStartBrowserError(msg)
        if self._shutdown_state in {BrowserShutdownState.SUCCEEDED, BrowserShutdownState.FAILED}:
            self._reset_after_shutdown()

    async def start(
        self,
        *,
        is_running: Callable[[], bool],
        popup_handler: Callable[[Any], Any],
    ) -> None:
        """Run concrete startup sequencing and delegate live launch to the driver."""
        was_running = is_running()
        self._admit_start()
        if is_running():
            return

        async with self._startup_lock:
            self._admit_start()
            if is_running():
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
                self._register_signal_handlers()
                self._register_atexit()
            except BaseException:
                await self.driver.rollback_start()
                self._unregister_signal_handlers()
                raise
            if not was_running:
                self._owns_local_profile = True

    async def connect(
        self,
        *,
        is_running: Callable[[], bool],
        ws_url: str,
        popup_handler: Callable[[Any], Any],
    ) -> None:
        """Attach concrete drivers to a caller-owned remote CDP websocket."""
        if self._shutdown_state is BrowserShutdownState.IN_PROGRESS:
            msg = "Browser is shutting down - cannot connect."
            raise FailedToStartBrowserError(msg)
        if self._shutdown_state in {BrowserShutdownState.SUCCEEDED, BrowserShutdownState.FAILED}:
            self._reset_after_shutdown()
        if is_running():
            return

        try:
            await self.driver.attach_remote(DriverRemoteAttachConfig(ws_url=ws_url, popup_handler=popup_handler))
            self._register_signal_handlers()
            self._register_atexit()
            self._owns_local_profile = False
        except BaseException:
            self._unregister_signal_handlers()
            raise

    async def _cleanup_resources(self) -> None:
        """Close browser resources and run final synchronous profile chores."""
        await self.driver.close_all_groups_and_pages()

        if self.driver.shared_pd is not None:
            logger.debug("Closing the pydoll connection...")
            try:
                await self.driver.shared_pd.close()
            except BaseException:  # noqa: BLE001
                logger.exception("Failed to close PyDoll during cleanup")
            finally:
                self.driver.shared_pd = None

        if self.driver.main_ctx is not None and self.driver.main_ctx_owned:
            logger.debug("Closing main persistent context...")
            try:
                await self.driver.main_ctx.close()
            except BaseException:  # noqa: BLE001
                logger.exception("Failed to close Playwright context during cleanup")
        self.driver.main_ctx = None
        self.driver.main_ctx_owned = False

        if self.driver.cdp_browser is not None:
            logger.debug("Closing Playwright CDP browser...")
            try:
                await self.driver.cdp_browser.close()
            except BaseException:  # noqa: BLE001
                logger.exception("Failed to close Playwright CDP browser during cleanup")
            self.driver.cdp_browser = None

        if self.driver.cdp_playwright is not None:
            logger.debug("Stopping Playwright CDP owner...")
            try:
                await self.driver.cdp_playwright.stop()
            except BaseException:  # noqa: BLE001
                logger.exception("Failed to stop Playwright during cleanup")
            self.driver.cdp_playwright = None

        try:
            self.do_sync_chores_before_exit()
        except BaseException:  # noqa: BLE001
            logger.exception("Failed to perform final synchronous cleanup")

    async def _do_shutdown(self) -> None:
        """Own cleanup execution and terminal state finalization."""
        try:
            await self._cleanup_resources()
        except BaseException as exc:  # noqa: BLE001
            self._shutdown_state = BrowserShutdownState.FAILED
            self._shutdown_error = exc
        else:
            self._shutdown_state = BrowserShutdownState.SUCCEEDED
        finally:
            self._shutdown_task = None
            self._unregister_signal_handlers()

    async def shutdown(self) -> None:
        """Gracefully tear down all browser resources once per generation."""
        if self._shutdown_state is BrowserShutdownState.SUCCEEDED:
            return
        if self._shutdown_state is BrowserShutdownState.FAILED:
            if self._shutdown_error is None:
                msg = "Invariant: FAILED without _shutdown_error"
                raise AssertionError(msg)
            raise self._shutdown_error

        existing_task = self._shutdown_task
        if existing_task is not None and not existing_task.done():
            if self._shutdown_state is BrowserShutdownState.FAILED:
                if self._shutdown_error is None:
                    msg = "Invariant: FAILED without _shutdown_error"
                    raise AssertionError(msg)
                raise self._shutdown_error
            return

        self._shutdown_state = BrowserShutdownState.IN_PROGRESS
        cleanup_task = asyncio.get_running_loop().create_task(self._do_shutdown(), name="browser-cleanup")
        self._shutdown_task = cleanup_task

        try:
            await asyncio.shield(cleanup_task)
        except asyncio.CancelledError:  # noqa: TRY203
            raise

        if self._shutdown_state is BrowserShutdownState.FAILED:
            if self._shutdown_error is None:  # pragma: no cover
                msg = "Invariant: FAILED without _shutdown_error"
                raise AssertionError(msg)
            raise self._shutdown_error

    def do_sync_chores_before_exit(self) -> None:
        """Run bounded synchronous cleanup needed before process exit."""
        if self._owns_local_profile:
            self.pack_profile()

    def _do_sync_chores_before_exit(self) -> None:
        """Compatibility alias for lifecycle-owned synchronous chores."""
        self.do_sync_chores_before_exit()

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
            logger.exception("Emergency profile packing failed.")

    def _sync_atexit_fallback(self) -> None:
        """Compatibility alias for lifecycle-owned atexit fallback."""
        self.sync_atexit_fallback()

    def _register_atexit(self) -> None:
        """Register the lifecycle-owned synchronous fallback once."""
        if not self._atexit_registered:
            atexit.register(self.sync_atexit_fallback)
            self._atexit_registered = True

    def _register_signal_handlers(self) -> None:
        """Install graceful-first, force-second signal handling."""
        if self._signal_handlers_registered:
            return

        loop = asyncio.get_running_loop()
        installed: list[tuple[str, signal.Signals]] = []

        try:
            for sig in (signal.SIGINT, signal.SIGTERM):
                prior = signal.getsignal(sig)
                try:
                    loop.add_signal_handler(sig, self.dispatch_exit_signal, sig)
                    installed.append(("add_signal_handler", sig))
                except NotImplementedError:
                    signal.signal(
                        sig,
                        lambda signum, _frame, event_loop=loop: event_loop.call_soon_threadsafe(  # type: ignore[misc]
                            self.dispatch_exit_signal,
                            signal.Signals(signum),
                        ),
                    )
                    installed.append(("signal.signal", sig))
                self._prior_signal_info[sig] = (installed[-1][0], prior, loop)
        except BaseException:
            for kind, sig in reversed(installed):
                try:
                    if kind == "add_signal_handler":
                        loop.remove_signal_handler(sig)
                    prior_info = self._prior_signal_info.pop(sig, None)
                    if prior_info is not None:
                        signal.signal(sig, prior_info[1])
                except BaseException:  # noqa: BLE001
                    logger.exception(f"Failed to rollback signal handler for {sig}")
            raise

        self._signal_handlers_registered = True

    def _unregister_signal_handlers(self) -> None:
        """Remove registered handlers and restore exact prior handlers."""
        if not self._signal_handlers_registered:
            return

        for sig in (signal.SIGINT, signal.SIGTERM):
            kind, prior, install_loop = self._prior_signal_info.pop(sig, (None, None, None))
            if kind == "add_signal_handler" and install_loop is not None:
                with contextlib.suppress(NotImplementedError, RuntimeError, ValueError):
                    install_loop.remove_signal_handler(sig)
            if prior is not None and (self._preserved_signal_info is None or sig not in self._preserved_signal_info):
                with contextlib.suppress(ValueError, TypeError):
                    signal.signal(sig, prior)

        self._signal_handlers_registered = False

    def _preserve_signal(self, sig: signal.Signals) -> None:
        """Snapshot signal metadata for one triggering signal if registered."""
        self._preserved_signal_info = {sig: self._prior_signal_info[sig]} if sig in self._prior_signal_info else None

    def dispatch_exit_signal(self, sig: signal.Signals) -> None:
        """Synchronously dispatch an exit signal."""
        signal_task = self._signal_exit_task
        is_running = self._shutdown_state is BrowserShutdownState.IN_PROGRESS
        task_active = signal_task is not None and not signal_task.done()
        if is_running or task_active:
            self.force_exit(sig)
            return

        logger.warning(
            f"[Browser] Received {sig.name}. Starting graceful shutdown. Send the signal again to force termination.",
        )
        self._preserve_signal(sig)
        self._shutdown_state = BrowserShutdownState.IN_PROGRESS

        loop = asyncio.get_running_loop()
        self._signal_exit_task = loop.create_task(
            self._handle_signal_exit(sig),
            name=f"browser-shutdown-{sig.name.lower()}",
        )

        def _on_signal_exit_done(task: asyncio.Task[None]) -> None:
            if task.cancelled() and self._preserved_signal_info is not None:
                for sig_key in list(self._preserved_signal_info):
                    handler = self._consume_signal_metadata(signal.Signals(sig_key))
                    with contextlib.suppress(ValueError, TypeError):
                        signal.signal(signal.Signals(sig_key), handler)
                self._unregister_signal_handlers()
                self._preserved_signal_info = None
                if self._shutdown_state is BrowserShutdownState.IN_PROGRESS:
                    self._shutdown_state = BrowserShutdownState.NOT_STARTED

        self._signal_exit_task.add_done_callback(_on_signal_exit_done)

    def _dispatch_exit_signal(self, sig: signal.Signals) -> None:
        """Compatibility alias for lifecycle-owned signal dispatch."""
        self.dispatch_exit_signal(sig)

    async def _handle_signal_exit(self, sig: signal.Signals) -> None:
        """Run graceful cleanup, then terminate with normal signal semantics."""
        try:
            await self.shutdown()
        except asyncio.CancelledError:
            logger.warning("Browser shutdown was cancelled.")
            raise
        except BaseException:  # noqa: BLE001
            logger.exception(f"Unhandled error during graceful shutdown for {sig.name}.")
        finally:
            self._terminate_by_signal(sig)

    def force_exit(self, sig: signal.Signals) -> None:
        """Immediately terminate after a second signal."""
        logger.critical(f"[Browser] Received {sig.name} again during shutdown; forcing exit.")
        if self._shutdown_state not in (BrowserShutdownState.SUCCEEDED, BrowserShutdownState.FAILED):
            try:
                self.do_sync_chores_before_exit()
            except BaseException:  # noqa: BLE001
                logger.exception("[Browser] Failed to do the left out chores")
        self._terminate_by_signal(sig)

    def _consume_signal_metadata(self, sig: signal.Signals) -> Any:
        """Consume preserved/prior metadata for *sig* and return a handler."""
        handler: Any = signal.SIG_DFL
        if self._preserved_signal_info is not None and sig in self._preserved_signal_info:
            info = self._preserved_signal_info.pop(sig)
            if not self._preserved_signal_info:
                self._preserved_signal_info = None
            if info is not None:
                handler = info[1]

        prior_info = self._prior_signal_info.pop(sig, None)
        if prior_info is not None:
            kind, prior, install_loop = prior_info
            if handler is signal.SIG_DFL:
                handler = prior
            if kind == "add_signal_handler" and install_loop is not None:
                with contextlib.suppress(NotImplementedError, RuntimeError, ValueError):
                    install_loop.remove_signal_handler(sig)

        return handler

    def _terminate_by_signal(self, sig: signal.Signals) -> None:
        """Restore prior handler and re-deliver the signal to this process."""
        handler = self._consume_signal_metadata(sig)
        signal.signal(sig, handler)
        signal.raise_signal(sig)

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
