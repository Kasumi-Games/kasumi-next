"""Real-kit product preview for themes sold by 流星堂."""

from dataclasses import dataclass

from PIL import Image

from utils.cards import BODY_SIZE
from utils.cards import LABEL_SIZE
from utils.cards import INNER_WIDTH
from utils.cards import badge
from utils.cards import meter
from utils.cards import stat_row
from utils.cards import card_page
from utils.cards import panel_section
from plugins.render import Fill
from plugins.render import Fixed
from plugins.render import Frame
from plugins.render import HStack
from plugins.render import VStack
from plugins.render import BaseKit
from plugins.render import AutoPage


@dataclass(frozen=True)
class ThemePreviewData:
    sku: str
    name: str
    description: str
    price: int
    balance: int
    owned: bool = False
    notice: str = ""
    footer: str = ""


def render_theme_preview(data: ThemePreviewData, kit: BaseKit) -> Image.Image:
    return theme_preview_page(data, kit).render()


def theme_preview_page(data: ThemePreviewData, kit: BaseKit) -> AutoPage:
    """Build a sample card entirely from the theme being offered."""

    sample = kit.panel(
        VStack(
            [
                HStack(
                    [
                        badge(kit, "实机", width=72, height=38, font_size=20),
                        Frame(
                            VStack(
                                [
                                    kit.text(
                                        "星光舞台 · 结算",
                                        font_size=BODY_SIZE,
                                        wrap=False,
                                        max_lines=1,
                                    ),
                                    kit.text(
                                        "下面的背景、字体、面板和进度条都来自本主题",
                                        font_size=LABEL_SIZE,
                                        color=kit.muted_text_color,
                                        wrap=False,
                                        max_lines=1,
                                        overflow="shrink",
                                    ),
                                ],
                                gap=5,
                                align="stretch",
                            ),
                            width=Fill(),
                            align_x="start",
                            align_y="center",
                        ),
                    ],
                    gap=14,
                    align="center",
                ),
                kit.separator(length=Fill()),
                stat_row(kit, "本局结果", "＋320 Pt", width=INNER_WIDTH - 48),
                stat_row(kit, "赛季排名", "第 12 名", width=INNER_WIDTH - 48),
                meter(
                    kit,
                    value=63,
                    total=90,
                    width=INNER_WIDTH - 48,
                    label="保底进度 63/90",
                ),
            ],
            gap=16,
            align="stretch",
        ),
        width=Fixed(INNER_WIDTH),
        padding=24,
    )

    surface_width = (INNER_WIDTH - 32) // 3
    surfaces = HStack(
        [
            _surface_chip(kit, "个人资料", "身份卡", surface_width),
            _surface_chip(kit, "游戏结果", "高频展示", surface_width),
            _surface_chip(kit, "排行榜", "群内可见", surface_width),
        ],
        gap=16,
        align="stretch",
    )

    status = "已拥有，可前往 /装扮 装备" if data.owned else f"{data.price} 盆栽"
    offer = kit.panel(
        VStack(
            [
                stat_row(kit, f"商品 {data.sku}", status, width=INNER_WIDTH - 48),
                kit.text(
                    data.description,
                    font_size=LABEL_SIZE,
                    color=kit.muted_text_color,
                    max_lines=2,
                    overflow="ellipsis",
                ),
            ],
            gap=10,
            align="stretch",
        ),
        width=Fixed(INNER_WIDTH),
        padding=24,
    )

    body = panel_section(
        kit,
        VStack([sample, surfaces, offer], gap=18, align="stretch"),
    )
    footer_text = data.footer or (
        f"已拥有 · /装扮 装备 {data.name}"
        if data.owned
        else f"/流星堂 购买 {data.sku} · 余额 {data.balance} 盆"
    )
    return card_page(
        kit,
        title=data.name,
        subtitle=data.notice or "流星堂主题实机预览",
        body=body,
        footer=kit.text(
            footer_text,
            font_size=LABEL_SIZE,
            wrap=False,
            max_lines=1,
            overflow="shrink",
        ),
    )


def _surface_chip(
    kit: BaseKit,
    title: str,
    detail: str,
    width: int,
):
    return kit.panel(
        VStack(
            [
                kit.text(
                    title,
                    font_size=BODY_SIZE,
                    align="center",
                    wrap=False,
                    max_lines=1,
                ),
                kit.text(
                    detail,
                    font_size=LABEL_SIZE,
                    color=kit.muted_text_color,
                    align="center",
                    wrap=False,
                    max_lines=1,
                ),
            ],
            gap=6,
            align="stretch",
        ),
        width=Fixed(width),
        padding=18,
    )
