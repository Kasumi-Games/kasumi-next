"""Bounded worker pool for synchronous image work."""

import asyncio
import os
from typing import Any
from typing import TypeVar
from typing import ParamSpec
from functools import partial
from collections.abc import Callable
from concurrent.futures import Executor
from concurrent.futures import ThreadPoolExecutor

P = ParamSpec("P")
T = TypeVar("T")

# Image renders are CPU- and memory-heavy. A small dedicated pool keeps bursts
# from occupying asyncio's shared executor or materialising dozens of large
# supersampled canvases at once.
IMAGE_WORKERS = max(2, min(4, os.cpu_count() or 2))
IMAGE_EXECUTOR = ThreadPoolExecutor(
    max_workers=IMAGE_WORKERS,
    thread_name_prefix="kasumi-image",
)


async def run_image_task(
    function: Callable[P, T],
    /,
    *args: P.args,
    executor: Executor | None = None,
    **kwargs: P.kwargs,
) -> T:
    """Run synchronous image work in the bounded image executor."""

    loop = asyncio.get_running_loop()
    call: Callable[[], Any] = partial(function, *args, **kwargs)
    return await loop.run_in_executor(executor or IMAGE_EXECUTOR, call)
