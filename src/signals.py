"""One-shot process-wide graceful signal coordinator.

The coordinator temporarily owns selected process signals, drains registered
cleanup handlers in strict LIFO order, restores the exact previous signal
handlers, and then redelivers the triggering signal.

A coordinator is intentionally one-shot.  Once a managed signal is received,
registration closes permanently.  If the process survives redelivery because
the previous signal handler returns or its exception is caught, future signals
are handled directly by the restored process handlers.

Installation and signal-handler restoration are main-thread-only. Registration
operations are thread-safe. Cleanup handlers run sequentially in strict LIFO
order: synchronous handlers run on the coordinator worker, while asynchronous
handlers run on the event loop supplied when they are registered.
"""

from __future__ import annotations

import asyncio
import contextlib
import ctypes
import enum
import inspect
import itertools
import os
import signal
import threading
import time
import weakref
from collections import deque
from collections.abc import Awaitable, Callable, Iterable, Mapping
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Self, TypeVar

from loguru import logger

if TYPE_CHECKING:
    import concurrent.futures
    from subprocess import Popen

MANAGED_SIGNALS = (signal.SIGINT, signal.SIGTERM)
DEFAULT_GRACE_PERIOD = 5.0

T = TypeVar("T")

type CleanupResult = Awaitable[None] | None
type CleanupCallback = Callable[[], CleanupResult]
type SignalHandler = Callable[[int, Any], Any] | int | None


class SignalCoordinatorError(RuntimeError):
    """Base class for signal-coordinator errors."""


class CoordinatorStateError(SignalCoordinatorError):
    """Raised when an operation is invalid in the coordinator's current phase."""


class OperationCancelledError(Exception):
    """Raised when application shutdown cancels active work."""


class CoordinatorPhase(enum.Enum):
    """Lifecycle of a one-shot coordinator."""

    NEW = "NEW"
    ACTIVE = "ACTIVE"
    DRAINING = "DRAINING"
    FINALIZING = "FINALIZING"
    UNINSTALLED = "UNINSTALLED"


# ---------------------------------------------------------------------------
# CPython main-thread pending-call bridge
# ---------------------------------------------------------------------------

_PendingCallCallback = ctypes.CFUNCTYPE(ctypes.c_int, ctypes.c_void_p)
_PENDING_CALLS: deque[Callable[[], None]] = deque()
_PENDING_CALLS_LOCK = threading.Lock()
_PENDING_CALL_SCHEDULED = False


@_PendingCallCallback
def _drain_pending_calls(_argument: ctypes.c_void_p) -> int:
    """Run callbacks posted through ``Py_AddPendingCall`` on the main thread."""
    del _argument
    global _PENDING_CALL_SCHEDULED  # noqa: PLW0603

    while True:
        with _PENDING_CALLS_LOCK:
            if not _PENDING_CALLS:
                _PENDING_CALL_SCHEDULED = False
                return 0
            callback = _PENDING_CALLS.popleft()

        try:
            callback()
        except BaseException:  # noqa: BLE001
            logger.exception("Main-thread pending callback failed.")


try:
    _PY_ADD_PENDING_CALL = ctypes.pythonapi.Py_AddPendingCall
except AttributeError:  # pragma: no cover - non-CPython interpreter
    _PY_ADD_PENDING_CALL = None
else:
    _PY_ADD_PENDING_CALL.argtypes = (_PendingCallCallback, ctypes.c_void_p)
    _PY_ADD_PENDING_CALL.restype = ctypes.c_int


def _post_to_main_thread(
    callback: Callable[[], None],
    *,
    retry_timeout: float = 1.0,
) -> None:
    """Schedule *callback* on the CPython main thread, retrying a full queue."""
    global _PENDING_CALL_SCHEDULED  # noqa: PLW0603

    if _PY_ADD_PENDING_CALL is None:
        msg = "SignalCoordinator requires CPython's Py_AddPendingCall"
        raise SignalCoordinatorError(msg)

    deadline = time.monotonic() + retry_timeout
    queued = False

    while True:
        with _PENDING_CALLS_LOCK:
            if not queued:
                _PENDING_CALLS.append(callback)
                queued = True

            if _PENDING_CALL_SCHEDULED:
                return

            _PENDING_CALL_SCHEDULED = True
            if _PY_ADD_PENDING_CALL(_drain_pending_calls, None) == 0:
                return
            _PENDING_CALL_SCHEDULED = False

        if time.monotonic() >= deadline:
            with _PENDING_CALLS_LOCK, contextlib.suppress(ValueError):
                _PENDING_CALLS.remove(callback)
            msg = "CPython pending-call queue remained full; cannot finalize signal handling"
            raise SignalCoordinatorError(msg)

        time.sleep(0.001)


@dataclass(slots=True)
class _Registration:
    identifier: int
    callback: CleanupCallback
    owner_loop: asyncio.AbstractEventLoop | None
    name: str
    timeout: float | None


class RegistrationToken:
    """Opaque handle used to unregister one cleanup callback.

    ``unregister()`` is idempotent. It returns ``True`` only when that call
    removed an active registration. Once shutdown begins, frozen tokens have
    already been detached and therefore report inactive.
    """

    __slots__ = ("_coordinator_id", "_coordinator_ref", "_identifier")

    def __init__(self, coordinator: SignalCoordinator, identifier: int) -> None:
        self._coordinator_ref = weakref.ref(coordinator)
        self._coordinator_id = id(coordinator)
        self._identifier = identifier

    @property
    def active(self) -> bool:
        """Whether this token still owns an active registration."""
        coordinator = self._coordinator_ref()
        return coordinator is not None and coordinator.registration_active(self)

    def unregister(self) -> bool:
        """Remove this registration if it is still active."""
        coordinator = self._coordinator_ref()
        if coordinator is None:
            return False
        return coordinator.unregister(self)

    def __enter__(self) -> Self:
        """Enter a synchronous context."""
        return self

    def __exit__(self, *exc_info: object) -> None:
        """Unregister when leaving a synchronous context."""
        del exc_info
        self.unregister()

    async def __aenter__(self) -> Self:
        """Enter an asynchronous context."""
        return self

    async def __aexit__(self, *exc_info: object) -> None:
        """Unregister when leaving an asynchronous context."""
        del exc_info
        self.unregister()

    def __repr__(self) -> str:
        """Return a diagnostic representation."""
        return f"RegistrationToken({self._identifier})"

    def __hash__(self) -> int:
        """Return a stable hash for the token's lifetime."""
        return hash((self._coordinator_id, self._identifier))

    def __eq__(self, other: object) -> bool:
        """Compare coordinator and registration identity."""
        if not isinstance(other, RegistrationToken):
            return NotImplemented
        return self._coordinator_id == other._coordinator_id and self._identifier == other._identifier


class CancellationToken:
    """Thread-safe cooperative cancellation token.

    The token wraps a shared event that may be set from any thread to request
    cancellation of ongoing work. Operations cooperate by checking
    `cancelled`, calling `raise_if_cancelled()`, or waiting through
    `wait()` at suitable interruption points.

    Cancellation is persistent and one-way: once `cancel()` is called, the
    token remains cancelled for its lifetime. The token does not forcibly
    terminate threads or inject exceptions into running code; callers must
    observe it explicitly and stop at safe boundaries.
    """

    def __init__(self) -> None:
        self._event = threading.Event()

    @property
    def cancelled(self) -> bool:
        """Whether the token was cancelled."""
        return self._event.is_set()

    def cancel(self) -> None:
        """Cancel the token. Doesn't raise any errors."""
        self._event.set()

    def raise_if_cancelled(self) -> None:
        """Raise :exc:`OperationCancelledError` if the token is cancelled."""
        if self._event.is_set():
            raise OperationCancelledError

    def wait(self, timeout: float | None = None) -> bool:
        """Return True if cancellation occurred."""
        return self._event.wait(timeout)

    async def wait_async(
        self,
        *,
        poll_interval: float = 0.1,
    ) -> None:
        """Wait asynchronously until cancellation is requested."""
        while not self.cancelled:  # noqa: ASYNC110
            await asyncio.sleep(poll_interval)

    def wait_for_event_in_daemon(  # noqa: PLR0913
        self,
        completed: threading.Event,
        *,
        poll_interval: float = 0.1,
        name: str = "cancellation-watcher",
        on_cancel: Callable[..., None],
        args: tuple[Any, ...] = (),
        kwargs: Mapping[str, Any] | None = None,
    ) -> threading.Thread:
        """Run ``on_cancel`` in a daemon thread if cancellation precedes completion.

        The watcher exits silently when ``completed`` is set. If cancellation
        is requested first, it calls ``on_cancel`` once and then exits.

        The completion event takes precedence when completion and cancellation
        occur at approximately the same time.
        """
        cb_kwargs = dict(kwargs) if kwargs is not None else {}

        def watch() -> None:
            while not completed.wait(poll_interval):
                if self.cancelled:
                    # Resolve a race where completion occurred immediately
                    # after the timed wait returned.
                    if not completed.is_set():
                        on_cancel(*args, **cb_kwargs)
                    return

        thread = threading.Thread(
            target=watch,
            name=name,
            daemon=True,
        )
        thread.start()
        return thread

    @staticmethod
    def terminate_process(process: Popen[bytes]) -> None:
        """To be used with :meth:`wait_for_event_in_daemon`'s callback to safely terminate the process."""
        if process.poll() is not None:
            return

        try:
            process.terminate()
        except OSError:
            if process.poll() is None:
                # Child hasn't terminated yet
                raise

    async def race(
        self,
        awaitable: Awaitable[T],
        *,
        poll_interval: float = 0.1,
    ) -> T:
        """Return the awaitable's result or raise if cancellation wins."""
        self.raise_if_cancelled()

        operation_task = asyncio.ensure_future(awaitable)
        cancellation_task = asyncio.create_task(
            self.wait_async(poll_interval=poll_interval),
            name="wait-for-cancellation",
        )

        try:
            done, _ = await asyncio.wait(
                (operation_task, cancellation_task),
                return_when=asyncio.FIRST_COMPLETED,
            )

            if cancellation_task in done:
                # Prefer a completed operation if both finished concurrently.
                if operation_task.done():
                    return await operation_task

                operation_task.cancel()
                await asyncio.gather(
                    operation_task,
                    return_exceptions=True,
                )

                self.raise_if_cancelled()
                msg = "Cancellation waiter completed without cancellation."
                raise RuntimeError(msg)

            return await operation_task

        finally:
            if not cancellation_task.done():
                cancellation_task.cancel()

            await asyncio.gather(
                cancellation_task,
                return_exceptions=True,
            )


class SignalCoordinator:
    """Coordinate process-wide graceful cleanup before native propagation.

    ``install()`` requires only the main thread; it does not require asyncio.

    A registration with ``owner_loop=None`` runs on the coordinator worker and
    must be synchronous. A registration with ``owner_loop=loop`` must be an
    async function and runs on that loop's thread.

    Cleanup is strictly sequential and LIFO. A second managed signal during
    draining abandons the remaining grace period and propagates immediately.
    """

    def __init__(
        self,
        *,
        signals: Iterable[signal.Signals] = MANAGED_SIGNALS,
        grace_period: float = DEFAULT_GRACE_PERIOD,
    ) -> None:
        managed = tuple(dict.fromkeys(signals))  # dedup with order preserving
        if not managed:
            msg = "at least one managed signal is required"
            raise ValueError(msg)
        if grace_period < 0:
            msg = "grace_period must be non-negative"
            raise ValueError(msg)

        self._signals = managed
        self._grace_period = float(grace_period)
        self._phase = CoordinatorPhase.NEW
        self._prior_handlers: dict[signal.Signals, SignalHandler] = {}

        self._registrations: dict[int, _Registration] = {}
        self._registration_snapshot: tuple[_Registration, ...] = ()
        self._frozen_identifiers: frozenset[int] = frozenset()
        self._ids = itertools.count(1)
        self._lock = threading.RLock()

        self._worker: threading.Thread | None = None
        self._active_async_future: concurrent.futures.Future[None] | None = None
        self._abort = threading.Event()
        self._triggering_signal: signal.Signals | None = None
        self._deadline: float | None = None
        self._signal_count = 0

    # ------------------------------------------------------------------
    # lifecycle
    # ------------------------------------------------------------------

    def install(self) -> None:
        """Install managed handlers from the main thread."""
        self._assert_main_thread()
        if _PY_ADD_PENDING_CALL is None:
            msg = "SignalCoordinator requires CPython's Py_AddPendingCall"
            raise SignalCoordinatorError(msg)

        with self._lock:
            if self._phase is CoordinatorPhase.ACTIVE:
                return
            if self._phase is CoordinatorPhase.UNINSTALLED:
                msg = "a one-shot coordinator cannot be reinstalled"
                raise CoordinatorStateError(msg)
            if self._phase is not CoordinatorPhase.NEW:
                msg = f"cannot install coordinator in phase {self._phase.value}"
                raise CoordinatorStateError(msg)

            saved: dict[signal.Signals, SignalHandler] = {}
            installed: list[signal.Signals] = []
            try:
                for managed_signal in self._signals:
                    saved[managed_signal] = signal.getsignal(managed_signal)
                    signal.signal(managed_signal, self._on_signal)
                    installed.append(managed_signal)
            except BaseException:
                for managed_signal in reversed(installed):
                    with contextlib.suppress(Exception):
                        signal.signal(managed_signal, saved[managed_signal])
                raise

            self._prior_handlers = saved
            self._phase = CoordinatorPhase.ACTIVE

    def uninstall(self) -> None:
        """Permanently restore previous handlers without signal redelivery."""
        self._assert_main_thread()

        with self._lock:
            if self._phase is CoordinatorPhase.NEW:
                return
            if self._phase is CoordinatorPhase.UNINSTALLED:
                return
            if self._phase in (
                CoordinatorPhase.DRAINING,
                CoordinatorPhase.FINALIZING,
            ):
                msg = "cannot manually uninstall during shutdown"
                raise CoordinatorStateError(msg)

            self._restore_handlers()
            self._registrations.clear()
            self._registration_snapshot = ()
            self._frozen_identifiers = frozenset()
            self._phase = CoordinatorPhase.UNINSTALLED

    # ------------------------------------------------------------------
    # registration
    # ------------------------------------------------------------------

    def register(
        self,
        cleanup: CleanupCallback,
        *,
        owner_loop: asyncio.AbstractEventLoop | None = None,
        name: str | None = None,
        timeout: float | None = None,
    ) -> RegistrationToken:
        """Register a cleanup callback and return an opaque token."""
        if not callable(cleanup):
            msg = "cleanup must be callable"
            raise TypeError(msg)
        if timeout is not None and timeout < 0:
            msg = "timeout must be non-negative"
            raise ValueError(msg)

        if owner_loop is not None:
            if not inspect.iscoroutinefunction(cleanup):
                msg = "a cleanup with owner_loop must be an async function"
                raise SignalCoordinatorError(msg)
            if owner_loop.is_closed() or not owner_loop.is_running():
                msg = "owner_loop must be running and not closed"
                raise SignalCoordinatorError(msg)
        elif inspect.iscoroutinefunction(cleanup):
            msg = "an async cleanup requires its running owner_loop"
            raise SignalCoordinatorError(msg)

        with self._lock:
            if self._phase is not CoordinatorPhase.ACTIVE:
                msg = f"signal cleanup is not guaranteed because the coordinator is {self._phase.value.lower()}"
                raise CoordinatorStateError(msg)

            identifier = next(self._ids)
            registration = _Registration(
                identifier=identifier,
                callback=cleanup,
                owner_loop=owner_loop,
                name=name or getattr(cleanup, "__qualname__", repr(cleanup)),
                timeout=None if timeout is None else float(timeout),
            )

            new_registry = dict(self._registrations)
            new_registry[identifier] = registration
            self._registrations = new_registry
            self._registration_snapshot = tuple(new_registry.values())

            # A signal can freeze the lock-free snapshot while this thread is
            # publishing. Accept the registration only when it was included.
            if self._phase is not CoordinatorPhase.ACTIVE and identifier not in self._frozen_identifiers:
                rollback = dict(self._registrations)
                rollback.pop(identifier, None)
                self._registrations = rollback
                self._registration_snapshot = tuple(rollback.values())
                msg = "cannot register after signal shutdown has started"
                raise CoordinatorStateError(msg)

            return RegistrationToken(self, identifier)

    def unregister(self, token: RegistrationToken) -> bool:
        """Remove one active registration; return false when already absent."""
        self._validate_token(token)
        with self._lock:
            new_registry = dict(self._registrations)
            removed = new_registry.pop(token._identifier, None)  # noqa: SLF001
            if removed is None:
                return False

            self._registrations = new_registry
            self._registration_snapshot = tuple(new_registry.values())

            # The signal handler may already have frozen the old snapshot. In
            # that case removal cannot prevent this cleanup from running.
            return self._phase is CoordinatorPhase.ACTIVE or token._identifier not in self._frozen_identifiers

    def registration_active(self, token: RegistrationToken) -> bool:
        """Return whether *token* still represents an active registration."""
        self._validate_token(token)
        with self._lock:
            return token._identifier in self._registrations  # noqa: SLF001

    register_callback = register
    unregister_callback = unregister

    # ------------------------------------------------------------------
    # signal path
    # ------------------------------------------------------------------

    def _on_signal(self, signum: int, frame: object | None) -> None:
        """Handle managed signals without acquiring coordinator locks."""
        del frame
        received = signal.Signals(signum)
        self._signal_count += 1

        if self._phase is CoordinatorPhase.ACTIVE:
            get_process_cancel_token().cancel()

            self._phase = CoordinatorPhase.DRAINING
            self._triggering_signal = received
            self._deadline = time.monotonic() + self._grace_period

            snapshot = self._registration_snapshot
            self._frozen_identifiers = frozenset(registration.identifier for registration in snapshot)
            self._registrations = {}
            self._registration_snapshot = ()
            registrations = list(reversed(snapshot))

            worker = threading.Thread(
                target=self._drain_worker,
                args=(registrations,),
                name="signal-coordinator-shutdown",
                daemon=True,
            )
            self._worker = worker
            worker.start()
            return

        if self._phase in (
            CoordinatorPhase.DRAINING,
            CoordinatorPhase.FINALIZING,
        ):
            logger.warning(
                "Received {} during graceful shutdown; escalating.",
                received.name,
            )
            self._abort.set()
            future = self._active_async_future
            if future is not None:
                future.cancel()
            self._propagate_from_main(received)
            return

        # Defensive fallback. Normally the coordinator handler is no longer
        # installed after UNINSTALLED.
        self._restore_handlers()
        signal.raise_signal(received)

    def _drain_worker(self, registrations: list[_Registration]) -> None:
        for index, registration in enumerate(registrations):
            if self._abort.is_set():
                return

            remaining = self._remaining_grace()
            if remaining <= 0:
                logger.warning(
                    "Grace period expired; skipping {} cleanup handler(s).",
                    len(registrations) - index,
                )
                break

            self._run_registration(registration, remaining)

        with self._lock:
            if self._phase is not CoordinatorPhase.DRAINING or self._abort.is_set():
                return
            self._phase = CoordinatorPhase.FINALIZING
            self._worker = None

        try:
            _post_to_main_thread(self._finalize_on_main_thread)
        except BaseException:  # noqa: BLE001
            # There is no portable, safe way for this worker to restore Python
            # signal handlers itself. Preserve the failure loudly rather than
            # pretending native propagation was restored.
            triggering = self._require_triggering_signal()
            logger.exception(
                "Unable to finalize signal handling on the main thread; terminating with signal exit status.",
            )
            os._exit(128 + int(triggering))

    def _run_registration(  # noqa: C901, PLR0912
        self,
        registration: _Registration,
        remaining_grace: float,
    ) -> None:
        timeout = remaining_grace
        if registration.timeout is not None:
            timeout = min(timeout, registration.timeout)

        started = time.monotonic()
        try:
            if registration.owner_loop is None:
                result = registration.callback()
                if inspect.isawaitable(result):
                    if inspect.iscoroutine(result):
                        result.close()
                    msg = f"cleanup {registration.name!r} returned an awaitable without an owner_loop"
                    raise SignalCoordinatorError(msg)
            else:
                loop = registration.owner_loop
                if loop.is_closed() or not loop.is_running():
                    msg = f"cleanup {registration.name!r} owner loop is unavailable"
                    raise SignalCoordinatorError(msg)

                future = asyncio.run_coroutine_threadsafe(
                    self._invoke_on_owner_loop(registration),
                    loop,
                )
                with self._lock:
                    self._active_async_future = future

                # A second signal can arrive after scheduling but before the
                # future is published. Recheck the escalation latch immediately.
                if self._abort.is_set():
                    future.cancel()
                    return

                try:
                    future.result(timeout=timeout)
                except TimeoutError:
                    future.cancel()
                    logger.warning(
                        "Cleanup {} exceeded its {:.3f}s timeout.",
                        registration.name,
                        timeout,
                    )
                finally:
                    with self._lock:
                        if self._active_async_future is future:
                            self._active_async_future = None
        except BaseException:  # noqa: BLE001
            logger.exception("Cleanup {} failed.", registration.name)
        finally:
            elapsed = time.monotonic() - started
            if registration.owner_loop is None and elapsed > timeout:
                logger.warning(
                    "Synchronous cleanup {} returned after {:.3f}s "
                    "(limit {:.3f}s); synchronous callbacks cannot be pre-empted.",
                    registration.name,
                    elapsed,
                    timeout,
                )

    @staticmethod
    async def _invoke_on_owner_loop(registration: _Registration) -> None:
        result = registration.callback()

        if inspect.isawaitable(result):
            await result
        elif result is not None:
            logger.debug(
                "Cleanup {} returned non-awaitable value {!r}; ignoring it.",
                registration.name,
                result,
            )

    def _finalize_on_main_thread(self) -> None:
        """Restore prior handlers, then arrange native redelivery outside ctypes."""
        self._assert_main_thread()
        if self._phase is not CoordinatorPhase.FINALIZING:
            return
        triggering = self._require_triggering_signal()
        self._detach_and_restore_on_main()

        # Do not redeliver from inside the ctypes pending-call callback: a prior
        # Python handler may raise (for example KeyboardInterrupt), and ctypes
        # callback boundaries suppress normal exception propagation. A helper
        # thread redelivers after this callback has returned to the interpreter.
        threading.Thread(
            target=self._redeliver_after_pending_call,
            args=(triggering,),
            name="signal-coordinator-redelivery",
            daemon=True,
        ).start()

    def _propagate_from_main(self, signum: signal.Signals) -> None:
        """Immediately restore handlers and redeliver from a real signal path."""
        self._assert_main_thread()
        self._detach_and_restore_on_main()
        signal.raise_signal(signum)

    def _detach_and_restore_on_main(self) -> None:
        """Make the coordinator terminal and restore handlers on the main thread."""
        self._assert_main_thread()
        self._phase = CoordinatorPhase.FINALIZING
        self._registrations = {}
        self._registration_snapshot = ()
        self._frozen_identifiers = frozenset()
        self._restore_handlers()
        self._phase = CoordinatorPhase.UNINSTALLED

    @staticmethod
    def _redeliver_after_pending_call(signum: signal.Signals) -> None:
        """Redeliver after the pending-call callback has left the ctypes boundary."""
        time.sleep(0.1)
        signal.raise_signal(signum)

    def _restore_handlers(self) -> None:
        """Restore every prior managed handler; main-thread-only."""
        self._assert_main_thread()
        for managed_signal, prior_handler in self._prior_handlers.items():
            signal.signal(managed_signal, prior_handler)
        self._prior_handlers.clear()

    # ------------------------------------------------------------------
    # properties and validation
    # ------------------------------------------------------------------

    @property
    def phase(self) -> CoordinatorPhase:
        """Return the current lifecycle phase."""
        return self._phase

    @property
    def installed(self) -> bool:
        """Whether coordinator handlers are physically installed."""
        return self._phase in (
            CoordinatorPhase.ACTIVE,
            CoordinatorPhase.DRAINING,
            CoordinatorPhase.FINALIZING,
        )

    @property
    def guarantees_cleanup(self) -> bool:
        """Whether new registrations still receive the cleanup guarantee."""
        return self._phase is CoordinatorPhase.ACTIVE

    @property
    def shutting_down(self) -> bool:
        """Whether graceful shutdown or finalization is active."""
        return self._phase in (
            CoordinatorPhase.DRAINING,
            CoordinatorPhase.FINALIZING,
        )

    @property
    def callback_count(self) -> int:
        """Return the number of active registrations."""
        with self._lock:
            return len(self._registrations)

    @property
    def signal_count(self) -> int:
        """Return the number of managed signals observed."""
        return self._signal_count

    @property
    def triggering_signal(self) -> signal.Signals | None:
        """Return the first signal that initiated graceful shutdown."""
        return self._triggering_signal

    @property
    def deadline(self) -> float | None:
        """Return the absolute deadline on :func:`time.monotonic`'s clock."""
        return self._deadline

    def _remaining_grace(self) -> float:
        deadline = self._deadline
        if deadline is None:
            return 0.0
        return max(0.0, deadline - time.monotonic())

    def _require_triggering_signal(self) -> signal.Signals:
        triggering = self._triggering_signal
        if triggering is None:
            msg = "no triggering signal has been recorded"
            raise SignalCoordinatorError(msg)
        return triggering

    def _validate_token(self, token: RegistrationToken) -> None:
        if not isinstance(token, RegistrationToken):
            msg = "token must be a RegistrationToken"
            raise TypeError(msg)
        if token._coordinator_ref() is not self:  # noqa: SLF001
            msg = "registration token belongs to another coordinator"
            raise ValueError(msg)

    @staticmethod
    def _assert_main_thread() -> None:
        if threading.current_thread() is not threading.main_thread():
            msg = "SignalCoordinator installation and handler restoration must run on the main thread"
            raise SignalCoordinatorError(msg)


_process_coordinator = SignalCoordinator()
_process_cancellation_token = CancellationToken()


def get_coordinator() -> SignalCoordinator:
    """Return the process-wide coordinator instance."""
    return _process_coordinator


def get_process_cancel_token() -> CancellationToken:
    """Return the process-wide cancellation token instance."""
    return _process_cancellation_token
