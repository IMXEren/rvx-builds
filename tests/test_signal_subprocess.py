"""Real signal propagation tests with explicit IPC readiness gates."""

# ruff: noqa: D103, S101, C901

from __future__ import annotations

import multiprocessing
import os
import signal
import threading
import time
from typing import Any

import pytest

import src.signals as process_signals

_GATE_TIMEOUT = 10.0


def _child_main(connection: Any, prior_kind: str, *, second_signal_case: bool) -> None:
    """Child subprocess: install coordinator, register callback, wait for signal."""
    coordinator = process_signals.SignalCoordinator()

    def prior_handler(signum: int, _frame: object) -> None:
        connection.send(("prior-called", signum))

    prior: Any = {
        "default": signal.SIG_DFL,
        "ignore": signal.SIG_IGN,
        "callable": prior_handler,
    }[prior_kind]
    signal.signal(signal.SIGINT, prior)
    signal.signal(signal.SIGTERM, prior)
    coordinator.install()

    if second_signal_case:
        # Blocking callback keeps drain active so a second signal
        # arrives during the draining phase (exercising the idempotent path).
        blocker = threading.Event()

        def blocking_callback() -> None:
            connection.send(("callback-fired", None))
            blocker.wait(timeout=1.0)

        coordinator.register(blocking_callback)
        connection.send(("handler-ready", os.getpid()))

        # Wait for first signal (signal_count advances from 0)
        deadline = time.monotonic() + _GATE_TIMEOUT
        while coordinator.signal_count == 0:
            if time.monotonic() >= deadline:
                os._exit(71)
            time.sleep(0.005)

        # Wait for coordinator to fully finish after both signals
        deadline = time.monotonic() + _GATE_TIMEOUT
        while coordinator.installed:
            if time.monotonic() >= deadline:
                os._exit(72)
            time.sleep(0.005)

        connection.send(("cleaned-up", None))

    else:
        callback_done = threading.Event()

        def sync_callback() -> None:
            connection.send(("cleanup-drained", None))
            callback_done.set()

        coordinator.register(sync_callback)
        connection.send(("handler-ready", os.getpid()))

        # Wait for signal (signal_count advances from 0)
        deadline = time.monotonic() + _GATE_TIMEOUT
        while coordinator.signal_count == 0:
            if time.monotonic() >= deadline:
                os._exit(71)
            time.sleep(0.005)

        if not callback_done.wait(_GATE_TIMEOUT):
            os._exit(72)

        # Wait for coordinator to uninstall completely
        deadline = time.monotonic() + _GATE_TIMEOUT
        while coordinator.installed:
            if time.monotonic() >= deadline:
                os._exit(73)
            time.sleep(0.005)

        # Give the redelivery thread time to fire the restored prior
        # handler before closing the IPC pipe.
        time.sleep(0.3)

    connection.close()


def _start_child(prior_kind: str, *, second_signal_case: bool = False) -> tuple[Any, Any]:
    context = multiprocessing.get_context("spawn")
    parent, child = context.Pipe(duplex=True)
    process = context.Process(
        target=_child_main,
        args=(child, prior_kind),
        kwargs={"second_signal_case": second_signal_case},
    )
    process.start()
    child.close()
    return process, parent


def _expect(connection: Any, name: str) -> object:
    assert connection.poll(_GATE_TIMEOUT), f"timed out waiting for {name}"
    actual_name, payload = connection.recv()
    assert actual_name == name, f"expected {name!r}, got {actual_name!r}"
    return payload


def _force_reap(process: Any) -> None:
    if process.is_alive():
        process.kill()
    process.join(timeout=5)
    process.close()


@pytest.fixture
def children() -> Any:
    processes: list[Any] = []
    try:
        yield processes
    finally:
        for process in processes:
            _force_reap(process)


def test_sig_dfl_terminates_after_callback_processing(children: list[Any]) -> None:
    """SIG_DFL: callback fires, then raise_signal terminates the child process."""
    process, connection = _start_child("default")
    children.append(process)
    pid = _expect(connection, "handler-ready")
    assert isinstance(pid, int)

    os.kill(pid, signal.SIGINT)
    _expect(connection, "cleanup-drained")

    process.join(timeout=_GATE_TIMEOUT)
    connection.close()


def test_sig_ign_survives_and_reinstalls(children: list[Any]) -> None:
    """SIG_IGN: coordinator processes callbacks, process survives."""
    process, connection = _start_child("ignore")
    children.append(process)
    pid = _expect(connection, "handler-ready")
    assert isinstance(pid, int)

    os.kill(pid, signal.SIGINT)
    _expect(connection, "cleanup-drained")

    process.join(timeout=_GATE_TIMEOUT)
    assert process.exitcode == 0
    connection.close()


def test_callable_prior_runs_after_signal(children: list[Any]) -> None:
    """Callable prior handler runs after coordinator drains callbacks."""
    process, connection = _start_child("callable")
    children.append(process)
    pid = _expect(connection, "handler-ready")
    assert isinstance(pid, int)

    os.kill(pid, signal.SIGTERM)
    _expect(connection, "cleanup-drained")
    _expect(connection, "prior-called")

    process.join(timeout=_GATE_TIMEOUT)
    assert process.exitcode == 0
    connection.close()


def test_second_signal_during_active_event_is_idempotent(children: list[Any]) -> None:
    """Second signal during drain is idempotent — process survives."""
    process, connection = _start_child("ignore", second_signal_case=True)
    children.append(process)
    pid = _expect(connection, "handler-ready")
    assert isinstance(pid, int)

    os.kill(pid, signal.SIGINT)
    _expect(connection, "callback-fired")
    os.kill(pid, signal.SIGINT)
    _expect(connection, "cleaned-up")

    process.join(timeout=_GATE_TIMEOUT)
    assert process.exitcode == 0
    connection.close()
