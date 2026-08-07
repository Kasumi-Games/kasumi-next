from math import ceil
from typing import Literal
from typing import Sequence
from dataclasses import field
from dataclasses import dataclass
from concurrent.futures import Executor

from PIL import Image
from PIL import ImageDraw

from utils.image_tasks import run_image_task

from .core import Rect
from .core import Size
from .core import Component
from .core import Background
from .core import Constraints
from .core import LayoutError
from .core import RenderContext
from .sizing import Fit
from .sizing import Fill
from .sizing import Fixed
from .sizing import Fraction
from .sizing import SizeValue
from .sizing import as_size_value
from .spacing import Insets
from .spacing import InsetsLike
from .spacing import as_insets

Align = Literal["start", "center", "end", "stretch"]


@dataclass(frozen=True)
class Page:
    """Fixed-size render root.

    Attributes:
        size: Output image size as ``(width, height)``.
        child: Optional component rendered inside the page content box.
        background: Optional page-sized background renderer.
        padding: Insets removed from the page before rendering ``child``.
    """

    size: tuple[int, int]
    child: Component | None = None
    background: Background | None = None
    padding: InsetsLike = 0

    def render(self, ctx: RenderContext | None = None) -> Image.Image:
        """Render the page to a new RGBA image.

        Args:
            ctx: Shared render context. A default context is created when omitted.

        Returns:
            The rendered page image.
        """

        ctx = (ctx or RenderContext()).for_root_render()
        render_ctx = ctx.activate_pixel_ratio()
        page_size = Size(*self.size)
        render_size = render_ctx.scale_size(page_size)
        canvas = (
            self.background.render(render_ctx, render_size)
            if self.background is not None
            else Image.new(
                "RGBA", (render_size.width, render_size.height), (0, 0, 0, 0)
            )
        )
        if self.child is not None:
            padding = as_insets(self.padding)
            rect = Rect(
                padding.left,
                padding.top,
                max(0, page_size.width - padding.horizontal),
                max(0, page_size.height - padding.vertical),
            )
            self.child.render(render_ctx, canvas, render_ctx.scale_rect(rect))
        if ctx.pixel_ratio == 1:
            return canvas
        return canvas.resize(self.size, Image.Resampling.LANCZOS)

    async def render_async(
        self,
        ctx: RenderContext | None = None,
        *,
        executor: Executor | None = None,
    ) -> Image.Image:
        """Render the page in a thread pool without blocking the event loop.

        Args:
            ctx: Shared render context. A default context is created when omitted.
            executor: Optional executor to use. When omitted, the bounded image
                thread pool is used.

        Returns:
            The rendered page image.
        """

        return await run_image_task(self.render, ctx, executor=executor)


@dataclass(frozen=True)
class AutoPage:
    """Render root that sizes itself from its child.

    Attributes:
        child: Component used to determine the page size.
        background: Optional background rendered at the computed page size.
        padding: Insets added around the measured child.
        min_width: Minimum page width after padding.
        max_width: Maximum page width after padding.
        min_height: Minimum page height after padding.
        max_height: Maximum page height after padding.
    """

    child: Component
    background: Background | None = None
    padding: InsetsLike = 0
    min_width: int = 0
    max_width: int | None = None
    min_height: int = 0
    max_height: int | None = None

    def render(self, ctx: RenderContext | None = None) -> Image.Image:
        """Measure the child, choose a page size, and render the result.

        Args:
            ctx: Shared render context. A default context is created when omitted.

        Returns:
            The rendered page image.
        """

        ctx = (ctx or RenderContext()).for_root_render()
        padding = as_insets(self.padding)
        constraints = Constraints(
            min_width=max(0, self.min_width - padding.horizontal),
            max_width=None
            if self.max_width is None
            else max(0, self.max_width - padding.horizontal),
            min_height=max(0, self.min_height - padding.vertical),
            max_height=None
            if self.max_height is None
            else max(0, self.max_height - padding.vertical),
        )
        child_size = ctx.measure(self.child, constraints)
        page_size = Constraints(
            self.min_width,
            self.max_width,
            self.min_height,
            self.max_height,
        ).clamp(
            Size(
                child_size.width + padding.horizontal,
                child_size.height + padding.vertical,
            )
        )
        render_ctx = ctx.activate_pixel_ratio()
        render_size = render_ctx.scale_size(page_size)
        canvas = (
            self.background.render(render_ctx, render_size)
            if self.background is not None
            else Image.new(
                "RGBA", (render_size.width, render_size.height), (0, 0, 0, 0)
            )
        )
        self.child.render(
            render_ctx,
            canvas,
            render_ctx.scale_rect(
                Rect(padding.left, padding.top, child_size.width, child_size.height)
            ),
        )
        if ctx.pixel_ratio == 1:
            return canvas
        return canvas.resize(
            (page_size.width, page_size.height), Image.Resampling.LANCZOS
        )

    async def render_async(
        self,
        ctx: RenderContext | None = None,
        *,
        executor: Executor | None = None,
    ) -> Image.Image:
        """Measure and render the page in a thread pool.

        Args:
            ctx: Shared render context. A default context is created when omitted.
            executor: Optional executor to use. When omitted, the bounded image
                thread pool is used.

        Returns:
            The rendered page image.
        """

        return await run_image_task(self.render, ctx, executor=executor)


@dataclass(frozen=True)
class Spacer:
    """Layout-only component that occupies space without drawing.

    Attributes:
        width: Horizontal sizing token or fixed pixel value.
        height: Vertical sizing token or fixed pixel value.
    """

    width: SizeValue | int | None = None
    height: SizeValue | int | None = None

    def measure(self, ctx: RenderContext, constraints: Constraints) -> Size:
        """Resolve the spacer's requested size under parent constraints.

        Args:
            ctx: Shared render context.
            constraints: Parent-provided measurement bounds.

        Returns:
            Resolved spacer size.
        """

        return Size(
            _resolve_axis(
                as_size_value(self.width), constraints.max_width, "Spacer.width"
            ),
            _resolve_axis(
                as_size_value(self.height), constraints.max_height, "Spacer.height"
            ),
        )

    def render(self, ctx: RenderContext, canvas: Image.Image, rect: Rect) -> None:
        """Render the spacer debug outline when debug mode is enabled.

        Args:
            ctx: Shared render context.
            canvas: Destination image.
            rect: Assigned render rectangle.
        """

        _draw_debug(ctx, canvas, rect, "spacer")


@dataclass(frozen=True)
class Frame:
    """Single-child layout wrapper.

    Attributes:
        child: Optional child component.
        width: Outer width sizing token or fixed pixel value.
        height: Outer height sizing token or fixed pixel value.
        padding: Insets between the outer frame and child content.
        align_x: Horizontal child alignment inside the content box.
        align_y: Vertical child alignment inside the content box.
        aspect_ratio: Optional ``width / height`` ratio applied to the outer size.
        max_width: Optional outer width cap before aspect-ratio correction.
        max_height: Optional outer height cap before aspect-ratio correction.
    """

    child: Component | None = None
    width: SizeValue | int | None = None
    height: SizeValue | int | None = None
    padding: InsetsLike = 0
    align_x: Align = "center"
    align_y: Align = "center"
    aspect_ratio: float | None = None
    max_width: int | None = None
    max_height: int | None = None

    def measure(self, ctx: RenderContext, constraints: Constraints) -> Size:
        """Measure the frame's outer size.

        Args:
            ctx: Shared render context.
            constraints: Parent-provided measurement bounds.

        Returns:
            Outer frame size after padding, max-size caps, and aspect correction.
        """

        padding = as_insets(self.padding)
        width_value = as_size_value(self.width)
        height_value = as_size_value(self.height)

        outer_w = _resolve_optional_axis(
            width_value, constraints.max_width, "Frame.width"
        )
        outer_h = _resolve_optional_axis(
            height_value, constraints.max_height, "Frame.height"
        )

        child_constraints = Constraints(
            max_width=max(0, outer_w - padding.horizontal)
            if outer_w is not None
            else (
                None
                if constraints.max_width is None
                else max(0, constraints.max_width - padding.horizontal)
            ),
            max_height=max(0, outer_h - padding.vertical)
            if outer_h is not None
            else (
                None
                if constraints.max_height is None
                else max(0, constraints.max_height - padding.vertical)
            ),
        )
        child_size = (
            ctx.measure(self.child, child_constraints)
            if self.child is not None
            else Size(0, 0)
        )
        if outer_w is None:
            outer_w = child_size.width + padding.horizontal
        if outer_h is None:
            outer_h = child_size.height + padding.vertical

        outer = _apply_max(Size(outer_w, outer_h), self.max_width, self.max_height)
        outer = _apply_aspect(outer, self.aspect_ratio)
        return constraints.clamp(outer)

    def render(self, ctx: RenderContext, canvas: Image.Image, rect: Rect) -> None:
        """Render the child inside the assigned outer rectangle.

        Args:
            ctx: Shared render context.
            canvas: Destination image.
            rect: Assigned outer rectangle.
        """

        _draw_debug(ctx, canvas, rect, "frame")
        if self.child is None:
            return
        padding = _scale_insets(ctx, self.padding)
        content = Rect(
            rect.x + padding.left,
            rect.y + padding.top,
            max(0, rect.width - padding.horizontal),
            max(0, rect.height - padding.vertical),
        )
        child_size = _measure_child_for_render(
            ctx, self.child, content.width, content.height
        )
        child_w = (
            content.width
            if self.align_x == "stretch"
            else min(child_size.width, content.width)
        )
        child_h = (
            content.height
            if self.align_y == "stretch"
            else min(child_size.height, content.height)
        )
        child_rect = Rect(
            content.x + _align_offset(content.width, child_w, self.align_x),
            content.y + _align_offset(content.height, child_h, self.align_y),
            child_w,
            child_h,
        )
        self.child.render(ctx, canvas, child_rect)


@dataclass(frozen=True)
class VStack:
    """Vertical stack layout.

    Attributes:
        children: Components rendered from top to bottom.
        gap: Pixels inserted between adjacent children.
        align: Horizontal alignment for each child.
    """

    children: Sequence[Component] = field(default_factory=tuple)
    gap: int = 0
    align: Align = "stretch"

    def measure(self, ctx: RenderContext, constraints: Constraints) -> Size:
        """Measure the stack, requiring a bounded height when children use Fill.

        Args:
            ctx: Shared render context.
            constraints: Parent-provided measurement bounds.

        Returns:
            Stack size.
        """

        sizes, fill_count = _measure_stack_children(
            ctx, constraints, self.children, axis="vertical", gap=self.gap
        )
        width = max((size.width for size in sizes), default=0)
        height = sum(size.height for size in sizes) + self.gap * max(0, len(sizes) - 1)
        if fill_count:
            height = constraints.require_height("VStack with Fill children")
        return constraints.clamp(Size(width, height))

    def render(self, ctx: RenderContext, canvas: Image.Image, rect: Rect) -> None:
        """Assign vertical child rectangles and render each child.

        Args:
            ctx: Shared render context.
            canvas: Destination image.
            rect: Assigned stack rectangle.
        """

        _draw_debug(ctx, canvas, rect, "vstack")
        child_rects = _stack_layout(
            ctx, self.children, rect, self.gap, "vertical", self.align
        )
        for child, child_rect in zip(self.children, child_rects):
            child.render(ctx, canvas, child_rect)


@dataclass(frozen=True)
class HStack:
    """Horizontal stack layout.

    Attributes:
        children: Components rendered from left to right.
        gap: Pixels inserted between adjacent children.
        align: Vertical alignment for each child.
    """

    children: Sequence[Component] = field(default_factory=tuple)
    gap: int = 0
    align: Align = "stretch"

    def measure(self, ctx: RenderContext, constraints: Constraints) -> Size:
        """Measure the stack, requiring a bounded width when children use Fill.

        Args:
            ctx: Shared render context.
            constraints: Parent-provided measurement bounds.

        Returns:
            Stack size.
        """

        sizes, fill_count = _measure_stack_children(
            ctx, constraints, self.children, axis="horizontal", gap=self.gap
        )
        width = sum(size.width for size in sizes) + self.gap * max(0, len(sizes) - 1)
        height = max((size.height for size in sizes), default=0)
        if fill_count:
            width = constraints.require_width("HStack with Fill children")
        return constraints.clamp(Size(width, height))

    def render(self, ctx: RenderContext, canvas: Image.Image, rect: Rect) -> None:
        """Assign horizontal child rectangles and render each child.

        Args:
            ctx: Shared render context.
            canvas: Destination image.
            rect: Assigned stack rectangle.
        """

        _draw_debug(ctx, canvas, rect, "hstack")
        child_rects = _stack_layout(
            ctx, self.children, rect, self.gap, "horizontal", self.align
        )
        for child, child_rect in zip(self.children, child_rects):
            child.render(ctx, canvas, child_rect)


@dataclass(frozen=True)
class Grid:
    """Track-based grid layout.

    Attributes:
        children: Components placed row-major into grid cells.
        columns: Column count or explicit column track sizing tokens.
        rows: Optional row count or explicit row track sizing tokens.
        column_track: Default track used when ``columns`` is an integer.
        row_track: Default track used when rows are inferred or integer-based.
        gap: Single gap or ``(column_gap, row_gap)`` tuple.
    """

    children: Sequence[Component] = field(default_factory=tuple)
    columns: int | Sequence[SizeValue] = 1
    rows: int | Sequence[SizeValue] | None = None
    column_track: SizeValue = field(default_factory=Fit)
    row_track: SizeValue = field(default_factory=Fit)
    gap: int | tuple[int, int] = 0

    def measure(self, ctx: RenderContext, constraints: Constraints) -> Size:
        """Resolve grid tracks and return the grid's total size.

        Args:
            ctx: Shared render context.
            constraints: Parent-provided measurement bounds.

        Returns:
            Grid size including track gaps.
        """

        col_tracks, row_tracks = self._tracks()
        col_gap, row_gap = _gap_xy(self.gap)
        col_widths = _resolve_tracks(
            ctx,
            self.children,
            col_tracks,
            constraints.max_width,
            col_gap,
            axis="columns",
            column_count=len(col_tracks),
        )
        row_heights = _resolve_tracks(
            ctx,
            self.children,
            row_tracks,
            constraints.max_height,
            row_gap,
            axis="rows",
            column_count=len(col_tracks),
        )
        return constraints.clamp(
            Size(
                sum(col_widths) + col_gap * max(0, len(col_widths) - 1),
                sum(row_heights) + row_gap * max(0, len(row_heights) - 1),
            )
        )

    def render(self, ctx: RenderContext, canvas: Image.Image, rect: Rect) -> None:
        """Render children into row-major grid cells.

        Args:
            ctx: Shared render context.
            canvas: Destination image.
            rect: Assigned grid rectangle.
        """

        _draw_debug(ctx, canvas, rect, "grid")
        col_tracks, row_tracks = self._tracks()
        col_gap, row_gap = _gap_xy(self.gap)
        logical_width = ctx.unscale_px(rect.width)
        logical_height = ctx.unscale_px(rect.height)
        col_widths = _resolve_tracks(
            ctx,
            self.children,
            col_tracks,
            logical_width,
            col_gap,
            axis="columns",
            column_count=len(col_tracks),
        )
        row_heights = _resolve_tracks(
            ctx,
            self.children,
            row_tracks,
            logical_height,
            row_gap,
            axis="rows",
            column_count=len(col_tracks),
        )
        col_widths = [ctx.scale_px(width) for width in col_widths]
        row_heights = [ctx.scale_px(height) for height in row_heights]
        col_gap = ctx.scale_px(col_gap)
        row_gap = ctx.scale_px(row_gap)
        y = rect.y
        for row_index, row_h in enumerate(row_heights):
            x = rect.x
            for col_index, col_w in enumerate(col_widths):
                child_index = row_index * len(col_widths) + col_index
                if child_index < len(self.children):
                    self.children[child_index].render(
                        ctx, canvas, Rect(x, y, col_w, row_h)
                    )
                x += col_w + col_gap
            y += row_h + row_gap

    def _tracks(self) -> tuple[list[SizeValue], list[SizeValue]]:
        """Return concrete column and row track token lists.

        Returns:
            ``(column_tracks, row_tracks)`` after expanding integer counts.
        """

        if isinstance(self.columns, int):
            col_count = self.columns
            col_tracks = [self.column_track for _ in range(col_count)]
        else:
            col_tracks = list(self.columns)
            col_count = len(col_tracks)
        if col_count <= 0:
            raise LayoutError("Grid requires at least one column")

        if self.rows is None:
            row_count = ceil(len(self.children) / col_count) if self.children else 0
            row_tracks = [self.row_track for _ in range(row_count)]
        elif isinstance(self.rows, int):
            row_tracks = [self.row_track for _ in range(self.rows)]
        else:
            row_tracks = list(self.rows)
        return col_tracks, row_tracks


@dataclass(frozen=True)
class Overlay:
    """Overlay layout that renders children into the same parent rectangle.

    Attributes:
        children: Components rendered in order, later children on top.
        align_x: Horizontal alignment for each child.
        align_y: Vertical alignment for each child.
    """

    children: Sequence[Component] = field(default_factory=tuple)
    align_x: Align = "center"
    align_y: Align = "center"

    def measure(self, ctx: RenderContext, constraints: Constraints) -> Size:
        """Measure to the maximum child width and height.

        Args:
            ctx: Shared render context.
            constraints: Parent-provided measurement bounds.

        Returns:
            Overlay size.
        """

        sizes = [ctx.measure(child, constraints) for child in self.children]
        return constraints.clamp(
            Size(
                max((size.width for size in sizes), default=0),
                max((size.height for size in sizes), default=0),
            )
        )

    def render(self, ctx: RenderContext, canvas: Image.Image, rect: Rect) -> None:
        """Render each child inside the same assigned rectangle.

        Args:
            ctx: Shared render context.
            canvas: Destination image.
            rect: Assigned overlay rectangle.
        """

        _draw_debug(ctx, canvas, rect, "overlay")
        for child in self.children:
            size = _measure_child_for_render(ctx, child, rect.width, rect.height)
            child_w = (
                rect.width if self.align_x == "stretch" else min(size.width, rect.width)
            )
            child_h = (
                rect.height
                if self.align_y == "stretch"
                else min(size.height, rect.height)
            )
            child.render(
                ctx,
                canvas,
                Rect(
                    rect.x + _align_offset(rect.width, child_w, self.align_x),
                    rect.y + _align_offset(rect.height, child_h, self.align_y),
                    child_w,
                    child_h,
                ),
            )


def _resolve_optional_axis(
    value: SizeValue, bound: int | None, owner: str
) -> int | None:
    """Resolve a frame axis where Fit means intrinsic child sizing.

    Args:
        value: Sizing token for the axis.
        bound: Parent maximum for the axis.
        owner: Name used in layout error messages.

    Returns:
        Pixel size, or ``None`` when the axis should fit its child.
    """

    if isinstance(value, Fit):
        return None
    return _resolve_axis(value, bound, owner)


def _resolve_axis(value: SizeValue, bound: int | None, owner: str) -> int:
    """Resolve a sizing token on a concrete axis.

    Args:
        value: Sizing token to resolve.
        bound: Parent maximum for the axis.
        owner: Name used in layout error messages.

    Returns:
        Resolved pixel size.
    """

    if isinstance(value, Fit):
        return 0
    if isinstance(value, Fixed):
        return value.value
    if isinstance(value, Fill):
        if bound is None:
            raise LayoutError(f"{owner} uses Fill(), but parent axis is unbounded")
        return bound
    if isinstance(value, Fraction):
        if bound is None:
            raise LayoutError(f"{owner} uses Fraction(), but parent axis is unbounded")
        return round(bound * value.value)
    raise TypeError(f"unsupported size value for {owner}: {value!r}")


def _apply_max(size: Size, max_width: int | None, max_height: int | None) -> Size:
    """Apply optional width and height caps.

    Args:
        size: Input size.
        max_width: Optional width cap.
        max_height: Optional height cap.

    Returns:
        Capped size.
    """

    return Size(
        size.width if max_width is None else min(size.width, max_width),
        size.height if max_height is None else min(size.height, max_height),
    )


def _apply_aspect(size: Size, aspect_ratio: float | None) -> Size:
    """Shrink one axis until the size satisfies the requested aspect ratio.

    Args:
        size: Input size.
        aspect_ratio: Optional ``width / height`` ratio.

    Returns:
        Aspect-corrected size.
    """

    if aspect_ratio is None or size.width == 0 or size.height == 0:
        return size
    if size.width / size.height > aspect_ratio:
        return Size(round(size.height * aspect_ratio), size.height)
    return Size(size.width, round(size.width / aspect_ratio))


def _align_offset(available: int, actual: int, align: Align) -> int:
    """Compute the offset needed to align a child within available space.

    Args:
        available: Parent axis length.
        actual: Child axis length.
        align: Alignment mode.

    Returns:
        Pixel offset from the start of the parent axis.
    """

    if align in ("start", "stretch"):
        return 0
    if align == "center":
        return max(0, (available - actual) // 2)
    if align == "end":
        return max(0, available - actual)
    raise ValueError(f"unsupported alignment: {align}")


def _measure_stack_children(
    ctx: RenderContext,
    constraints: Constraints,
    children: Sequence[Component],
    axis: Literal["horizontal", "vertical"],
    gap: int,
) -> tuple[list[Size], int]:
    """Measure stack children before final rect assignment.

    Args:
        ctx: Shared render context.
        constraints: Parent-provided measurement bounds.
        children: Stack children.
        axis: Main stack axis.
        gap: Gap between children.

    Returns:
        Pair of measured child sizes and number of Fill children.
    """

    sizes: list[Size] = []
    fill_count = 0
    for child in children:
        child_constraints = constraints
        axis_value = _component_axis_size_value(child, axis)
        if isinstance(axis_value, Fill):
            sizes.append(ctx.measure(child, child_constraints))
            fill_count += 1
            continue
        sizes.append(ctx.measure(child, child_constraints))
    if fill_count:
        if axis == "vertical":
            constraints.require_height("VStack with Fill children")
        else:
            constraints.require_width("HStack with Fill children")
    return sizes, fill_count


def _stack_layout(
    ctx: RenderContext,
    children: Sequence[Component],
    rect: Rect,
    gap: int,
    axis: Literal["horizontal", "vertical"],
    cross_align: Align,
) -> list[Rect]:
    """Assign child rects after fixed, fraction, and gap space are reserved.

    Args:
        ctx: Shared render context.
        children: Stack children.
        rect: Assigned stack rectangle.
        gap: Gap between children.
        axis: Main stack axis.
        cross_align: Alignment on the opposite axis.

    Returns:
        Render rectangles matching ``children`` order.
    """

    fixed_sizes: list[Size | None] = []
    fill_indices: list[int] = []
    gap = ctx.scale_px(gap)
    gaps = gap * max(0, len(children) - 1)
    main_bound = rect.height if axis == "vertical" else rect.width

    for index, child in enumerate(children):
        axis_value = _component_axis_size_value(child, axis)
        fraction_size = None
        fill_axis = isinstance(axis_value, Fill)
        if isinstance(axis_value, Fraction):
            fraction_size = round((main_bound - gaps) * axis_value.value)

        if fill_axis:
            fill_indices.append(index)
            fixed_sizes.append(None)
        elif fraction_size is not None:
            if axis == "vertical":
                fixed_sizes.append(Size(rect.width, fraction_size))
            else:
                fixed_sizes.append(Size(fraction_size, rect.height))
        else:
            size = _measure_child_for_render(ctx, child, rect.width, rect.height)
            fixed_sizes.append(size)

    used = gaps
    for size in fixed_sizes:
        if size is not None:
            used += size.height if axis == "vertical" else size.width
    fill_size = max(0, (main_bound - used) // len(fill_indices)) if fill_indices else 0

    output: list[Rect] = []
    cursor = rect.y if axis == "vertical" else rect.x
    for index, child in enumerate(children):
        size = fixed_sizes[index]
        if size is None:
            main = fill_size
            cross = rect.width if axis == "vertical" else rect.height
        else:
            main = size.height if axis == "vertical" else size.width
            cross = size.width if axis == "vertical" else size.height
        if axis == "vertical":
            child_w = rect.width if cross_align == "stretch" else min(cross, rect.width)
            output.append(
                Rect(
                    rect.x + _align_offset(rect.width, child_w, cross_align),
                    cursor,
                    child_w,
                    main,
                )
            )
        else:
            child_h = (
                rect.height if cross_align == "stretch" else min(cross, rect.height)
            )
            output.append(
                Rect(
                    cursor,
                    rect.y + _align_offset(rect.height, child_h, cross_align),
                    main,
                    child_h,
                )
            )
        cursor += main + gap
    return output


def _scale_insets(ctx: RenderContext, value: InsetsLike | None) -> Insets:
    """Scale logical insets into current render pixels."""

    return ctx.scale_insets(as_insets(value))


def _measure_child_for_render(
    ctx: RenderContext,
    child: Component,
    max_width: int | None,
    max_height: int | None,
) -> Size:
    """Measure a child in logical pixels, then scale for render rect assignment."""

    logical_constraints = ctx.unscale_constraints(
        Constraints(max_width=max_width, max_height=max_height)
    )
    return ctx.scale_size(ctx.measure(child, logical_constraints))


def _component_axis_size_value(
    child: Component,
    axis: Literal["horizontal", "vertical"],
) -> SizeValue:
    """Read width/height sizing from any component that exposes those fields.

    Args:
        child: Component to inspect.
        axis: Axis whose sizing token should be read.

    Returns:
        The component's sizing token, or Fit when no axis field exists.
    """

    attr = "width" if axis == "horizontal" else "height"
    explicit = getattr(child, attr, None)
    if explicit is not None:
        return as_size_value(explicit)

    if isinstance(child, (HStack, VStack)):
        for nested_child in child.children:
            if isinstance(_component_axis_size_value(nested_child, axis), Fill):
                return Fill()

    return Fit()


def _resolve_tracks(
    ctx: RenderContext,
    children: Sequence[Component],
    tracks: Sequence[SizeValue],
    bound: int | None,
    gap: int,
    axis: Literal["columns", "rows"],
    column_count: int | None = None,
) -> list[int]:
    """Resolve grid track sizes.

    Args:
        ctx: Shared render context.
        children: Grid children.
        tracks: Track sizing tokens.
        bound: Parent maximum for the track axis.
        gap: Gap between tracks.
        axis: Track direction being resolved.
        column_count: Column count, needed when resolving row fit tracks.

    Returns:
        Pixel sizes for each track.
    """

    if not tracks:
        return []
    usable_bound = (
        None if bound is None else max(0, bound - gap * max(0, len(tracks) - 1))
    )
    sizes = [0 for _ in tracks]
    fill_indices: list[int] = []
    used = 0

    for index, track in enumerate(tracks):
        if isinstance(track, Fill):
            fill_indices.append(index)
        elif isinstance(track, Fit):
            sizes[index] = _fit_track_size(ctx, children, axis, index, column_count)
            used += sizes[index]
        else:
            sizes[index] = _resolve_axis(
                track, usable_bound, f"Grid {axis} track {index}"
            )
            used += sizes[index]

    if fill_indices:
        if usable_bound is None:
            raise LayoutError(f"Grid {axis} use Fill(), but parent axis is unbounded")
        fill_size = max(0, (usable_bound - used) // len(fill_indices))
        for index in fill_indices:
            sizes[index] = fill_size
    return sizes


def _fit_track_size(
    ctx: RenderContext,
    children: Sequence[Component],
    axis: Literal["columns", "rows"],
    index: int,
    column_count: int | None,
) -> int:
    """Compute a Fit track size from the largest child in that track.

    Args:
        ctx: Shared render context.
        children: Grid children.
        axis: Track direction being resolved.
        index: Track index.
        column_count: Column count, needed to map child indices to rows.

    Returns:
        Intrinsic pixel size for the fit track.
    """

    sizes: list[int] = []
    for child_index, child in enumerate(children):
        if axis == "columns":
            if column_count is None or child_index % column_count != index:
                continue
        else:
            if column_count is None or child_index // column_count != index:
                continue
        measured = ctx.measure(child, Constraints())
        sizes.append(measured.width if axis == "columns" else measured.height)
    return max(sizes, default=0)


def _gap_xy(gap: int | tuple[int, int]) -> tuple[int, int]:
    """Normalize grid gap input.

    Args:
        gap: Single gap value or ``(column_gap, row_gap)`` tuple.

    Returns:
        ``(column_gap, row_gap)``.
    """

    if isinstance(gap, tuple):
        return gap
    return gap, gap


def _draw_debug(
    ctx: RenderContext, canvas: Image.Image, rect: Rect, label: str
) -> None:
    """Draw a debug outline for a layout rectangle.

    Args:
        ctx: Shared render context.
        canvas: Destination image.
        rect: Rectangle to outline.
        label: Text label drawn near the rectangle origin.
    """

    if not ctx.debug:
        return
    draw = ImageDraw.Draw(canvas)
    width = max(1, ctx.scale_px(1))
    draw.rectangle(
        (rect.x, rect.y, rect.right - width, rect.bottom - width),
        outline=(255, 0, 0, 180),
        width=width,
    )
    draw.text(
        (rect.x + ctx.scale_px(2), rect.y + ctx.scale_px(2)),
        label,
        fill=(255, 0, 0, 180),
    )
