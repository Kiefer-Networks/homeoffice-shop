import asyncio
from typing import Any

_background_tasks: set[asyncio.Task[Any]] = set()


def create_background_task(coro) -> asyncio.Task:
    """Create a background task with proper lifecycle management."""
    task = asyncio.create_task(coro)
    _background_tasks.add(task)
    task.add_done_callback(_background_tasks.discard)
    return task
