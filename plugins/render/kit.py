from abc import ABC
from abc import abstractmethod
from typing import Literal

from .core import Component
from .core import Background
from .color import ColorLike
from .types import ImageFit
from .types import Overflow
from .types import TextAlign
from .types import ImageSource
from .sizing import SizeValue
from .spacing import InsetsLike


class BaseKit(ABC):
    """Abstract contract for neutral render-kit atoms.

    Concrete kits may expose richer theme-specific helpers, but shared callers
    should only depend on these general factories.
    """

    @abstractmethod
    def background(self, *, fill: ColorLike | None = None) -> Background:
        """Create a neutral page background.

        Args:
            fill: Optional background fill color override.

        Returns:
            Background renderer.
        """

        ...

    @abstractmethod
    def text(
        self,
        text: str,
        *,
        font_size: int = 40,
        color: ColorLike | None = None,
        align: TextAlign = "left",
        wrap: bool = True,
        max_lines: int | None = None,
        overflow: Overflow = "ellipsis",
        line_height: int | None = None,
    ) -> Component:
        """Create text.

        Args:
            text: Text content.
            font_size: Requested font size in pixels.
            color: Optional text color override.
            align: Horizontal text alignment.
            wrap: Whether text may wrap inside a bounded width.
            max_lines: Optional maximum number of rendered lines.
            overflow: Behavior when text exceeds its bounds.
            line_height: Optional line height override.

        Returns:
            Text component.
        """

        ...

    @abstractmethod
    def image(
        self,
        image: ImageSource,
        *,
        width: SizeValue | int | None = None,
        height: SizeValue | int | None = None,
        fit: ImageFit = "contain",
        opacity: float = 1.0,
        radius: int = 0,
    ) -> Component:
        """Create an image wrapper.

        Args:
            image: Image path or in-memory PIL image.
            width: Optional width sizing token or pixel value.
            height: Optional height sizing token or pixel value.
            fit: Resize behavior inside the assigned rectangle.
            opacity: Alpha multiplier from 0.0 to 1.0.
            radius: Optional corner radius in pixels.

        Returns:
            Image component.
        """

        ...

    @abstractmethod
    def panel(
        self,
        child: Component | None = None,
        *,
        width: SizeValue | int | None = None,
        height: SizeValue | int | None = None,
        padding: InsetsLike = 0,
        fill: ColorLike | None = None,
        radius: int | None = None,
    ) -> Component:
        """Create a container surface.

        Args:
            child: Optional child component.
            width: Optional width sizing token or pixel value.
            height: Optional height sizing token or pixel value.
            padding: Insets between the panel and child.
            fill: Optional panel fill color override.
            radius: Optional corner radius override.

        Returns:
            Panel component.
        """

        ...

    @abstractmethod
    def separator(
        self,
        *,
        orientation: Literal["horizontal", "vertical"] = "horizontal",
        length: SizeValue | int | None = None,
        thickness: int = 2,
        color: ColorLike | None = None,
    ) -> Component:
        """Create a divider.

        Args:
            orientation: Divider direction.
            length: Optional length sizing token or pixel value.
            thickness: Divider thickness in pixels.
            color: Optional divider color override.

        Returns:
            Separator component.
        """

        ...
