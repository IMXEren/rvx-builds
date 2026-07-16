"""Tests for the concrete browser driver runtime state container."""

from __future__ import annotations

import ast
import asyncio
from pathlib import Path
from unittest import TestCase

from src.browser.driver.runtime import BrowserRuntimeState

# ruff: noqa: PT009

ROOT = Path(__file__).resolve().parents[1]


class BrowserRuntimeStateTests(TestCase):
    """Concrete state container behavior."""

    def test_state_defaults_are_empty_and_concrete(self) -> None:
        """Happy path: live maps, locks, semaphore, and identity start ready."""
        state = BrowserRuntimeState(max_groups=3)

        self.assertIsNone(state.main_ctx)
        self.assertIsNone(state.shared_pd)
        self.assertEqual(state.target_to_page_map, {})
        self.assertEqual(state.page_to_group, {})
        self.assertEqual(state.active_groups, set())
        self.assertIsInstance(state.spawn_lock, asyncio.Lock)
        self.assertIsInstance(state.group_semaphore, asyncio.Semaphore)
        self.assertEqual(state.next_group_id, 1)

    def test_each_state_gets_independent_mutable_containers(self) -> None:
        """Invariant: maps and locks are not shared across state instances."""
        first = BrowserRuntimeState(max_groups=1)
        second = BrowserRuntimeState(max_groups=2)

        first.target_to_page_map["target"] = object()
        first.active_groups.add(object())

        self.assertEqual(second.target_to_page_map, {})
        self.assertEqual(second.active_groups, set())
        self.assertIsNot(first.spawn_lock, second.spawn_lock)
        self.assertIsNot(first.group_semaphore, second.group_semaphore)

    def test_group_id_allocation_advances_for_multiple_inputs(self) -> None:
        """Input variation: sequential ids advance across typical values."""
        state = BrowserRuntimeState(max_groups=3)

        self.assertEqual([state.allocate_group_id() for _ in range(3)], [1, 2, 3])
        self.assertEqual(state.next_group_id, 4)

    def test_boundary_max_groups_configures_semaphore(self) -> None:
        """Boundary: semaphore honors the configured group limit."""
        state = BrowserRuntimeState(max_groups=1)

        self.assertEqual(state.group_semaphore._value, 1)  # noqa: SLF001

    def test_error_path_rejects_abstract_driver_shapes(self) -> None:
        """Error path: no protocol, ABC, adapter, interface, or vtable module is added."""
        driver_dir = ROOT / "src" / "browser" / "driver"
        self.assertFalse((driver_dir / "interfaces.py").exists())

        for path in [driver_dir / "runtime.py", ROOT / "src" / "browser" / "browser.py"]:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            names = {node.id for node in ast.walk(tree) if isinstance(node, ast.Name)}
            self.assertTrue({"Protocol", "ABC", "abstractmethod", "Adapter", "VTable"}.isdisjoint(names))
