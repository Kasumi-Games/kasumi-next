"""Image encoding for outgoing messages.

Every renderer returns a ``PIL.Image.Image``; this is the single place that turns
one into something sendable. Before this module the same four lines were copied
into ``plugins/bang_avatar/render.py``, ``plugins/bang_avatar/utils.py``,
``plugins/one_stroke/__init__.py`` and ``plugins/cck/draw.py``.

Note: ``utils.image_to_bytes`` is a different, older helper that produces JPEG
bytes for the matplotlib chart pipeline. It is not a replacement for this.
"""

import io
from collections.abc import Callable
from typing import TypeVar
from typing import ParamSpec

from PIL import Image
from nonebot.adapters.satori import MessageSegment

from .image_tasks import run_image_task

P = ParamSpec("P")
T = TypeVar("T")


def image_bytes(image: Image.Image) -> bytes:
    """Encode an image as PNG bytes.

    PNG rather than JPEG because rendered cards are mostly flat fills and text.
    JPEG's chroma subsampling visibly damages exactly the things the kits rely
    on: the magenta/cyan tube edges in ``neon``, the pink body text in
    ``sakura``, and every hairline separator.

    Args:
        image: Image to encode.

    Returns:
        PNG-encoded bytes.
    """

    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def image_segment(image: Image.Image) -> MessageSegment:
    """Encode an image as a satori image message segment.

    Args:
        image: Image to send.

    Returns:
        Message segment carrying the PNG.
    """

    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return MessageSegment.image(raw=buffer, mime="image/png")


async def render_image_segment(
    renderer: Callable[P, Image.Image],
    /,
    *args: P.args,
    **kwargs: P.kwargs,
) -> MessageSegment:
    """Render and PNG-encode an image without blocking the event loop.

    Keeping both PIL stages in one worker avoids moving only the drawing work
    off-loop while accidentally doing the potentially expensive ``save`` back
    on the event-loop thread.

    Args:
        renderer: Synchronous callable returning a PIL image.
        *args: Positional arguments passed to ``renderer``.
        **kwargs: Keyword arguments passed to ``renderer``.

    Returns:
        Image message segment carrying the rendered PNG.
    """

    def render_and_encode() -> MessageSegment:
        return image_segment(renderer(*args, **kwargs))

    return await run_image_task(render_and_encode)


async def image_segment_async(image: Image.Image) -> MessageSegment:
    """PNG-encode an already-rendered image outside the event-loop thread."""

    return await run_image_task(image_segment, image)


async def render_image_value(
    renderer: Callable[P, Image.Image],
    encoder: Callable[[Image.Image], T],
    /,
    *args: P.args,
    **kwargs: P.kwargs,
) -> T:
    """Render an image and transform it in the same worker-thread call."""

    def render_and_encode() -> T:
        return encoder(renderer(*args, **kwargs))

    return await run_image_task(render_and_encode)
