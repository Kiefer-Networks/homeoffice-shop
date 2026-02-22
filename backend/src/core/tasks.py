import asyncio
import logging
from collections.abc import Coroutine
from typing import Any

logger = logging.getLogger(__name__)

_background_tasks: set[asyncio.Task[Any]] = set()


def _task_done(task: asyncio.Task) -> None:
    _background_tasks.discard(task)
    if not task.cancelled():
        exc = task.exception()
        if exc:
            logger.error("Background task failed: %s", exc, exc_info=exc)


def create_background_task(coro: Coroutine[Any, Any, Any]) -> asyncio.Task:
    """Create a background task with proper lifecycle management."""
    task = asyncio.create_task(coro)
    _background_tasks.add(task)
    task.add_done_callback(_task_done)
    return task
