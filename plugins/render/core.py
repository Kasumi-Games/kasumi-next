from typing import Protocol
from dataclasses import field
from dataclasses import replace
from dataclasses import dataclass

from PIL import Image

from .spacing import Insets
from .image_cache import ImageCache


class LayoutError(RuntimeError):
    """Raised when component constraints cannot produce a valid layout."""


@dataclass(frozen=True)
class Size:
    """Pixel dimensions produced by measurement.

    Attributes:
        width: Width in pixels.
        height: Height in pixels.
    """

    width: int
    height: int

    def __post_init__(self) -> None:
        if self.width < 0 or self.height < 0:
            raise ValueError("size values must be non-negative")


@dataclass(frozen=True)
class Rect:
    """Concrete render slot in the parent canvas.

    Attributes:
        x: Left coordinate in pixels.
        y: Top coordinate in pixels.
        width: Width in pixels.
        height: Height in pixels.
    """

    x: int
    y: int
    width: int
    height: int

    @property
    def right(self) -> int:
        """Right edge coordinate."""

        return self.x + self.width

    @property
    def bottom(self) -> int:
        """Bottom edge coordinate."""

        return self.y + self.height


@dataclass(frozen=True)
class Constraints:
    """Min/max bounds offered by a parent during layout measurement.

    Attributes:
        min_width: Minimum allowed width.
        max_width: Maximum allowed width, or ``None`` when unbounded.
        min_height: Minimum allowed height.
        max_height: Maximum allowed height, or ``None`` when unbounded.
    """

    min_width: int = 0
    max_width: int | None = None
    min_height: int = 0
    max_height: int | None = None

    def __post_init__(self) -> None:
        if self.min_width < 0 or self.min_height < 0:
            raise ValueError("minimum constraints must be non-negative")
        if self.max_width is not None and self.max_width < self.min_width:
            raise ValueError("max_width must be >= min_width")
        if self.max_height is not None and self.max_height < self.min_height:
            raise ValueError("max_height must be >= min_height")

    def shrink(self, width: int = 0, height: int = 0) -> "Constraints":
        """Return constraints reduced by reserved outer space.

        Args:
            width: Horizontal pixels to reserve.
            height: Vertical pixels to reserve.

        Returns:
            New constraints with reduced min/max bounds.
        """

        return Constraints(
            min_width=max(0, self.min_width - width),
            max_width=None
            if self.max_width is None
            else max(0, self.max_width - width),
            min_height=max(0, self.min_height - height),
            max_height=None
            if self.max_height is None
            else max(0, self.max_height - height),
        )

    def clamp(self, size: Size) -> Size:
        """Clamp a measured size into this constraint range.

        Args:
            size: Size to clamp.

        Returns:
            Size adjusted to satisfy min and max bounds.
        """

        width = max(self.min_width, size.width)
        height = max(self.min_height, size.height)
        if self.max_width is not None:
            width = min(width, self.max_width)
        if self.max_height is not None:
            height = min(height, self.max_height)
        return Size(width, height)

    def require_width(self, owner: str) -> int:
        """Return bounded width for sizing modes that require one.

        Args:
            owner: Name used in layout error messages.

        Returns:
            Maximum width.
        """

        if self.max_width is None:
            raise LayoutError(f"{owner} requires bounded max_width")
        return self.max_width

    def require_height(self, owner: str) -> int:
        """Return bounded height for sizing modes that require one.

        Args:
            owner: Name used in layout error messages.

        Returns:
            Maximum height.
        """

        if self.max_height is None:
            raise LayoutError(f"{owner} requires bounded max_height")
        return self.max_height


@dataclass
class RenderContext:
    """Shared render-time services and flags.

    Attributes:
        image_cache: Cache for loaded external images.
        debug: Whether layout components draw debug outlines.
        pixel_ratio: Requested root-render supersampling ratio. Page roots use this
            to create a larger internal canvas and downsample back to logical size.
        _render_ratio: Active draw-time ratio for the current canvas. This stays
            ``1`` for direct component renders and is set from ``pixel_ratio`` only
            inside ``Page``/``AutoPage`` root rendering.
    """

    image_cache: ImageCache = field(default_factory=ImageCache)
    debug: bool = False
    pixel_ratio: int = 2
    _render_ratio: int = field(default=1, repr=False, compare=False)
    _measure_cache: dict[tuple[int, Constraints], tuple[object, Size]] | None = field(
        default=None, repr=False, compare=False
    )

    def __post_init__(self) -> None:
        if type(self.pixel_ratio) is not int or self.pixel_ratio < 1:
            raise ValueError("pixel_ratio must be an integer >= 1")
        if type(self._render_ratio) is not int or self._render_ratio < 1:
            raise ValueError("_render_ratio must be an integer >= 1")

    @property
    def render_ratio(self) -> int:
        """Active render scale for drawing into the current canvas."""

        return self._render_ratio

    def activate_pixel_ratio(self) -> "RenderContext":
        """Return a context whose draw-time scale matches ``pixel_ratio``."""

        return replace(self, _render_ratio=self.pixel_ratio)

    def for_root_render(self) -> "RenderContext":
        """Return a logical context with an empty render-scoped measure cache."""

        return replace(self, _render_ratio=1, _measure_cache={})

    def measure(self, component: "Component", constraints: Constraints) -> Size:
        """Measure a component once per constraint set during a root render."""

        if self._measure_cache is None:
            return component.measure(self, constraints)
        key = (id(component), constraints)
        cached = self._measure_cache.get(key)
        if cached is not None and cached[0] is component:
            return cached[1]
        size = component.measure(self, constraints)
        # Retaining the component alongside the id prevents object-id reuse
        # from aliasing transient Frame instances during the same render.
        self._measure_cache[key] = (component, size)
        return size

    def scale_px(self, value: int | float) -> int:
        """Scale a logical pixel value into current render pixels."""

        return round(value * self._render_ratio)

    def unscale_px(self, value: int | float) -> int:
        """Convert current render pixels back to logical pixels."""

        return round(value / self._render_ratio)

    def scale_size(self, size: Size) -> Size:
        """Scale logical dimensions into current render pixels."""

        return Size(self.scale_px(size.width), self.scale_px(size.height))

    def scale_rect(self, rect: Rect) -> Rect:
        """Scale a logical rectangle into current render pixels."""

        return Rect(
            self.scale_px(rect.x),
            self.scale_px(rect.y),
            self.scale_px(rect.width),
            self.scale_px(rect.height),
        )

    def scale_constraints(self, constraints: Constraints) -> Constraints:
        """Scale logical constraints into current render pixels."""

        return Constraints(
            min_width=self.scale_px(constraints.min_width),
            max_width=None
            if constraints.max_width is None
            else self.scale_px(constraints.max_width),
            min_height=self.scale_px(constraints.min_height),
            max_height=None
            if constraints.max_height is None
            else self.scale_px(constraints.max_height),
        )

    def unscale_constraints(self, constraints: Constraints) -> Constraints:
        """Convert current render-pixel constraints to logical constraints."""

        return Constraints(
            min_width=self.unscale_px(constraints.min_width),
            max_width=None
            if constraints.max_width is None
            else self.unscale_px(constraints.max_width),
            min_height=self.unscale_px(constraints.min_height),
            max_height=None
            if constraints.max_height is None
            else self.unscale_px(constraints.max_height),
        )

    def scale_insets(self, insets: Insets) -> Insets:
        """Scale logical insets into current render pixels."""

        return Insets(
            left=self.scale_px(insets.left),
            top=self.scale_px(insets.top),
            right=self.scale_px(insets.right),
            bottom=self.scale_px(insets.bottom),
        )


class Component(Protocol):
    """Anything that can measure itself and paint into an assigned rect."""

    def measure(self, ctx: RenderContext, constraints: Constraints) -> Size:
        """Measure this component under parent constraints.

        Args:
            ctx: Shared render context.
            constraints: Parent-provided measurement bounds.

        Returns:
            Desired component size.
        """

        ...

    def render(self, ctx: RenderContext, canvas: Image.Image, rect: Rect) -> None:
        """Paint this component into an assigned rectangle.

        Args:
            ctx: Shared render context.
            canvas: Destination image.
            rect: Assigned render rectangle.
        """

        ...


class Background(Protocol):
    """Page background renderer; backgrounds size themselves to the page."""

    def render(self, ctx: RenderContext, size: Size) -> Image.Image:
        """Render a background image for a page.

        Args:
            ctx: Shared render context.
            size: Requested background size.

        Returns:
            Rendered background image.
        """

        ...
