"""Utilities for browser."""

import asyncio
import threading
from collections.abc import Coroutine
from concurrent.futures import ThreadPoolExecutor
from typing import Any

from annotated_types import T


def run_coroutine_sync(coroutine: Coroutine[Any, Any, T]) -> T:
    """Run a coroutine synchronously, bridging into any thread/loop context."""

    def _run_in_new_loop() -> T:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            return loop.run_until_complete(coroutine)
        finally:
            loop.run_until_complete(loop.shutdown_asyncgens())
            loop.run_until_complete(loop.shutdown_default_executor())
            loop.close()

    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coroutine)

    if threading.current_thread() is threading.main_thread():
        if not loop.is_running():
            return loop.run_until_complete(coroutine)
        with ThreadPoolExecutor(1) as pool:
            future = pool.submit(_run_in_new_loop)
            return future.result()

    return asyncio.run_coroutine_threadsafe(coroutine, loop).result()
