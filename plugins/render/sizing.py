from typing import Union
from dataclasses import dataclass


@dataclass(frozen=True)
class Fit:
    """Use the component's intrinsic size."""


@dataclass(frozen=True)
class Fill:
    """Use remaining bounded parent space."""


@dataclass(frozen=True)
class Fixed:
    """Use an exact pixel size.

    Attributes:
        value: Pixel size.
    """

    value: int

    def __post_init__(self) -> None:
        if self.value < 0:
            raise ValueError("Fixed size must be non-negative")


@dataclass(frozen=True)
class Fraction:
    """Use a fraction of bounded parent space.

    Attributes:
        value: Fraction of the bounded parent axis.
    """

    value: float

    def __post_init__(self) -> None:
        if self.value < 0:
            raise ValueError("Fraction must be non-negative")


SizeValue = Union[Fit, Fill, Fixed, Fraction]


def as_size_value(value: SizeValue | int | None) -> SizeValue:
    """Normalize shorthand size inputs.

    Args:
        value: Sizing token, integer pixel value, or ``None``.

    Returns:
        Sizing token. ``None`` becomes ``Fit`` and integers become ``Fixed``.
    """

    if value is None:
        return Fit()
    if isinstance(value, int):
        return Fixed(value)
    return value
