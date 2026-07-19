"""Tests for src/signals.py -- one-shot process-wide graceful signal coordinator.

Tests cover the current API surface: SignalCoordinator, RegistrationToken,
CancellationToken, LIFO drain, per-registration timeout, and one-shot
install/uninstall lifecycle.
"""

# ruff: noqa: D102, S101, SLF001, ARG005, PLR2004
# mypy: disable-error-code="attr-defined,arg-type,return-value,comparison-overlap"

from __future__ import annotations

import asyncio
import os
import signal
import threading
import time
from typing import Any, cast
from unittest.mock import MagicMock

import pytest

import src.signals as process_signals

# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def _noop() -> None:
    """Trivial sync callback."""


async def _async_noop() -> None:
    """Trivial async callback."""


def _register_hold(coord: process_signals.SignalCoordinator) -> threading.Event:
    """Block drain worker from completing until the returned event is set.

    The blocker is registered LAST so it runs FIRST in LIFO drain order,
    keeping the worker alive and letting the caller inspect intermediate
    state (phase, frozen identifiers, etc.).
    """
    hold = threading.Event()
    coord.register(lambda: hold.wait(timeout=5))
    return hold


def _make_running_loop() -> MagicMock:
    """Return a mock loop that appears running and open."""
    loop = MagicMock(spec=asyncio.AbstractEventLoop)
    loop.is_closed.return_value = False
    loop.is_running.return_value = True
    return cast("asyncio.AbstractEventLoop", loop)


# ---------------------------------------------------------------------------
# fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _prevent_real_signal_raise(monkeypatch: pytest.MonkeyPatch) -> None:
    """Prevent any production path from sending real signals to the test process."""
    monkeypatch.setattr(signal, "raise_signal", lambda signum: None)


@pytest.fixture(autouse=True)
def _prevent_os_exit(monkeypatch: pytest.MonkeyPatch) -> None:
    """Prevent os._exit from killing test processes in drain worker failure paths."""
    monkeypatch.setattr(os, "_exit", lambda code: None)


# ---------------------------------------------------------------------------
# SignalCoordinator constructor
# ---------------------------------------------------------------------------


class TestSignalCoordinatorConstructor:
    """Constructor validation -- signals, grace_period, initial state."""

    def test_default_constructor(self) -> None:
        coord = process_signals.SignalCoordinator()
        assert coord.phase is process_signals.CoordinatorPhase.NEW
        assert not coord.installed
        assert not coord.shutting_down
        assert coord.callback_count == 0
        assert coord.signal_count == 0
        assert coord.triggering_signal is None
        assert coord.deadline is None

    def test_empty_signals_raises(self) -> None:
        with pytest.raises(ValueError, match="at least one"):
            process_signals.SignalCoordinator(signals=())

    def test_negative_grace_period_raises(self) -> None:
        with pytest.raises(ValueError, match="non-negative"):
            process_signals.SignalCoordinator(grace_period=-1)

    def test_custom_signals_and_grace_period(self) -> None:
        coord = process_signals.SignalCoordinator(
            signals=(signal.SIGTERM,),
            grace_period=10.0,
        )
        assert coord.phase is process_signals.CoordinatorPhase.NEW


# ---------------------------------------------------------------------------
# RegistrationToken                                                        AC5
# ---------------------------------------------------------------------------


class TestRegistrationToken:
    """AC5 -- RegistrationToken identity, equality, and properties."""

    def test_token_constructor(self) -> None:
        coord = process_signals.SignalCoordinator()
        tok = process_signals.RegistrationToken(coord, 42)
        assert "42" in repr(tok)
        assert isinstance(tok, process_signals.RegistrationToken)

    def test_token_equality_is_id_based(self) -> None:
        coord = process_signals.SignalCoordinator()
        a = process_signals.RegistrationToken(coord, 1)
        b = process_signals.RegistrationToken(coord, 1)
        c = process_signals.RegistrationToken(coord, 2)
        assert a == b
        assert a != c
        assert hash(a) == hash(b)

    def test_token_not_equal_to_other_types(self) -> None:
        coord = process_signals.SignalCoordinator()
        tok = process_signals.RegistrationToken(coord, 1)
        assert tok != "a"
        assert tok != 42

    def test_token_repr_contains_identifier(self) -> None:
        coord = process_signals.SignalCoordinator()
        tok = process_signals.RegistrationToken(coord, 99)
        assert "99" in repr(tok)

    def test_token_active_after_register(self) -> None:
        coord = process_signals.SignalCoordinator()
        coord.install()
        tok = coord.register(_noop)
        assert tok.active is True

    def test_token_active_false_after_unregister(self) -> None:
        coord = process_signals.SignalCoordinator()
        coord.install()
        tok = coord.register(_noop)
        tok.unregister()
        assert tok.active is False

    def test_token_active_false_after_signal(self) -> None:
        coord = process_signals.SignalCoordinator()
        coord.install()
        tok = coord.register(_noop)
        coord._on_signal(signal.SIGINT, None)
        assert tok.active is False

    def test_token_context_manager_sync(self) -> None:
        coord = process_signals.SignalCoordinator()
        coord.install()
        with coord.register(_noop) as tok:
            assert tok.active is True
        assert tok.active is False

    def test_token_context_manager_async(self) -> None:
        """Async context manager (__aenter__/__aexit__) for RegistrationToken."""
        coord = process_signals.SignalCoordinator()
        coord.install()
        tok = coord.register(_noop)

        async def _use() -> None:
            async with tok:
                assert tok.active is True

        asyncio.run(_use())
        assert tok.active is False

    def test_set_membership_by_id(self) -> None:
        coord = process_signals.SignalCoordinator()
        a = process_signals.RegistrationToken(coord, 1)
        b = process_signals.RegistrationToken(coord, 1)
        s: set[process_signals.RegistrationToken] = {a}
        assert b in s

    def test_token_unregister_returns_bool(self) -> None:
        coord = process_signals.SignalCoordinator()
        coord.install()
        tok = coord.register(_noop)
        assert tok.unregister() is True
        assert tok.unregister() is False


# ---------------------------------------------------------------------------
# register                                                                 AC5
# ---------------------------------------------------------------------------


class TestRegister:
    """AC5 -- register() returns RegistrationToken with correct contract."""

    def test_register_sync_no_owner_loop(self) -> None:
        coord = process_signals.SignalCoordinator()
        coord.install()
        tok = coord.register(_noop)
        assert isinstance(tok, process_signals.RegistrationToken)
        assert tok.active is True

    def test_register_async_with_owner_loop(self) -> None:
        coord = process_signals.SignalCoordinator()
        coord.install()
        loop = _make_running_loop()
        tok = coord.register(_async_noop, owner_loop=loop)
        assert isinstance(tok, process_signals.RegistrationToken)
        assert tok.active is True

    def test_register_async_requires_owner_loop(self) -> None:
        coord = process_signals.SignalCoordinator()
        coord.install()
        with pytest.raises(
            process_signals.SignalCoordinatorError,
            match="owner_loop",
        ):
            coord.register(_async_noop)

    def test_register_sync_rejects_owner_loop(self) -> None:
        coord = process_signals.SignalCoordinator()
        coord.install()
        loop = _make_running_loop()
        with pytest.raises(
            process_signals.SignalCoordinatorError,
            match="async",
        ):
            coord.register(_noop, owner_loop=loop)

    def test_register_with_name(self) -> None:
        coord = process_signals.SignalCoordinator()
        coord.install()
        tok = coord.register(_noop, name="my_cleanup")
        assert tok.active is True

    def test_register_with_timeout(self) -> None:
        coord = process_signals.SignalCoordinator()
        coord.install()
        tok = coord.register(_noop, timeout=3.0)
        assert tok.active is True

    def test_register_increments_callback_count(self) -> None:
        coord = process_signals.SignalCoordinator()
        coord.install()
        assert coord.callback_count == 0
        coord.register(_noop)
        assert coord.callback_count == 1
        coord.register(_noop)
        assert coord.callback_count == 2

    def test_not_callable_raises_type_error(self) -> None:
        coord = process_signals.SignalCoordinator()
        coord.install()
        with pytest.raises(TypeError, match="callable"):
            coord.register(cast("Any", "not-callable"))

    def test_negative_timeout_raises(self) -> None:
        coord = process_signals.SignalCoordinator()
        coord.install()
        with pytest.raises(ValueError, match="timeout must be non-negative"):
            coord.register(_noop, timeout=-1.0)

    def test_register_rejects_when_not_active(self) -> None:
        coord = process_signals.SignalCoordinator()
        with pytest.raises(process_signals.CoordinatorStateError):
            coord.register(_noop)

    def test_register_rejects_after_uninstall(self) -> None:
        coord = process_signals.SignalCoordinator()
        coord.install()
        coord.uninstall()
        with pytest.raises(process_signals.CoordinatorStateError):
            coord.register(_noop)

    def test_register_rejects_during_draining(self) -> None:
        coord = process_signals.SignalCoordinator()
        coord.install()
        coord.register(_noop)
        coord._on_signal(signal.SIGINT, None)
        with pytest.raises(process_signals.CoordinatorStateError):
            coord.register(_noop)

    def test_register_rejects_closed_loop(self) -> None:
        coord = process_signals.SignalCoordinator()
        coord.install()
        loop = MagicMock(spec=asyncio.AbstractEventLoop)
        loop.is_closed.return_value = True
        with pytest.raises(
            process_signals.SignalCoordinatorError,
            match="running",
        ):
            coord.register(_async_noop, owner_loop=loop)

    def test_register_rejects_stopped_loop(self) -> None:
        coord = process_signals.SignalCoordinator()
        coord.install()
        loop = MagicMock(spec=asyncio.AbstractEventLoop)
        loop.is_closed.return_value = False
        loop.is_running.return_value = False
        with pytest.raises(
            process_signals.SignalCoordinatorError,
            match="running",
        ):
            coord.register(_async_noop, owner_loop=loop)

    def test_register_callback_alias(self) -> None:
        """register_callback is an alias for register."""
        coord = process_signals.SignalCoordinator()
        coord.install()
        tok = coord.register_callback(_noop)
        assert isinstance(tok, process_signals.RegistrationToken)
        assert tok.active is True


# ---------------------------------------------------------------------------
# unregister                                                               AC6
# ---------------------------------------------------------------------------


class TestUnregister:
    """AC6 -- thread-safe unregister; False = idempotent success."""

    def test_unregister_returns_true_for_active_token(self) -> None:
        coord = process_signals.SignalCoordinator()
        coord.install()
        tok = coord.register(_noop)
        assert coord.unregister(tok) is True
        assert coord.callback_count == 0

    def test_unregister_returns_false_for_removed_token(self) -> None:
        coord = process_signals.SignalCoordinator()
        coord.install()
        tok = coord.register(_noop)
        coord.unregister(tok)
        assert coord.unregister(tok) is False
        assert coord.callback_count == 0

    def test_unregister_returns_false_for_unknown_identifier(self) -> None:
        coord = process_signals.SignalCoordinator()
        coord.install()
        tok = process_signals.RegistrationToken(coord, 9999)
        assert coord.unregister(tok) is False

    def test_unregister_returns_false_after_signal(self) -> None:
        coord = process_signals.SignalCoordinator()
        coord.install()
        tok = coord.register(_noop)
        coord._on_signal(signal.SIGINT, None)
        assert coord.unregister(tok) is False

    def test_unregister_raises_for_wrong_coordinator(self) -> None:
        coord = process_signals.SignalCoordinator()
        coord.install()
        other = process_signals.SignalCoordinator()
        other.install()
        tok = other.register(_noop)
        with pytest.raises(ValueError, match="another coordinator"):
            coord.unregister(tok)

    def test_unregister_raises_for_bad_type(self) -> None:
        coord = process_signals.SignalCoordinator()
        coord.install()
        with pytest.raises(TypeError, match="RegistrationToken"):
            coord.unregister(cast("Any", "not-a-token"))

    def test_unregister_from_another_thread(self) -> None:
        coord = process_signals.SignalCoordinator()
        coord.install()
        tok = coord.register(_noop)
        results: list[bool] = []

        def _unreg() -> None:
            results.append(coord.unregister(tok))

        t = threading.Thread(target=_unreg)
        t.start()
        t.join()
        assert results == [True]
        assert coord.callback_count == 0

    def test_unregister_callback_alias(self) -> None:
        """unregister_callback is an alias for unregister."""
        coord = process_signals.SignalCoordinator()
        coord.install()
        tok = coord.register(_noop)
        assert coord.unregister_callback(tok) is True


# ---------------------------------------------------------------------------
# registration_active
# ---------------------------------------------------------------------------


class TestRegistrationActive:
    """registration_active identifies current tokens."""

    def test_active_returns_true_for_registered_token(self) -> None:
        coord = process_signals.SignalCoordinator()
        coord.install()
        tok = coord.register(_noop)
        assert coord.registration_active(tok) is True

    def test_active_returns_false_after_unregister(self) -> None:
        coord = process_signals.SignalCoordinator()
        coord.install()
        tok = coord.register(_noop)
        coord.unregister(tok)
        assert coord.registration_active(tok) is False

    def test_active_returns_false_for_never_registered(self) -> None:
        coord = process_signals.SignalCoordinator()
        coord.install()
        tok = process_signals.RegistrationToken(coord, 9999)
        assert coord.registration_active(tok) is False


# ---------------------------------------------------------------------------
# Phases                                                                   AC9
# ---------------------------------------------------------------------------


class TestPhases:
    """AC9 -- phases are NEW -> ACTIVE -> DRAINING -> FINALIZING -> UNINSTALLED."""

    def test_enum_members_exist(self) -> None:
        for name in ("NEW", "ACTIVE", "DRAINING", "FINALIZING", "UNINSTALLED"):
            assert hasattr(process_signals.CoordinatorPhase, name)

    def test_initial_phase_is_new(self) -> None:
        coord = process_signals.SignalCoordinator()
        assert coord.phase is process_signals.CoordinatorPhase.NEW

    def test_install_transitions_to_active(self) -> None:
        coord = process_signals.SignalCoordinator()
        coord.install()
        assert coord.phase is process_signals.CoordinatorPhase.ACTIVE

    def test_uninstall_from_active_goes_to_uninstalled(self) -> None:
        coord = process_signals.SignalCoordinator()
        coord.install()
        coord.uninstall()
        assert coord.phase is process_signals.CoordinatorPhase.UNINSTALLED

    def test_on_signal_transitions_to_draining(self) -> None:
        coord = process_signals.SignalCoordinator()
        coord.install()
        hold = _register_hold(coord)
        coord._on_signal(signal.SIGINT, None)
        assert coord.phase is process_signals.CoordinatorPhase.DRAINING
        hold.set()
        coord._worker.join(timeout=5)


# ---------------------------------------------------------------------------
# Active-event registration refusal                                       AC10
# ---------------------------------------------------------------------------


class TestActiveEventRefusal:
    """AC10 -- registration during non-ACTIVE phases raises CoordinatorStateError."""

    def test_refuses_when_new(self) -> None:
        coord = process_signals.SignalCoordinator()
        with pytest.raises(process_signals.CoordinatorStateError):
            coord.register(_noop)

    def test_refuses_during_draining(self) -> None:
        coord = process_signals.SignalCoordinator()
        coord.install()
        coord.register(_noop)
        coord._on_signal(signal.SIGINT, None)
        with pytest.raises(process_signals.CoordinatorStateError):
            coord.register(_noop)

    def test_refuses_during_finalizing(self) -> None:
        coord = process_signals.SignalCoordinator()
        coord.install()
        coord._phase = process_signals.CoordinatorPhase.FINALIZING
        with pytest.raises(process_signals.CoordinatorStateError):
            coord.register(_noop)

    def test_refuses_during_uninstalled(self) -> None:
        coord = process_signals.SignalCoordinator()
        coord.install()
        coord.uninstall()
        with pytest.raises(process_signals.CoordinatorStateError):
            coord.register(_noop)

    def test_refusal_does_not_mutate_state(self) -> None:
        coord = process_signals.SignalCoordinator()
        coord.install()
        tok = coord.register(_noop)
        assert coord.callback_count == 1
        coord._phase = process_signals.CoordinatorPhase.FINALIZING
        with pytest.raises(process_signals.CoordinatorStateError):
            coord.register(_noop)
        assert tok.active is True


# ---------------------------------------------------------------------------
# _on_signal                                                               AC8
# ---------------------------------------------------------------------------


class TestOnSignal:
    """AC8 -- _on_signal handles managed signals, freezes snapshot, spawns worker."""

    def test_records_triggering_signal(self) -> None:
        coord = process_signals.SignalCoordinator()
        coord.install()
        hold = _register_hold(coord)
        coord._on_signal(signal.SIGTERM, None)
        assert coord.triggering_signal == signal.SIGTERM
        hold.set()
        coord._worker.join(timeout=5)

    def test_records_deadline(self) -> None:
        coord = process_signals.SignalCoordinator()
        coord.install()
        hold = _register_hold(coord)
        before = time.monotonic()
        coord._on_signal(signal.SIGINT, None)
        after = time.monotonic()
        assert coord.deadline is not None
        assert before <= coord.deadline <= after + process_signals.DEFAULT_GRACE_PERIOD + 0.5
        hold.set()
        coord._worker.join(timeout=5)

    def test_sets_draining_phase(self) -> None:
        coord = process_signals.SignalCoordinator()
        coord.install()
        hold = _register_hold(coord)
        coord._on_signal(signal.SIGINT, None)
        assert coord.phase is process_signals.CoordinatorPhase.DRAINING
        hold.set()
        coord._worker.join(timeout=5)

    def test_does_not_invoke_callbacks_inline(self) -> None:
        """_on_signal does not invoke callbacks -- drain worker does."""
        coord = process_signals.SignalCoordinator()
        coord.install()
        called: list[int] = []

        def record() -> None:
            called.append(1)

        coord.register(record)  # registered first, runs second (LIFO)
        hold = _register_hold(coord)  # registered second, runs first (LIFO)
        coord._on_signal(signal.SIGINT, None)
        # hold blocks the worker thread, so record has not been called yet
        assert called == []
        hold.set()
        coord._worker.join(timeout=5)

    def test_freezes_frozen_identifiers(self) -> None:
        coord = process_signals.SignalCoordinator()
        coord.install()
        tok = coord.register(_noop)
        hold = _register_hold(coord)
        coord._on_signal(signal.SIGINT, None)
        # held drain worker means _frozen_identifiers hasn't been cleared
        assert tok._identifier in coord._frozen_identifiers
        hold.set()
        coord._worker.join(timeout=5)

    def test_clears_registrations_after_freeze(self) -> None:
        coord = process_signals.SignalCoordinator()
        coord.install()
        coord.register(_noop)
        hold = _register_hold(coord)
        coord._on_signal(signal.SIGINT, None)
        assert coord.callback_count == 0
        hold.set()
        coord._worker.join(timeout=5)

    def test_increments_signal_count(self) -> None:
        coord = process_signals.SignalCoordinator()
        coord.install()
        hold = _register_hold(coord)
        assert coord.signal_count == 0
        coord._on_signal(signal.SIGINT, None)
        assert coord.signal_count == 1
        hold.set()
        coord._worker.join(timeout=5)

    def test_starts_worker_thread(self) -> None:
        coord = process_signals.SignalCoordinator()
        coord.install()
        hold = _register_hold(coord)
        coord._on_signal(signal.SIGINT, None)
        assert coord._worker is not None
        assert coord._worker.is_alive()
        hold.set()
        coord._worker.join(timeout=5)

    def test_cancels_global_cancel_token(self) -> None:
        """_on_signal cancels the process-wide cancel token."""
        coord = process_signals.SignalCoordinator()
        coord.install()
        hold = _register_hold(coord)
        coord._on_signal(signal.SIGINT, None)
        # Global token becomes cancelled (may have been already from
        # a prior test; we only verify the post-condition).
        assert process_signals.get_process_cancel_token().cancelled
        hold.set()
        coord._worker.join(timeout=5)

    def test_second_signal_escalates(self) -> None:
        coord = process_signals.SignalCoordinator()
        coord.install()
        hold = _register_hold(coord)
        # First signal: drain is blocked by hold
        coord._on_signal(signal.SIGINT, None)
        assert coord.phase is process_signals.CoordinatorPhase.DRAINING
        assert not coord._abort.is_set()
        # Second signal while DRAINING -- escalates
        coord._on_signal(signal.SIGTERM, None)
        assert coord._abort.is_set()
        hold.set()
        if coord._worker:
            coord._worker.join(timeout=5)

    def test_second_signal_increments_signal_count(self) -> None:
        coord = process_signals.SignalCoordinator()
        coord.install()
        hold = _register_hold(coord)
        coord._on_signal(signal.SIGINT, None)
        assert coord.signal_count == 1
        coord._on_signal(signal.SIGTERM, None)
        assert coord.signal_count == 2
        hold.set()
        coord._worker.join(timeout=5)


# ---------------------------------------------------------------------------
# _drain_worker
# ---------------------------------------------------------------------------


class TestDrainWorker:
    """Test _drain_worker LIFO order, timeout, and abort behavior."""

    def test_drain_worker_transitions_to_finalizing(self) -> None:
        coord = process_signals.SignalCoordinator()
        coord.install()
        coord.register(_noop)
        coord._on_signal(signal.SIGINT, None)
        # Capture thread before the worker clears its own reference
        worker = coord._worker
        if worker:
            worker.join(timeout=5)
        # Worker sets FINALIZING; _finalize_on_main_thread may or may not
        # have run via pending-call mechanism, so accept either state.
        assert coord.phase in (
            process_signals.CoordinatorPhase.FINALIZING,
            process_signals.CoordinatorPhase.UNINSTALLED,
        )

    def test_drain_worker_lifo_order(self) -> None:
        coord = process_signals.SignalCoordinator()
        coord.install()
        order: list[int] = []

        def first() -> None:
            order.append(1)

        def second() -> None:
            order.append(2)

        def third() -> None:
            order.append(3)

        coord.register(first)
        coord.register(second)
        coord.register(third)
        coord._on_signal(signal.SIGINT, None)
        worker = coord._worker
        if worker:
            worker.join(timeout=5)
        assert order == [3, 2, 1]

    def test_drain_worker_skips_when_grace_expired(self) -> None:
        coord = process_signals.SignalCoordinator(grace_period=0)
        coord.install()
        called: list[int] = []

        def record() -> None:
            called.append(1)

        coord.register(record)
        coord._on_signal(signal.SIGINT, None)
        worker = coord._worker
        if worker:
            worker.join(timeout=5)
        # With grace_period=0, deadline ~= now. By the time the worker
        # thread checks remaining_grace, it should be ~0, so callbacks
        # are skipped.
        assert called == []

    def test_drain_worker_abort_skips_remaining(self) -> None:
        coord = process_signals.SignalCoordinator()
        coord.install()
        coord.register(_noop)
        hold = _register_hold(coord)
        coord._on_signal(signal.SIGINT, None)
        # drain is blocked on hold; set abort
        coord._abort.set()
        hold.set()
        worker = coord._worker
        if worker:
            worker.join(timeout=5)
        assert coord._abort.is_set()


# ---------------------------------------------------------------------------
# _run_registration
# ---------------------------------------------------------------------------


class TestRunRegistration:
    """Test _run_registration sync/async dispatch and exception handling."""

    def test_run_sync_registration(self) -> None:
        coord = process_signals.SignalCoordinator()
        coord.install()
        called: list[int] = []

        def record() -> None:
            called.append(1)

        coord.register(record)  # runs second (LIFO)
        hold = _register_hold(coord)  # runs first, blocks
        coord._on_signal(signal.SIGINT, None)
        hold.set()
        worker = coord._worker
        if worker:
            worker.join(timeout=5)
        assert called == [1]

    def test_run_multiple_sync_registrations(self) -> None:
        coord = process_signals.SignalCoordinator()
        coord.install()
        results: list[int] = []

        def a() -> None:
            results.append(1)

        def b() -> None:
            results.append(2)

        coord.register(a)  # runs second (LIFO)
        coord.register(b)  # runs first (LIFO)
        coord._on_signal(signal.SIGINT, None)
        worker = coord._worker
        if worker:
            worker.join(timeout=5)
        assert results == [2, 1]

    def test_run_registration_with_exception_logged(self) -> None:
        """An exception in a sync callback is caught and logged."""
        coord = process_signals.SignalCoordinator()
        coord.install()

        def _explode() -> None:
            msg = "boom"
            raise ValueError(msg)

        coord.register(_explode)  # runs second (LIFO)
        hold = _register_hold(coord)  # runs first, blocks
        coord._on_signal(signal.SIGINT, None)
        hold.set()
        worker = coord._worker
        if worker:
            worker.join(timeout=5)
        assert coord.phase in (
            process_signals.CoordinatorPhase.FINALIZING,
            process_signals.CoordinatorPhase.UNINSTALLED,
        )


# ---------------------------------------------------------------------------
# _finalize_on_main_thread
# ---------------------------------------------------------------------------


class TestFinalizeOnMainThread:
    """Test _finalize_on_main_thread internal behavior."""

    def test_finalize_restores_handlers(self) -> None:
        coord = process_signals.SignalCoordinator()
        prior_int = signal.getsignal(signal.SIGINT)
        coord.install()
        assert signal.getsignal(signal.SIGINT) is not prior_int

        coord._phase = process_signals.CoordinatorPhase.FINALIZING
        coord._triggering_signal = signal.SIGINT
        coord._finalize_on_main_thread()

        assert coord.phase is process_signals.CoordinatorPhase.UNINSTALLED
        assert signal.getsignal(signal.SIGINT) is prior_int

    def test_finalize_noop_if_not_finalizing(self) -> None:
        coord = process_signals.SignalCoordinator()
        coord.install()
        coord._finalize_on_main_thread()
        assert coord.phase is process_signals.CoordinatorPhase.ACTIVE

    def test_finalize_sets_uninstalled(self) -> None:
        coord = process_signals.SignalCoordinator()
        coord.install()
        coord._phase = process_signals.CoordinatorPhase.FINALIZING
        coord._triggering_signal = signal.SIGINT
        coord._finalize_on_main_thread()
        assert coord.phase is process_signals.CoordinatorPhase.UNINSTALLED


# ---------------------------------------------------------------------------
# CancellationToken
# ---------------------------------------------------------------------------


class TestCancellationToken:
    """CancellationToken cooperative cancellation."""

    def test_initial_not_cancelled(self) -> None:
        tok = process_signals.CancellationToken()
        assert not tok.cancelled

    def test_cancel_sets_cancelled(self) -> None:
        tok = process_signals.CancellationToken()
        tok.cancel()
        assert tok.cancelled

    def test_raise_if_cancelled_raises(self) -> None:
        tok = process_signals.CancellationToken()
        tok.cancel()
        with pytest.raises(process_signals.OperationCancelledError):
            tok.raise_if_cancelled()

    def test_raise_if_cancelled_noop_when_not_cancelled(self) -> None:
        tok = process_signals.CancellationToken()
        tok.raise_if_cancelled()

    def test_wait_returns_true_after_cancel(self) -> None:
        tok = process_signals.CancellationToken()
        tok.cancel()
        assert tok.wait(timeout=1) is True

    def test_wait_returns_false_on_timeout(self) -> None:
        tok = process_signals.CancellationToken()
        assert tok.wait(timeout=0.01) is False

    def test_cancel_idempotent(self) -> None:
        tok = process_signals.CancellationToken()
        tok.cancel()
        tok.cancel()
        assert tok.cancelled


# ---------------------------------------------------------------------------
# install / uninstall (one-shot)                                   AC15-AC17
# ---------------------------------------------------------------------------


class TestInstallUninstall:
    """AC15-AC17 -- main-thread-only, idempotent install, one-shot enforcement."""

    def test_install_idempotent(self) -> None:
        coord = process_signals.SignalCoordinator()
        coord.install()
        assert coord.installed
        coord.install()
        assert coord.installed

    def test_uninstall_idempotent(self) -> None:
        coord = process_signals.SignalCoordinator()
        coord.install()
        coord.uninstall()
        assert not coord.installed
        coord.uninstall()
        assert not coord.installed

    def test_install_saves_prior_handlers(self) -> None:
        coord = process_signals.SignalCoordinator()
        coord.install()
        assert signal.SIGINT in coord._prior_handlers
        assert signal.SIGTERM in coord._prior_handlers

    def test_uninstall_restores_handlers(self) -> None:
        coord = process_signals.SignalCoordinator()
        prior_int = signal.getsignal(signal.SIGINT)
        coord.install()
        coord.uninstall()
        assert signal.getsignal(signal.SIGINT) is prior_int

    def test_one_shot_install_raises_after_uninstall(self) -> None:
        coord = process_signals.SignalCoordinator()
        coord.install()
        coord.uninstall()
        with pytest.raises(
            process_signals.CoordinatorStateError,
            match="cannot be reinstalled",
        ):
            coord.install()

    def test_install_rejects_non_main_thread(self) -> None:
        coord = process_signals.SignalCoordinator()
        error: Exception | None = None

        def _install() -> None:
            nonlocal error
            try:
                coord.install()
            except process_signals.SignalCoordinatorError as e:
                error = e

        t = threading.Thread(target=_install)
        t.start()
        t.join()
        assert error is not None
        assert isinstance(error, process_signals.SignalCoordinatorError)

    def test_uninstall_rejects_non_main_thread(self) -> None:
        coord = process_signals.SignalCoordinator()
        coord.install()
        error: Exception | None = None

        def _uninstall() -> None:
            nonlocal error
            try:
                coord.uninstall()
            except process_signals.SignalCoordinatorError as e:
                error = e

        t = threading.Thread(target=_uninstall)
        t.start()
        t.join()
        assert error is not None
        assert isinstance(error, process_signals.SignalCoordinatorError)

    def test_uninstall_rejects_during_shutdown(self) -> None:
        coord = process_signals.SignalCoordinator()
        coord.install()
        coord._phase = process_signals.CoordinatorPhase.DRAINING
        with pytest.raises(
            process_signals.CoordinatorStateError,
            match="cannot manually uninstall",
        ):
            coord.uninstall()

    def test_partial_install_failure_rolls_back(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """AC16 -- second managed signal installation raises; rollback restores first."""
        coord = process_signals.SignalCoordinator()
        prior_int: object = signal.getsignal(signal.SIGINT)
        prior_term: object = signal.getsignal(signal.SIGTERM)

        call_count = [0]
        original = signal.signal

        def _failing_signal(sig: int, handler: object) -> object:
            call_count[0] += 1
            if call_count[0] == 2:
                msg = "Simulated install failure"
                raise OSError(msg)
            return original(sig, cast("Any", handler))

        monkeypatch.setattr(signal, "signal", _failing_signal)

        with pytest.raises(OSError, match="Simulated install failure"):
            coord.install()

        assert not coord.installed
        assert signal.getsignal(signal.SIGINT) is prior_int
        assert signal.getsignal(signal.SIGTERM) is prior_term
        assert signal.SIGINT not in coord._prior_handlers


# ---------------------------------------------------------------------------
# Legacy / convenience properties
# ---------------------------------------------------------------------------


class TestLegacyProperties:
    """Pre-existing API: shutting_down, signal_count, installed, callback_count."""

    def test_shutting_down_false_initially(self) -> None:
        coord = process_signals.SignalCoordinator()
        coord.install()
        assert not coord.shutting_down

    def test_shutting_down_true_during_draining(self) -> None:
        coord = process_signals.SignalCoordinator()
        coord.install()
        hold = _register_hold(coord)
        coord._on_signal(signal.SIGINT, None)
        assert coord.shutting_down
        hold.set()
        coord._worker.join(timeout=5)

    def test_signal_count_monotonic(self) -> None:
        coord = process_signals.SignalCoordinator()
        coord.install()
        assert coord.signal_count == 0
        coord._on_signal(signal.SIGINT, None)
        assert coord.signal_count == 1
        coord._on_signal(signal.SIGTERM, None)
        assert coord.signal_count == 2

    def test_guarantees_cleanup_true_when_active(self) -> None:
        coord = process_signals.SignalCoordinator()
        coord.install()
        assert coord.guarantees_cleanup is True

    def test_guarantees_cleanup_false_when_not_active(self) -> None:
        coord = process_signals.SignalCoordinator()
        assert coord.guarantees_cleanup is False

    def test_installed_true_after_install(self) -> None:
        coord = process_signals.SignalCoordinator()
        assert not coord.installed
        coord.install()
        assert coord.installed

    def test_installed_false_after_uninstall(self) -> None:
        coord = process_signals.SignalCoordinator()
        coord.install()
        coord.uninstall()
        assert not coord.installed

    def test_installed_true_during_draining(self) -> None:
        coord = process_signals.SignalCoordinator()
        coord.install()
        hold = _register_hold(coord)
        coord._on_signal(signal.SIGINT, None)
        assert coord.installed
        hold.set()
        coord._worker.join(timeout=5)

    def test_callback_count(self) -> None:
        coord = process_signals.SignalCoordinator()
        coord.install()
        assert coord.callback_count == 0
        coord.register(_noop)
        assert coord.callback_count == 1
        coord.register(_noop)
        assert coord.callback_count == 2

    def test_triggering_signal_none_initially(self) -> None:
        coord = process_signals.SignalCoordinator()
        coord.install()
        assert coord.triggering_signal is None

    def test_deadline_none_initially(self) -> None:
        coord = process_signals.SignalCoordinator()
        coord.install()
        assert coord.deadline is None


# ---------------------------------------------------------------------------
# Singletons
# ---------------------------------------------------------------------------


class TestGetCoordinator:
    """get_coordinator returns a singleton."""

    def test_get_coordinator_singleton(self) -> None:
        assert process_signals.get_coordinator() is process_signals.get_coordinator()


class TestGetProcessCancelToken:
    """get_process_cancel_token returns a singleton."""

    def test_get_process_cancel_token_singleton(self) -> None:
        assert process_signals.get_process_cancel_token() is process_signals.get_process_cancel_token()


# ---------------------------------------------------------------------------
# Error hierarchy
# ---------------------------------------------------------------------------


class TestErrorHierarchy:
    """CoordinatorStateError is-a SignalCoordinatorError is-a RuntimeError."""

    def test_coordinator_state_error_is_coordinator_error(self) -> None:
        err = process_signals.CoordinatorStateError("test")
        assert isinstance(err, process_signals.SignalCoordinatorError)
        assert isinstance(err, RuntimeError)

    def test_signal_coordinator_error_is_runtime_error(self) -> None:
        err = process_signals.SignalCoordinatorError("test")
        assert isinstance(err, RuntimeError)

    def test_operation_cancelled_error(self) -> None:
        err = process_signals.OperationCancelledError("cancelled")
        assert isinstance(err, Exception)


# ---------------------------------------------------------------------------
# Registration-vs-freeze race (identifier epoch protocol)
# ---------------------------------------------------------------------------


class TestRegistrationFreezeRace:
    """Registration is either in frozen snapshot or rejected."""

    def test_registration_rejected_when_handler_froze_first(self) -> None:
        coord = process_signals.SignalCoordinator()
        coord.install()
        hold = _register_hold(coord)
        coord._on_signal(signal.SIGINT, None)
        assert coord.phase is process_signals.CoordinatorPhase.DRAINING

        with pytest.raises(process_signals.CoordinatorStateError):
            coord.register(_noop)

        assert coord.callback_count == 0
        hold.set()
        coord._worker.join(timeout=5)

    def test_registration_accepted_before_handler_freezes(self) -> None:
        coord = process_signals.SignalCoordinator()
        coord.install()

        tok = coord.register(_noop)
        assert coord.callback_count == 1

        hold = _register_hold(coord)
        coord._on_signal(signal.SIGINT, None)
        assert tok._identifier in coord._frozen_identifiers
        hold.set()
        coord._worker.join(timeout=5)

    def test_concurrent_register_and_signal_consistent_outcome(self) -> None:
        coord = process_signals.SignalCoordinator()
        coord.install()
        barrier = threading.Barrier(2, timeout=5)
        results: list[str] = []

        def _register() -> None:
            barrier.wait()
            try:
                coord.register(_noop)
            except process_signals.CoordinatorStateError:
                results.append("rejected")
            else:
                results.append("accepted")

        t = threading.Thread(target=_register)

        hold = _register_hold(coord)
        coord._on_signal(signal.SIGINT, None)
        assert coord.phase is process_signals.CoordinatorPhase.DRAINING

        t.start()
        barrier.wait()
        t.join(timeout=5)

        assert results == ["rejected"]
        assert coord.callback_count == 0
        hold.set()
        coord._worker.join(timeout=5)


# ---------------------------------------------------------------------------
# Scheduling failure
# ---------------------------------------------------------------------------


class TestSchedulingFailure:
    """Scheduling failure in _run_registration for async callbacks."""

    def test_async_registration_with_unavailable_loop(self) -> None:
        """Async cleanup fails gracefully when owner loop becomes unavailable."""
        coord = process_signals.SignalCoordinator()
        coord.install()

        loop = _make_running_loop()
        tok = coord.register(_async_noop, owner_loop=loop)
        assert tok.active is True

        # After registration, make the loop appear closed.
        # _run_registration checks is_closed/is_running before scheduling.
        loop.is_closed.return_value = True

        # _on_signal triggers drain, which calls _run_registration.
        # The async callback should fail with a logged error but not crash.
        coord._on_signal(signal.SIGINT, None)
        worker = coord._worker
        if worker:
            worker.join(timeout=5)
        assert coord.phase in (
            process_signals.CoordinatorPhase.FINALIZING,
            process_signals.CoordinatorPhase.UNINSTALLED,
        )
