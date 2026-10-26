"""Measured drawing tools, not a shared page template.

Each plugin adapter owns its columns, reading order and emphasis. This module
only supplies typography, rules, images and a deferred sync/async page contract.
Geometry is authored in logical pixels and painted with supersampling.
"""

from typing import Callable
from dataclasses import dataclass

from PIL import Image
from PIL import ImageDraw

from plugins.render import Rect
from plugins.render import Constraints
from plugins.render import RenderContext
from plugins.render import PlayerIdentity
from utils.image_tasks import run_image_task
from plugins.render.kits.atoms import KitImage
from plugins.render.primitives import load_font
from plugins.render.text_layout import ellipsis
from plugins.render.text_layout import wrap_text
from plugins.render.text_layout import draw_text_line
from plugins.render.text_layout import display_text_width

from ..components import INK
from ..components import ROSE
from ..components import MUTED
from ..components import SERIF
from ..components import SURFACE
from ..components import book_paper


@dataclass(frozen=True)
class Surface:
    draw: Callable
    width: int
    book: bool

    def __call__(self, sheet, *args, **kwargs):
        return self.draw(sheet, *args, **kwargs)


def surface(width=1100, *, book=False):
    return lambda draw: Surface(draw, width, book)


@dataclass(frozen=True)
class FolioPage:
    kit: object
    surface: Surface
    args: tuple
    kwargs: dict

    def compose(self, ctx=None):
        sheet = Sheet(
            self.kit, self.surface.width, ctx or RenderContext(), self.surface.book
        )
        self.surface(sheet, *self.args, **self.kwargs)
        return sheet

    def render(self, ctx=None):
        return self.compose(ctx).render()

    async def render_async(self, ctx=None, *, executor=None):
        return await run_image_task(self.render, ctx, executor=executor)


@dataclass(frozen=True)
class TextRun:
    value: str
    rect: Rect
    lines: tuple[str, ...]
    font_size: int
    align: str


class Sheet:
    def __init__(self, kit, width, ctx, book):
        self.kit, self.width, self.book = kit, width, book
        self.ctx = ctx.for_root_render().activate_pixel_ratio()
        self.ops = []
        self.texts = []
        self.blocks = []
        self.gutters = []
        self.gutter_padding = []
        self.height = 0

    def _op(self, bottom, paint):
        self.height = max(self.height, round(bottom))
        self.ops.append(paint)

    def text(
        self,
        value,
        x,
        y,
        width,
        size=24,
        color=INK,
        *,
        align="left",
        lines=None,
        leading=None,
    ):
        value = str(value)
        font = load_font(size, SERIF)
        content = wrap_text(value, font, max(1, width))
        if lines and len(content) > lines:
            content = content[:lines]
            content[-1] = ellipsis(content[-1], font, width, force=True)
        leading = leading or round(size * 1.45)
        height = leading * len(content)
        self.texts.append(
            TextRun(value, Rect(x, y, width, height), tuple(content), size, align)
        )

        def paint(canvas):
            draw = ImageDraw.Draw(canvas)
            face = load_font(self.ctx.scale_px(size), SERIF)
            for index, line in enumerate(content):
                left = self.ctx.scale_px(x)
                room = self.ctx.scale_px(width)
                draw_width = display_text_width(line, face, room)
                if align == "center":
                    left += max(0, (room - draw_width) // 2)
                elif align == "right":
                    left += max(0, room - draw_width)
                box = face.getbbox(line)
                top = self.ctx.scale_px(y + index * leading) - box[1]
                draw_text_line(draw, (left, top), line, face, color, max_width=room)

        self._op(y + height, paint)
        return y + height

    def line(self, x, y, width, color=ROSE, weight=1):
        self._op(
            y + weight,
            lambda c: ImageDraw.Draw(c).line(
                (
                    self.ctx.scale_px(x),
                    self.ctx.scale_px(y),
                    self.ctx.scale_px(x + width),
                    self.ctx.scale_px(y),
                ),
                fill=color,
                width=max(1, self.ctx.scale_px(weight)),
            ),
        )

    def box(self, x, y, width, height, fill=SURFACE, border=None, weight=1):
        self.blocks.append(("box", Rect(x, y, width, height)))
        self._op(
            y + height,
            lambda c: ImageDraw.Draw(c).rectangle(
                (
                    self.ctx.scale_px(x),
                    self.ctx.scale_px(y),
                    self.ctx.scale_px(x + width),
                    self.ctx.scale_px(y + height),
                ),
                fill=fill,
                outline=border,
                width=max(1, self.ctx.scale_px(weight)),
            ),
        )

    def image(self, source, x, y, width, height, *, fit="contain", opacity=1):
        if source is None:
            self.box(x, y, width, height, fill=(230, 218, 213, 255), border=MUTED)
            self.text(
                "暂无图像",
                x + 12,
                y + height // 2 - 16,
                width - 24,
                22,
                MUTED,
                align="center",
            )
            return y + height
        return self.component(
            KitImage(source, fit=fit, opacity=opacity), x, y, width, height
        )

    def component(self, component, x, y, width, height):
        self.blocks.append((type(component).__name__, Rect(x, y, width, height)))
        self._op(
            y + height,
            lambda c: component.render(
                self.ctx, c, self.ctx.scale_rect(Rect(x, y, width, height))
            ),
        )
        return y + height

    def title(self, title, kicker, subtitle=""):
        self.text(kicker, 52, 32, self.width - 104, 18, ROSE)
        title_component = self.kit.page_title(title, font_size=44)
        size = title_component.measure(
            RenderContext(), Constraints(max_width=self.width - 104)
        )
        self.component(title_component, 44, 68, size.width, size.height)
        bottom = 68 + size.height
        if subtitle:
            bottom = self.text(subtitle, 58, bottom + 10, self.width - 116, 22, MUTED)
        self.line(52, bottom + 22, self.width - 104, color=MUTED)
        return bottom + 46

    def section(self, label, x, y, width):
        self.text(label, x, y, width, 24, ROSE)
        self.line(x, y + 41, width, color=(161, 128, 133, 255))
        return y + 60

    def facts(self, rows, x, y, width, *, size=23, label_width=None):
        label_width = label_width or round(width * 0.42)
        for label, value in rows:
            a = self.text(label, x, y, label_width - 12, size, MUTED)
            b = self.text(
                value, x + label_width, y, width - label_width, size, align="right"
            )
            y = max(a, b) + 17
        return y

    def metric(self, label, value, x, y, width, *, size=52):
        bottom = self.text(label, x, y, width, 20, MUTED)
        return self.text(value, x, bottom + 8, width, size)

    def stamp(self, label, x, y, width, *, size=26):
        height = 60
        font = load_font(size, SERIF)
        label = ellipsis(str(label), font, width - 24)
        bounds = font.getbbox(label)
        glyph_height = bounds[3] - bounds[1]
        top = y + (height - glyph_height) // 2
        self.box(x, y, width, height, fill=None, border=ROSE, weight=2)
        self.text(label, x + 12, top, width - 24, size, ROSE, align="center", lines=1)
        return y + height

    def person(
        self, identity, x, y, width, *, avatar_size=64, font_size=27, level=True
    ):
        if identity is None:
            return y
        avatar = self.kit._avatar(
            identity.avatar, identity.nickname, avatar_size, identity.avatar_frame
        )
        size = avatar.measure(RenderContext(), Constraints())
        self.component(avatar, x, y, size.width, size.height)
        bottom = self.text(
            identity.nickname,
            x + size.width + 16,
            y + 2,
            width - size.width - 16,
            font_size,
        )
        if level and identity.level is not None:
            bottom = self.text(
                f"Lv.{identity.level}",
                x + size.width + 16,
                bottom + 3,
                width - size.width - 16,
                20,
                ROSE,
            )
        return max(y + size.height, bottom)

    def table(self, headers, rows, x, y, widths, *, size=22, highlight=()):
        total = sum(widths)
        if headers:
            self.box(x, y, total, 44, INK)
            left = x
            for header, width in zip(headers, widths, strict=True):
                self.text(header, left + 12, y + 9, width - 24, 19, SURFACE, lines=1)
                left += width
            y += 44
        for index, row in enumerate(rows):
            left, bottom = x, y
            if index in highlight:
                self.box(x, y, total, 4, ROSE)
                y += 10
            for value, width in zip(row, widths, strict=True):
                if isinstance(value, PlayerIdentity):
                    end = self.person(
                        value,
                        left + 12,
                        y + 13,
                        width - 24,
                        avatar_size=40,
                        font_size=size,
                        level=False,
                    )
                else:
                    end = self.text(value, left + 12, y + 13, width - 24, size, lines=3)
                bottom = max(bottom, end)
                left += width
            y = max(y + 54, bottom + 15)
            self.line(x, y, total, (186, 160, 160, 255))
        return y + 16

    def meter(self, value, total, x, y, width, label=""):
        ratio = max(0, min(1, value / total)) if total > 0 else 0
        self.box(x, y, width, 8, (211, 191, 191, 255))
        if ratio:
            self.box(x, y, max(1, round(width * ratio)), 8, ROSE)
        if label:
            return self.text(label, x, y + 20, width, 20, MUTED)
        return y + 8

    def gutter(self, left, right, top, bottom, *, padding=32):
        """Anchor the entire book background to the reserved column gap."""
        if right - left < padding * 2 + 12:
            raise ValueError("Book gutter needs room for its fold and padding")
        if not self.book:
            raise ValueError("Only book surfaces can request a gutter")
        if bottom <= top:
            return
        if self.gutters:
            raise ValueError("A book spread has one binding position")
        width = min(20, right - left - padding * 2)
        self.gutters.append(
            Rect(round((left + right - width) / 2), top, width, bottom - top)
        )
        self.gutter_padding.append(padding)

    @property
    def book_spine(self):
        # Full-width letters and multi-column registers use the broad right
        # leaf, with the facing page compressed into the outer margin.
        if not self.gutters:
            return 28
        gutter = self.gutters[0]
        return gutter.x + gutter.width / 2

    def gutter_conflicts(self):
        errors = []
        for gutter, padding in zip(self.gutters, self.gutter_padding, strict=True):
            for label, rect in [*self.glyph_boxes(), *self.blocks]:
                dx = min(gutter.right + padding, rect.right) - max(
                    gutter.x - padding, rect.x
                )
                dy = min(gutter.bottom, rect.bottom) - max(gutter.y, rect.y)
                if dx > 0 and dy > 0:
                    errors.append(
                        f"content too close to book gutter: {label!r} / {rect}"
                    )
        return errors

    def footer(self, text, y=None):
        y = max(self.height + 34, y or 0)
        self.line(52, y, self.width - 104, MUTED)
        bottom = self.text(text, 52, y + 18, self.width - 104, 20, MUTED)
        self.height = bottom + 48

    def render(self):
        logical_height = max(420, self.height + 24)
        from plugins.render import Size

        canvas = self.kit.background().render(
            self.ctx, self.ctx.scale_size(Size(self.width, logical_height))
        )
        if self.book:
            canvas = Image.blend(
                canvas,
                book_paper(*canvas.size, spine=self.book_spine / self.width),
                0.10,
            )
        for paint in self.ops:
            paint(canvas)
        if self.ctx.render_ratio > 1:
            canvas = canvas.resize(
                (self.width, logical_height), Image.Resampling.LANCZOS
            )
        return canvas

    def glyph_boxes(self):
        """Actual text extents for layout audits, excluding empty line boxes."""
        boxes = []
        for run in self.texts:
            face = load_font(run.font_size, SERIF)
            leading = run.rect.height // len(run.lines)
            for index, line in enumerate(run.lines):
                if not line.strip():
                    continue
                bounds = face.getbbox(line)
                width = display_text_width(line, face, run.rect.width)
                offset = (
                    max(0, (run.rect.width - width) // 2)
                    if run.align == "center"
                    else max(0, run.rect.width - width)
                    if run.align == "right"
                    else 0
                )
                boxes.append(
                    (
                        line,
                        Rect(
                            run.rect.x + offset + bounds[0],
                            run.rect.y + index * leading,
                            width,
                            bounds[3] - bounds[1],
                        ),
                    )
                )
        return boxes


def gain_rows(data):
    """Shared reward facts; each game places these in its own composition."""
    rows = []
    task = getattr(data, "task", None)
    if task:
        rows.append((f"任务 · {task.name}", f"+{task.reward} 星星贴纸"))
    elif getattr(data, "task_name", None):
        rows.append((f"任务 · {data.task_name}", f"+{data.task_reward or 0} 星星贴纸"))
    level = getattr(data, "level", None)
    old = level.old_level if level else getattr(data, "old_level", None)
    new = level.new_level if level else getattr(data, "new_level", None)
    if old is not None and new is not None and new > old:
        rows.append(("等级提升", f"Lv.{old} → Lv.{new}"))
        stickers = level.stickers if level else getattr(data, "level_stickers", 0)
        if stickers:
            rows.append(("升级奖励", f"+{stickers} 星星贴纸"))
    return rows
