"""Image encoding for outgoing messages.

Every renderer returns a ``PIL.Image.Image``; this is the single place that turns
one into something sendable. Before this module the same four lines were copied
into ``plugins/bang_avatar/render.py``, ``plugins/bang_avatar/utils.py``,
``plugins/one_stroke/__init__.py`` and ``plugins/cck/draw.py``.

Note: ``utils.image_to_bytes`` is a different, older helper that produces JPEG
bytes for the matplotlib chart pipeline. It is not a replacement for this.
"""

import io

from PIL import Image
from nonebot.adapters.satori import MessageSegment


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
