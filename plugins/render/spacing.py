from typing import Union
from dataclasses import dataclass


@dataclass(frozen=True)
class Insets:
    """Insets around a rectangular content box.

    Attributes:
        left: Left inset in pixels.
        top: Top inset in pixels.
        right: Right inset in pixels.
        bottom: Bottom inset in pixels.
    """

    left: int = 0
    top: int = 0
    right: int = 0
    bottom: int = 0

    @classmethod
    def all(cls, value: int) -> "Insets":
        """Create equal insets on all sides.

        Args:
            value: Inset value in pixels.

        Returns:
            Insets with all sides set to ``value``.
        """

        return cls(value, value, value, value)

    @classmethod
    def xy(cls, x: int = 0, y: int = 0) -> "Insets":
        """Create symmetric horizontal and vertical insets.

        Args:
            x: Left and right inset in pixels.
            y: Top and bottom inset in pixels.

        Returns:
            Insets with matching horizontal and vertical sides.
        """

        return cls(x, y, x, y)

    @classmethod
    def only(
        cls, left: int = 0, top: int = 0, right: int = 0, bottom: int = 0
    ) -> "Insets":
        """Create insets by specifying each side.

        Args:
            left: Left inset in pixels.
            top: Top inset in pixels.
            right: Right inset in pixels.
            bottom: Bottom inset in pixels.

        Returns:
            Insets with the provided side values.
        """

        return cls(left, top, right, bottom)

    @property
    def horizontal(self) -> int:
        """Total horizontal inset."""

        return self.left + self.right

    @property
    def vertical(self) -> int:
        """Total vertical inset."""

        return self.top + self.bottom


InsetsLike = Union[int, Insets]


def as_insets(value: InsetsLike | None) -> Insets:
    """Normalize shorthand inset inputs.

    Args:
        value: Insets, integer shorthand, or ``None``.

    Returns:
        Insets instance. ``None`` becomes zero insets; integers apply to all sides.
    """

    if value is None:
        return Insets()
    if isinstance(value, int):
        return Insets.all(value)
    return value
