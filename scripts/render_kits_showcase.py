"""Render a visual showcase of every registered render kit.

The detailed page for one kit intentionally exercises the same factories that
the production renderers use:

* the shared atoms: background, text, image, panel, and separator;
* kit-specific headers and controls when a kit publishes them; and
* the Tier A surfaces implemented by the kit: game identity, player card, and
  pull reveal.

With ``--kit all`` the script also creates one contact sheet containing all
registered kits.  That makes the theme differences easy to compare while the
individual pages remain available for close visual inspection.

Examples::

    uv run python scripts/render_kits_showcase.py
    uv run python scripts/render_kits_showcase.py --kit kasumi
    uv run python scripts/render_kits_showcase.py --kit all --output-dir .cache/render-kits
"""

from __future__ import annotations

import argparse
import math
import sys
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

from PIL import Image
from PIL import ImageDraw
from PIL import ImageFont

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from plugins.render import AutoPage
from plugins.render import BaseKit
from plugins.render import Component
from plugins.render import Fill
from plugins.render import Fixed
from plugins.render import Frame
from plugins.render import Grid
from plugins.render import HStack
from plugins.render import Insets
from plugins.render import PlayerIdentity
from plugins.render import PullRevealItem
from plugins.render import Spacer
from plugins.render import VStack
from plugins.render import RenderContext
from plugins.render.kits import KIT_DISPLAY_NAMES
from plugins.render.kits import KITS
from plugins.render.kits.fonts import CHINESE_FONT
from plugins.render.primitives import load_font


DEFAULT_OUTPUT_DIR = ROOT / ".cache" / "render-kits"
PAGE_WIDTH = 960
PAGE_PADDING = 48
CARD_GAP = 18


@dataclass(frozen=True)
class ShowcaseArt:
    """Deterministic art fixtures used by every kit in the showcase."""

    avatar: Image.Image
    frame: Image.Image
    title_primary: Image.Image
    title_secondary: Image.Image
    standing: Image.Image


def _rgba_gradient(
    size: tuple[int, int],
    top: tuple[int, int, int, int],
    bottom: tuple[int, int, int, int],
) -> Image.Image:
    """Create a small vertical RGBA gradient without relying on a theme."""

    width, height = size
    canvas = Image.new("RGBA", size)
    pixels = canvas.load()
    denominator = max(1, height - 1)
    for y in range(height):
        ratio = y / denominator
        color = tuple(
            round(top[channel] + (bottom[channel] - top[channel]) * ratio)
            for channel in range(4)
        )
        for x in range(width):
            pixels[x, y] = color
    return canvas


def _font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    """Load the project's CJK font for the generated art labels."""

    return load_font(size, CHINESE_FONT)


def _make_art() -> ShowcaseArt:
    """Build colourful but generic art so the showcase has no live-data input."""

    avatar = _rgba_gradient((256, 256), (103, 72, 174, 255), (244, 119, 132, 255))
    avatar_draw = ImageDraw.Draw(avatar)
    avatar_draw.ellipse((38, 30, 218, 210), fill=(255, 231, 196, 255))
    avatar_draw.ellipse((72, 72, 98, 104), fill=(62, 48, 89, 255))
    avatar_draw.ellipse((158, 72, 184, 104), fill=(62, 48, 89, 255))
    avatar_draw.arc((88, 92, 168, 168), start=15, end=165, fill=(239, 91, 108, 255), width=8)
    avatar_draw.polygon(((24, 235), (128, 178), (232, 235)), fill=(246, 194, 92, 255))

    frame = Image.new("RGBA", (256, 256), (255, 255, 255, 0))
    frame_draw = ImageDraw.Draw(frame)
    frame_draw.rounded_rectangle((8, 8, 247, 247), radius=42, outline=(255, 250, 173, 255), width=9)
    frame_draw.rounded_rectangle((20, 20, 235, 235), radius=34, outline=(255, 255, 255, 205), width=3)
    frame_draw.polygon(((128, 2), (138, 22), (118, 22)), fill=(255, 250, 173, 255))
    frame_draw.polygon(((254, 128), (234, 138), (234, 118)), fill=(255, 250, 173, 255))

    standing = _rgba_gradient((300, 420), (42, 39, 94, 255), (220, 83, 134, 255))
    standing_draw = ImageDraw.Draw(standing)
    standing_draw.polygon(((0, 420), (62, 120), (130, 244), (204, 80), (300, 420)), fill=(255, 190, 150, 255))
    standing_draw.ellipse((88, 52, 210, 174), fill=(255, 231, 196, 255))
    standing_draw.polygon(((62, 112), (122, 26), (214, 78), (212, 138), (162, 105), (116, 145)), fill=(85, 58, 136, 255))
    standing_draw.line((110, 210, 62, 370), fill=(255, 255, 255, 180), width=13)
    standing_draw.line((190, 206, 246, 370), fill=(255, 255, 255, 180), width=13)
    standing_draw.text((20, 20), "STARB EAT", font=_font(20), fill=(255, 255, 255, 220))

    def title_art(text: str, fill: tuple[int, int, int, int]) -> Image.Image:
        image = Image.new("RGBA", (220, 48), (255, 255, 255, 0))
        draw = ImageDraw.Draw(image)
        draw.rounded_rectangle((1, 1, 218, 46), radius=14, fill=fill)
        draw.text((110, 24), text, font=_font(19), fill=(255, 255, 255, 255), anchor="mm")
        return image

    return ShowcaseArt(
        avatar=avatar,
        frame=frame,
        title_primary=title_art("星星在跳动", (239, 91, 108, 255)),
        title_secondary=title_art("舞台中央", (103, 72, 174, 255)),
        standing=standing,
    )


def _accent(kit: BaseKit):
    """Return the strongest available accent without assuming every kit has one."""

    return getattr(kit, "accent", getattr(kit, "primary", kit.text_color))


def _overrides(kit: BaseKit, method_name: str) -> bool:
    """Tell whether a kit provides a concrete implementation of a base surface."""

    base_method = getattr(BaseKit, method_name, None)
    actual_method = getattr(type(kit), method_name, None)
    return actual_method is not None and actual_method is not base_method


def _label(kit: BaseKit, text: str, *, color=None, size: int = 18) -> Component:
    return kit.text(
        text,
        font_size=size,
        color=color or kit.muted_text_color,
        wrap=False,
        max_lines=1,
    )


def _labelled_atom(
    kit: BaseKit,
    name: str,
    child: Component,
    *,
    width: int,
    height: int,
) -> Component:
    """Put one atom in a consistent labelled specimen card."""

    return kit.panel(
        VStack(
            [
                _label(kit, name, size=16),
                Frame(child, width=Fill(), height=Fill(), align_x="center", align_y="center"),
            ],
            gap=8,
            align="stretch",
        ),
        width=Fixed(width),
        height=Fixed(height),
        padding=Insets.only(left=14, top=12, right=14, bottom=12),
    )


def _section(
    kit: BaseKit,
    index: str,
    title: str,
    child: Component,
    *,
    width: int,
) -> Component:
    """Create a section with a readable section marker."""

    heading = HStack(
        [
            _label(kit, index, color=_accent(kit), size=18),
            _label(kit, title, color=kit.text_color, size=24),
            Spacer(width=Fill()),
        ],
        gap=10,
        align="center",
    )
    return kit.panel(
        VStack([heading, child], gap=16, align="stretch"),
        width=Fixed(width),
        padding=Insets.only(left=22, top=18, right=22, bottom=22),
    )


def _atoms(kit: BaseKit, art: ShowcaseArt, *, width: int) -> Component:
    """Use every neutral BaseKit atom in one row."""

    columns = 4
    gap = 12
    cell_width = (width - gap * (columns - 1)) // columns
    separator = Frame(
        kit.separator(length=Fixed(max(80, cell_width - 28)), thickness=3),
        width=Fill(),
        height=Fixed(32),
        align_x="center",
        align_y="center",
    )
    image = kit.image(
        art.avatar,
        width=Fixed(82),
        height=Fixed(82),
        fit="cover",
        radius=18,
    )
    return Grid(
        children=[
            _labelled_atom(
                kit,
                "TEXT",
                kit.text("组件文字 / Text", font_size=22, wrap=False, max_lines=1),
                width=cell_width,
                height=132,
            ),
            _labelled_atom(kit, "IMAGE", image, width=cell_width, height=132),
            _labelled_atom(
                kit,
                "PANEL",
                kit.panel(
                    kit.text("Surface", font_size=20, wrap=False, max_lines=1),
                    width=Fixed(max(110, cell_width - 48)),
                    height=Fixed(52),
                    padding=12,
                ),
                width=cell_width,
                height=132,
            ),
            _labelled_atom(kit, "SEPARATOR", separator, width=cell_width, height=132),
        ],
        columns=columns,
        column_track=Fixed(cell_width),
        row_track=Fixed(132),
        gap=gap,
    )


def _custom_components(kit: BaseKit, art: ShowcaseArt, *, width: int) -> Component | None:
    """Build every public, theme-specific component factory when available."""

    pieces: list[Component] = []

    if callable(getattr(kit, "board_frame", None)):
        pieces.append(
            _labelled_atom(
                kit,
                "BOARD FRAME",
                kit.board_frame(
                    kit.image(art.avatar, width=Fixed(100), height=Fixed(100), fit="cover"),
                    width=Fixed(132),
                    height=Fixed(132),
                    padding=10,
                ),
                width=width,
                height=176,
            )
        )
    if callable(getattr(kit, "title_pill", None)):
        pieces.append(
            _labelled_atom(
                kit,
                "TITLE PILL",
                kit.title_pill("RENDER KITS", "component catalog", pill_width=500, pill_height=57),
                width=width,
                height=148,
            )
        )
    if callable(getattr(kit, "titled_panel", None)):
        pieces.append(
            _labelled_atom(
                kit,
                "TITLED PANEL",
                kit.titled_panel(
                    "SURFACES",
                    kit.text("A named panel with a themed title rail.", font_size=20),
                    title_width=Fixed(width - 32),
                    title_height=Fixed(48),
                    main_width=Fixed(width - 32),
                    main_height=Fixed(78),
                    title_font_size=22,
                ),
                width=width,
                height=166,
            )
        )
    if callable(getattr(kit, "pill", None)):
        pieces.append(
            _labelled_atom(
                kit,
                "PILL",
                kit.pill("ACTIVE", width=Fixed(150), height=Fixed(42), font_size=22),
                width=width,
                height=96,
            )
        )
    if callable(getattr(kit, "game_title", None)):
        pieces.append(
            _labelled_atom(
                kit,
                "GAME TITLE",
                kit.game_title("星之鼓动", "KASUMI / STARBEAT", width=width - 32, height=112),
                width=width,
                height=154,
            )
        )
    if callable(getattr(kit, "article_header", None)):
        pieces.append(
            _labelled_atom(
                kit,
                "ARTICLE HEADER",
                kit.article_header("COMPONENT CATALOG", width=width - 32, detail="12 KITS"),
                width=width,
                height=104,
            )
        )
    if callable(getattr(kit, "compact_header", None)):
        pieces.append(
            _labelled_atom(
                kit,
                "COMPACT HEADER",
                kit.compact_header("LIVE PREVIEW", "all atoms rendered", width=width - 32),
                width=width,
                height=104,
            )
        )
    if callable(getattr(kit, "panel_heading", None)):
        pieces.append(
            _labelled_atom(
                kit,
                "PANEL HEADING",
                kit.panel_heading("SIGNATURE COMPONENTS", width=width - 32),
                width=width,
                height=86,
            )
        )

    if not pieces:
        return None
    return VStack(pieces, gap=12, align="stretch")


def _identity(art: ShowcaseArt) -> PlayerIdentity:
    return PlayerIdentity(
        nickname="香澄 · Showcase",
        level=42,
        avatar=art.avatar,
        avatar_frame=art.frame,
    )


def _pulls(art: ShowcaseArt) -> tuple[PullRevealItem, ...]:
    names = ("星光序曲", "舞台练习", "闪耀和弦", "夜空回响", "星之鼓动")
    rarities = (2, 3, 4, 5, 6)
    return tuple(
        PullRevealItem(
            name=name,
            rarity=rarity,
            is_new=index in (0, 4),
            featured=index == 4,
            image=art.standing,
            note="NEW" if index == 0 else "PICK UP" if index == 4 else "",
        )
        for index, (name, rarity) in enumerate(zip(names, rarities, strict=True))
    )


def _surface_placeholder(kit: BaseKit, method_name: str, *, width: int) -> Component:
    """Show the contract status for kits that intentionally use the fallback."""

    return kit.panel(
        VStack(
            [
                _label(kit, method_name.upper(), color=_accent(kit), size=16),
                kit.text(
                    "BaseKit contract is not overridden by this theme.",
                    font_size=20,
                    color=kit.muted_text_color,
                    max_lines=2,
                ),
            ],
            gap=8,
            align="start",
        ),
        width=Fixed(width),
        height=Fixed(88),
        padding=14,
    )


def _tier_a(kit: BaseKit, art: ShowcaseArt, *, width: int) -> Component:
    """Render all Tier A surfaces the concrete kit owns."""

    identity = _identity(art)
    pieces: list[Component] = []
    if _overrides(kit, "game_identity"):
        pieces.append(
            _labelled_atom(
                kit,
                "GAME IDENTITY",
                kit.game_identity(identity, width=width, detail="SHOWCASE / 2026"),
                width=width,
                height=126,
            )
        )
    else:
        pieces.append(_surface_placeholder(kit, "game_identity", width=width))

    if _overrides(kit, "player_card"):
        pieces.append(
            _labelled_atom(
                kit,
                "PLAYER CARD",
                kit.player_card(
                    avatar_image=art.avatar,
                    frame_image=art.frame,
                    title1_image=art.title_primary,
                    title2_image=art.title_secondary,
                    nickname="香澄 · Showcase",
                    level=42,
                    current_pt=2350,
                    description="把整个 render kit 放进一个页面，方便逐个检查层次、边框、字体与图像槽位。",
                    width=width - 32,
                    height=420,
                    standing_art=art.standing,
                ),
                width=width,
                height=500,
            )
        )
    else:
        pieces.append(_surface_placeholder(kit, "player_card", width=width))

    if _overrides(kit, "pull_reveal"):
        pieces.append(
            _labelled_atom(
                kit,
                "PULL REVEAL",
                kit.pull_reveal(_pulls(art), width=width - 32),
                width=width,
                height=410,
            )
        )
    else:
        pieces.append(_surface_placeholder(kit, "pull_reveal", width=width))

    return VStack(pieces, gap=12, align="stretch")


def build_showcase_page(
    kit_name: str,
    *,
    width: int = PAGE_WIDTH,
    pixel_ratio: int = 2,
) -> Image.Image:
    """Render one complete component page for ``kit_name``."""

    if kit_name not in KITS:
        raise ValueError(f"unknown kit: {kit_name}")

    kit = KITS[kit_name]()
    art = _make_art()
    content_width = width - PAGE_PADDING * 2
    custom = _custom_components(kit, art, width=content_width)

    intro = kit.panel(
        VStack(
            [
                kit.page_title("RENDER KITS", font_size=54),
                kit.text(
                    f"{KIT_DISPLAY_NAMES.get(kit_name, kit_name)}  ·  {kit_name}",
                    font_size=24,
                    color=kit.muted_text_color,
                    wrap=False,
                    max_lines=1,
                ),
                kit.text(
                    "One interface / every component specimen",
                    font_size=20,
                    color=_accent(kit),
                    wrap=False,
                    max_lines=1,
                ),
            ],
            gap=8,
            align="start",
        ),
        width=Fixed(content_width),
        padding=Insets.only(left=26, top=24, right=26, bottom=24),
    )

    sections: list[Component] = [
        intro,
        _section(
            kit,
            "01",
            "CORE ATOMS",
            _atoms(kit, art, width=content_width - 44),
            width=content_width,
        ),
    ]
    if custom is not None:
        sections.append(
            _section(
                kit,
                "02",
                "KIT SIGNATURES",
                custom,
                width=content_width,
            )
        )
        tier_index = "03"
    else:
        tier_index = "02"
    sections.append(
        _section(
            kit,
            tier_index,
            "TIER A SURFACES",
            _tier_a(kit, art, width=content_width - 44),
            width=content_width,
        )
    )

    content = VStack(sections, gap=24, align="stretch")
    return AutoPage(
        content,
        background=kit.background(),
        padding=Insets.all(PAGE_PADDING),
        min_width=width,
        max_width=width,
    ).render(RenderContext(pixel_ratio=pixel_ratio))


def _contact_font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    try:
        return ImageFont.truetype(str(CHINESE_FONT), size)
    except OSError:
        return ImageFont.load_default()


def _contact_sheet(
    pages: Iterable[tuple[str, Image.Image]],
    *,
    output: Path,
    columns: int = 3,
) -> Path:
    """Compose all detailed pages into one overview interface."""

    entries = list(pages)
    if not entries:
        raise ValueError("cannot create an empty contact sheet")

    margin = 34
    gap = 22
    title_height = 76
    tile_width = 420
    thumbnail_width = tile_width - 28
    thumbnails: list[tuple[str, Image.Image]] = []
    for name, page in entries:
        ratio = thumbnail_width / page.width
        thumbnail = page.resize(
            (thumbnail_width, max(1, round(page.height * ratio))),
            Image.Resampling.LANCZOS,
        )
        thumbnails.append((name, thumbnail))
    tile_heights = [image.height + 54 for _, image in thumbnails]
    rows = math.ceil(len(thumbnails) / columns)
    row_heights = [
        max(tile_heights[row * columns : (row + 1) * columns])
        for row in range(rows)
    ]
    sheet = Image.new(
        "RGBA",
        (
            margin * 2 + columns * tile_width + (columns - 1) * gap,
            title_height + margin + sum(row_heights) + (rows - 1) * gap + margin,
        ),
        (244, 245, 249, 255),
    )
    draw = ImageDraw.Draw(sheet)
    draw.text(
        (margin, 24),
        "RENDER KITS / COMPONENT SHOWCASE",
        font=_contact_font(28),
        fill=(35, 39, 52, 255),
    )
    draw.text(
        (margin, 51),
        f"{len(entries)} registered themes · one interface · generated locally",
        font=_contact_font(16),
        fill=(105, 110, 125, 255),
    )

    for index, (name, thumbnail) in enumerate(thumbnails):
        row, column = divmod(index, columns)
        x = margin + column * (tile_width + gap)
        y = title_height + margin + sum(row_heights[:row]) + row * gap
        tile_height = thumbnail.height + 54
        draw.rounded_rectangle(
            (x, y, x + tile_width - 1, y + tile_height - 1),
            radius=18,
            fill=(255, 255, 255, 255),
            outline=(220, 224, 232, 255),
            width=2,
        )
        sheet.alpha_composite(thumbnail, (x + 14, y + 12))
        draw.text(
            (x + 16, y + thumbnail.height + 18),
            KIT_DISPLAY_NAMES.get(name, name),
            font=_contact_font(18),
            fill=(35, 39, 52, 255),
        )

    output.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(output)
    return output


def _render_pages(
    kit_names: Iterable[str],
    *,
    output_dir: Path,
    width: int,
    pixel_ratio: int,
) -> tuple[list[tuple[str, Image.Image]], list[str]]:
    output_dir.mkdir(parents=True, exist_ok=True)
    pages: list[tuple[str, Image.Image]] = []
    failures: list[str] = []
    for kit_name in kit_names:
        path = output_dir / f"render-kit-{kit_name}.png"
        try:
            page = build_showcase_page(
                kit_name,
                width=width,
                pixel_ratio=pixel_ratio,
            )
            page.save(path)
            pages.append((kit_name, page))
            print(f"OK  {path}  {page.width}x{page.height}")
        except Exception as error:  # Keep the remaining kits available for QA.
            message = f"{kit_name}: {type(error).__name__}: {error}"
            failures.append(message)
            print(f"ERR {message}")
    return pages, failures


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Render every component in the registered render kits."
    )
    parser.add_argument(
        "--kit",
        default="all",
        choices=[*sorted(KITS), "all"],
        help="One kit for a detailed page, or 'all' for all pages plus a contact sheet.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help="Directory for generated PNGs.",
    )
    parser.add_argument(
        "--width",
        type=int,
        default=PAGE_WIDTH,
        help="Logical width of each detailed page (default: 960).",
    )
    parser.add_argument(
        "--pixel-ratio",
        type=int,
        choices=(1, 2),
        default=2,
        help="Render scale before downsampling (default: 2; use 1 to disable supersampling).",
    )
    args = parser.parse_args()
    if args.width < 720:
        parser.error("--width must be at least 720px for the showcase components")

    kit_names = list(KITS) if args.kit == "all" else [args.kit]
    pages, failures = _render_pages(
        kit_names,
        output_dir=args.output_dir,
        width=args.width,
        pixel_ratio=args.pixel_ratio,
    )
    if args.kit == "all" and pages:
        contact = _contact_sheet(
            pages,
            output=args.output_dir / "render-kits-showcase.png",
        )
        print(f"SHOWCASE {contact}")
    if failures:
        print(f"{len(failures)} kit(s) failed to render:")
        for failure in failures:
            print(f"  - {failure}")
        raise SystemExit(1)


if __name__ == "__main__":
    main()
