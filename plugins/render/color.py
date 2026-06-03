from typing import Union
from typing import Sequence

Color = tuple[int, int, int, int]
ColorLike = Union[str, Sequence[int]]


def rgba(red: int, green: int, blue: int, alpha: int = 255) -> Color:
    """Create an RGBA color tuple.

    Args:
        red: Red channel value.
        green: Green channel value.
        blue: Blue channel value.
        alpha: Alpha channel value.

    Returns:
        Clamped ``(red, green, blue, alpha)`` tuple.
    """

    return (_clamp(red), _clamp(green), _clamp(blue), _clamp(alpha))


def rgb(red: int, green: int, blue: int) -> Color:
    """Create an opaque RGBA color tuple.

    Args:
        red: Red channel value.
        green: Green channel value.
        blue: Blue channel value.

    Returns:
        Clamped opaque ``(red, green, blue, 255)`` tuple.
    """

    return rgba(red, green, blue)


def normalize_color(value: ColorLike | None) -> Color | None:
    """Normalize supported color inputs.

    Args:
        value: ``None``, a hex string, or a 3/4-channel integer sequence.

    Returns:
        RGBA tuple, or ``None`` when ``value`` is ``None``.
    """

    if value is None:
        return None
    if isinstance(value, str):
        return _from_hex(value)
    parts = tuple(int(part) for part in value)
    if len(parts) == 3:
        return rgba(parts[0], parts[1], parts[2])
    if len(parts) == 4:
        return rgba(parts[0], parts[1], parts[2], parts[3])
    raise ValueError("color tuples must have 3 or 4 channels")


def _from_hex(value: str) -> Color:
    """Parse a hex color string.

    Args:
        value: Hex color in ``#RRGGBB`` or ``#RRGGBBAA`` form.

    Returns:
        RGBA tuple.
    """

    text = value.strip()
    if text.startswith("#"):
        text = text[1:]
    if len(text) == 6:
        return rgba(
            int(text[0:2], 16),
            int(text[2:4], 16),
            int(text[4:6], 16),
        )
    if len(text) == 8:
        return rgba(
            int(text[0:2], 16),
            int(text[2:4], 16),
            int(text[4:6], 16),
            int(text[6:8], 16),
        )
    raise ValueError("hex colors must be #RRGGBB or #RRGGBBAA")


def _clamp(value: int) -> int:
    """Clamp a color channel to the 0-255 range.

    Args:
        value: Channel value.

    Returns:
        Clamped integer channel value.
    """

    return max(0, min(255, int(value)))
