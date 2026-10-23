"""Deliver every Manosaba kit feature and the repository's business surfaces.

    .venv/bin/python scripts/preview_manosaba.py
    .venv/bin/python scripts/preview_manosaba.py --skip-business

The business gallery uses isolated test fixtures, never the live bot database.
Output: PNGs, searchable offline HTML gallery, coverage JSON and a contact sheet.
"""

from __future__ import annotations

import sys
import html
import json
import argparse
from pathlib import Path

from PIL import Image
from PIL import ImageDraw

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from plugins.render import Fill
from plugins.render import Grid
from plugins.render import Page
from plugins.render import Fixed
from plugins.render import Frame
from plugins.render import HStack
from plugins.render import VStack
from plugins.render import AutoPage
from plugins.render import PlayerIdentity
from plugins.render import PullRevealItem
from plugins.render.primitives import load_font
from plugins.render.kits.manosaba import ManosabaKit
from plugins.render.kits.manosaba.components import INK
from plugins.render.kits.manosaba.components import PINK
from plugins.render.kits.manosaba.components import ROSE
from plugins.render.kits.manosaba.components import SERIF
from plugins.render.kits.manosaba.components import SURFACE
from plugins.render.kits.manosaba.components import RESOURCES

BUSINESS_LABELS = [
    "资料·完整",
    "资料·空状态",
    "签到",
    "签到·连签与升级",
    "等级排行榜",
    "赛季排行榜",
    "赛季趋势",
    "赛季信息",
    "装扮背包",
    "帮助总览",
    "命令详情",
    "卡池·立绘",
    "卡池·无立绘",
    "抽卡·单抽",
    "抽卡·十连",
    "抽卡记录",
    "邮箱",
    "邮箱·密集列表",
    "邮箱·空状态",
    "邮件·领取",
    "邮件·已读",
    "邮件·一键领取",
    "邮件·无可领取",
    "红包·创建",
    "红包·列表",
    "红包·空列表",
    "红包·结算",
    "红包·多人结算",
    "黑香澄·帮助",
    "黑香澄·手牌",
    "黑香澄·牌桌",
    "黑香澄·统计",
    "探险·棋盘",
    "探险·撤退结算",
    "探险·失败结算",
    "探险·统计",
    "一笔画·棋盘",
    "一笔画·排行榜",
    "一笔画·结果",
    "猜卡面·成功",
    "猜卡面·超时",
    "猜谱面·成功",
    "猜谱面·超时",
    "巡演·帮助",
    "巡演·对局",
    "巡演·结算",
    "流星堂·首页",
    "流星堂·立绘",
    "流星堂·头像框",
    "流星堂·主题",
    "流星堂·主题预览",
    "流星堂·已购主题",
    "流星堂·加抽",
    "巡演·排行榜",
]


def feature_gallery(output: Path) -> list[dict]:
    kit = ManosabaKit()
    folder = output / "features"
    folder.mkdir(parents=True, exist_ok=True)
    records = []
    ema = RESOURCES / "portrait_ema.png"
    hiro = RESOURCES / "portrait_hiro.png"

    def emit(slug, title, api, child, width=960):
        page = AutoPage(
            Frame(
                VStack(
                    [
                        kit.page_title(title),
                        child,
                    ],
                    gap=28,
                    align="stretch",
                ),
                width=width - 96,
            ),
            background=kit.background(),
            padding=48,
        )
        path = folder / f"{slug}.png"
        image = page.render()
        image.save(path)
        records.append(
            {
                "file": str(path.relative_to(output)),
                "title": title,
                "api": api,
                "group": "kit 功能",
                "size": list(image.size),
            }
        )

    emit(
        "01-background",
        "旧纸与墨迹",
        "background",
        Frame(
            HStack(
                [
                    Frame(
                        VStack(
                            [
                                kit.text("魔法少女的魔女审判", font_size=40),
                                kit.text(
                                    "MANOSABA / RENDER KIT", font_size=22, color=ROSE
                                ),
                                kit.ornament(width=320),
                                kit.text(
                                    "旧纸记下证言，墨迹划出边界。\n将原作的审判与图鉴视觉带入每一张卡片。",
                                    font_size=26,
                                ),
                                kit.text(
                                    "游戏原始素材 · Source Han Serif SC",
                                    font_size=18,
                                    color=ROSE,
                                ),
                            ],
                            gap=22,
                        ),
                        width=Fill(),
                        align_y="center",
                    ),
                    kit.portrait(ema, width=260, height=380),
                ],
                gap=24,
                align="center",
            ),
            height=500,
        ),
    )
    for name, color in [("paper", SURFACE), ("ink", INK)]:
        path = folder / f"02-background-{name}.png"
        Page(
            size=(640, 240),
            background=kit.background(fill=color),
            child=Frame(
                kit.text(
                    "自定义底色",
                    font_size=32,
                    color=INK if name == "paper" else SURFACE,
                ),
                align_x="center",
                align_y="center",
            ),
        ).render().save(path)
        records.append(
            {
                "file": str(path.relative_to(output)),
                "title": f"背景覆盖·{name}",
                "api": "background(fill=...)",
                "group": "kit 功能",
                "size": [640, 240],
            }
        )
    emit(
        "03-text",
        "文字与层级",
        "text",
        kit.panel(
            VStack(
                [
                    kit.text("魔法少女的魔女审判", font_size=48),
                    kit.text("蔷薇色的证言", font_size=32, color=ROSE),
                    kit.text("简体中文 / 日本語 / Latin 0123456789", font_size=26),
                    kit.text(
                        "每段文字都可设置字号、颜色、行高与对齐方式。", font_size=24
                    ),
                    kit.text("居中排列", font_size=26, align="center"),
                    kit.text("右侧对齐 · 2,350 Pt", font_size=26, align="right"),
                ],
                gap=18,
                align="stretch",
            ),
            padding=28,
        ),
    )
    long = "这是一段用来检查中文换行和边界的证言。长文本仍需要清楚地展示，不应压住装饰或挤出卡片。"
    emit(
        "04-text-overflow",
        "换行与边界",
        "text(wrap, max_lines, overflow, line_height)",
        VStack(
            [
                kit.panel(
                    kit.text(long, font_size=28, max_lines=3, line_height=40),
                    padding=24,
                ),
                kit.panel(
                    kit.text(long, font_size=28, wrap=False, max_lines=1), padding=24
                ),
                Frame(
                    kit.panel(
                        kit.text(
                            "SHRINK TO FIT · 0123456789",
                            font_size=52,
                            wrap=False,
                            overflow="shrink",
                        ),
                        width=560,
                        padding=24,
                    ),
                    align_x="start",
                ),
            ],
            gap=22,
            align="stretch",
        ),
    )
    emit(
        "05-images",
        "图像适配",
        "image(fit, opacity, radius)",
        Grid(
            [
                kit.panel(
                    VStack(
                        [
                            kit.text(label, font_size=22),
                            kit.image(
                                AutoPage(
                                    kit.portrait(ema, width=300, height=360)
                                ).render(),
                                width=220,
                                height=260,
                                fit=fit,
                                opacity=alpha,
                                radius=radius,
                            ),
                        ],
                        gap=12,
                    ),
                    padding=20,
                )
                for label, fit, alpha, radius in [
                    ("CONTAIN", "contain", 1, 0),
                    ("COVER", "cover", 1, 0),
                    ("STRETCH", "stretch", 1, 0),
                    ("透明度 45%", "contain", 0.45, 0),
                    ("圆角裁切", "cover", 1, 48),
                ]
            ],
            columns=3,
            column_track=Fixed(272),
            gap=18,
        ),
    )
    emit(
        "06-panels",
        "容器与边框",
        "panel(fill, radius, padding, width, height)",
        VStack(
            [
                kit.panel(kit.text("默认双线框与藤蔓花饰", font_size=28), padding=28),
                kit.panel(
                    kit.text("深色容器", font_size=28, color=SURFACE),
                    padding=28,
                    fill=INK,
                ),
                kit.panel(
                    kit.text("显式圆角 · radius=24", font_size=28),
                    padding=28,
                    radius=24,
                ),
                kit.panel(
                    kit.text("半透明容器", font_size=28),
                    padding=28,
                    fill=(255, 255, 255, 110),
                ),
            ],
            gap=20,
            align="stretch",
        ),
    )
    emit(
        "07-separators",
        "分隔与花饰",
        "separator / ornament",
        kit.panel(
            VStack(
                [
                    kit.separator(length=Fill(), thickness=2),
                    kit.separator(length=Fill(), thickness=12),
                    HStack(
                        [
                            kit.text("证言", font_size=30),
                            kit.separator(
                                orientation="vertical", length=64, thickness=2
                            ),
                            kit.text("记录", font_size=30),
                        ],
                        gap=32,
                        align="center",
                    ),
                    kit.ornament(width=560),
                ],
                gap=28,
                align="stretch",
            ),
            padding=30,
        ),
    )
    emit(
        "08-titles",
        "标题字牌",
        "page_title",
        VStack(
            [
                kit.page_title("审判记录", font_size=56),
                kit.page_title("WITCH TRIALS", font_size=44),
                Frame(kit.page_title("长标题会根据容器宽度调整并省略"), width=340),
            ],
            gap=24,
            align="start",
        ),
    )
    emit(
        "09-choice",
        "作出你的选择",
        "choice",
        VStack(
            [
                kit.choice("相信这份证言", width=Fill()),
                kit.choice("提出异议", width=Fill(), active=True),
                kit.choice("窄幅选项", width=300),
            ],
            gap=20,
            align="stretch",
        ),
    )
    identities = [
        PlayerIdentity("樱羽艾玛", 24, ema),
        PlayerIdentity("二阶堂希罗", 42, hiro),
        PlayerIdentity("未留下姓名的人"),
    ]
    emit(
        "10-identity",
        "对局身份",
        "game_identity",
        VStack(
            [
                kit.game_identity(
                    identities[0], width=864, detail="押注 120 Pt · 第 3 回合"
                ),
                kit.game_identity(identities[1], width=864),
                kit.game_identity(identities[2], width=864),
                kit.game_identity(
                    PlayerIdentity("很长很长的玩家昵称", 999),
                    width=200,
                    detail="窄幅优先展示昵称",
                ),
            ],
            gap=20,
            align="start",
        ),
    )
    common = dict(
        avatar_image=ema,
        frame_image=None,
        title1_image=None,
        title2_image=None,
        nickname="樱羽艾玛",
        level=24,
        current_pt=2350,
        description="即使怀抱不安，也想相信身边的人。\n把今天的故事，留在这页记录里。",
        width=864,
        height=420,
    )
    emit(
        "11-player-card",
        "人物档案",
        "player_card",
        kit.player_card(**common, standing_art=ema),
    )
    emit(
        "12-player-card-empty",
        "尚未留下证言",
        "player_card(None assets)",
        kit.player_card(
            **{
                **common,
                "avatar_image": None,
                "nickname": "新玩家",
                "description": "",
                "level": 0,
                "current_pt": 0,
            }
        ),
    )
    frame = ROOT / "plugins/inventory/resources/items/avatar_frames/frame_default.png"
    titles = Image.new("RGBA", (260, 40), INK)
    ImageDraw.Draw(titles).text(
        (18, 2), "永不遗忘的证言", font=load_font(23, SERIF), fill=PINK
    )
    emit(
        "13-player-cosmetics",
        "称号与头像框",
        "player_card(frame, titles)",
        kit.player_card(
            **{
                **common,
                "frame_image": frame,
                "title1_image": titles,
                "title2_image": titles,
            }
        ),
    )
    pulls = [
        PullRevealItem(
            name=name,
            rarity=rarity,
            is_new=i % 3 == 0,
            featured=rarity == 6,
            image=ema if i % 2 == 0 else hiro,
            note="盆栽 +120" if i == 1 else "",
        )
        for i, (name, rarity) in enumerate(
            [
                ("樱羽艾玛", 6),
                ("二阶堂希罗", 4),
                ("未寄出的信", 3),
                ("封存的记忆", 5),
                ("深夜的约定", 3),
            ]
            * 2
        )
    ]
    for count in range(1, 11):
        emit(
            f"14-pulls-{count:02d}",
            f"抽取结果 · {count} 抽",
            "pull_reveal",
            kit.pull_reveal(pulls[:count], width=864),
        )
    emit(
        "15-pulls-no-art",
        "无图像的抽取结果",
        "pull_reveal(image=None)",
        kit.pull_reveal(
            [
                PullRevealItem("封存的记忆", r, is_new=r % 2 == 0, featured=r == 6)
                for r in range(1, 7)
            ],
            width=864,
        ),
    )
    emit(
        "16-pulls-narrow",
        "窄幅抽取结果",
        "pull_reveal(width=200)",
        kit.pull_reveal(pulls[:3], width=200),
        width=296,
    )
    emit(
        "17-pulls-empty",
        "空抽取记录",
        "pull_reveal([])",
        kit.pull_reveal([], width=864),
    )
    # Original assets, as a reviewable source reference, with no story CGs.
    assets = [
        "paper.png",
        "book.png",
        "tab.png",
        "choice.png",
        "choice_active.png",
        "rule.png",
        "diamond.png",
        "flourish_left.png",
        "flourish_right.png",
        "title_ornament.png",
        "crest.png",
        "portrait_frame.png",
    ]
    emit(
        "18-source-assets",
        "原作 UI 素材",
        "resources/manifest.json",
        Grid(
            [
                kit.panel(
                    VStack(
                        [
                            kit.image(RESOURCES / name, width=230, height=150),
                            kit.text(name, font_size=18, align="center"),
                        ],
                        gap=10,
                    ),
                    padding=16,
                )
                for name in assets
            ],
            columns=3,
            column_track=Fixed(272),
            gap=18,
        ),
    )
    return records


def write_gallery(output: Path, records: list[dict]) -> None:
    (output / "coverage.json").write_text(
        json.dumps(records, ensure_ascii=False, indent=2) + "\n"
    )
    entries = []
    for r in records:
        entries.append(
            f'<a class="card" href="{html.escape(r["file"])}" data-search="{html.escape(r["title"] + " " + r["api"] + " " + r["group"])}"><img loading="lazy" src="{html.escape(r["file"])}" alt="{html.escape(r["title"])}"><div><small>{html.escape(r["group"])}</small><h2>{html.escape(r["title"])}</h2><p>{html.escape(r["api"])} · {r["size"][0]} × {r["size"][1]}</p></div></a>'
        )
    document = (
        """<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>魔女审判 · 渲染图鉴</title><style>
*{box-sizing:border-box}body{margin:0;background:#e8dbd6;color:#2b2227;font:16px Georgia,"Songti SC",serif}header{background:#2b2227;color:#f7ede5;padding:52px max(24px,6vw);border-bottom:5px solid #882b41}small{color:#a55369;letter-spacing:2px}header small{color:#ff92ae}h1{font-size:clamp(32px,4vw,64px);margin:16px 0}header p{line-height:1.8;max-width:780px;color:#d4c0bf}nav{display:flex;gap:14px;align-items:center;flex-wrap:wrap;padding:24px 6vw;position:sticky;top:0;background:#e8dbd6ef;z-index:1;border-bottom:1px solid #aa8b90}input{font:inherit;padding:12px 18px;min-width:240px;flex:1;border:1px solid #8c7278;background:#f7ede5;color:#2b2227}button{font:inherit;padding:12px 18px;background:#2b2227;color:#f7ede5;border:0;cursor:pointer}main{padding:28px 6vw;display:grid;grid-template-columns:repeat(auto-fill,minmax(280px,1fr));gap:24px}.card{color:inherit;text-decoration:none;background:#f7ede5;border:1px solid #a78a90;display:flex;flex-direction:column}.card:hover{outline:2px solid #882b41}.card img{width:100%;height:340px;object-fit:contain;object-position:top;background:#cbbab8;padding:10px}.card div{padding:18px}.card h2{font-size:22px;margin:10px 0}.card p{font:13px system-ui;overflow-wrap:anywhere;color:#745f66}.card[hidden]{display:none}footer{padding:30px 6vw;color:#745f66}a:focus-visible,button:focus-visible,input:focus-visible{outline:3px solid #b34167}</style>
<header><small>MANOSABA / VISUAL ARCHIVE</small><h1>魔女审判 · 渲染图鉴</h1><p>游戏原始 UI 素材、旧纸纹理与衬线字体构成的渲染 kit。点击任意卡片查看完整尺寸 PNG。业务图采用仓库的真实渲染器和测试数据；人物与物品名称属于示例数据。</p></header>
<nav><input id="search" aria-label="搜索示例" placeholder="搜索功能、页面或 API…"><button data-filter="">全部</button><button data-filter="kit 功能">Kit 功能</button><button data-filter="业务页面">业务页面</button><span id="count"></span></nav><main>"""
        + "".join(entries)
        + """</main><footer>素材提取：UnityPy · Steam App 3101040。游戏美术归原权利人所有，不属于仓库 MIT 授权。Source Han Serif SC：SIL OFL 1.1。详见 resources/manifest.json 和 kit README。</footer><script>
const field=document.querySelector('#search'),cards=[...document.querySelectorAll('.card')];function filter(){const q=field.value.toLowerCase();let n=0;for(const c of cards){c.hidden=!c.dataset.search.toLowerCase().includes(q);if(!c.hidden)n++}document.querySelector('#count').textContent=n+' 张示例'}field.addEventListener('input',filter);for(const b of document.querySelectorAll('button'))b.addEventListener('click',()=>{field.value=b.dataset.filter;filter()});filter();</script></html>"""
    )
    (output / "index.html").write_text(document)
    # All full-size outputs also have a compact, paginated visual index.
    font = load_font(20, SERIF)
    for start in range(0, len(records), 20):
        batch = records[start : start + 20]
        sheet = Image.new("RGB", (1600, ((len(batch) + 4) // 5) * 310 + 80), "#e8dbd6")
        draw = ImageDraw.Draw(sheet)
        draw.text(
            (24, 18),
            f"魔女审判 / 渲染图鉴   {start + 1}–{start + len(batch)}",
            font=load_font(30, SERIF),
            fill=INK,
        )
        for i, r in enumerate(batch):
            with Image.open(output / r["file"]) as source:
                im = source.convert("RGB")
                im.thumbnail((296, 260), Image.Resampling.LANCZOS)
            x = i % 5 * 320 + 12
            y = i // 5 * 310 + 70
            sheet.paste(im, (x + (296 - im.width) // 2, y))
            draw.text((x, y + 266), r["title"], font=font, fill=INK)
        sheet.save(output / f"contact-{start // 20 + 1:02d}.jpg", quality=90)
    # A small curated overview suitable for inline delivery.
    titles = (
        ("资料·完整", "抽卡·十连", "邮箱", "巡演·对局")
        if any(r["group"] == "业务页面" for r in records)
        else ("人物档案", "作出你的选择", "抽取结果 · 1 抽", "抽取结果 · 10 抽")
    )
    picks = [next(r for r in records if r["title"] == title) for title in titles]
    overview = Image.new("RGB", (1600, 1300), "#e8dbd6")
    draw = ImageDraw.Draw(overview)
    draw.text((42, 24), "魔女审判 · 插件专属布局", font=load_font(42, SERIF), fill=INK)
    for i, r in enumerate(picks):
        with Image.open(output / r["file"]) as source:
            im = source.convert("RGB")
            im.thumbnail((750, 540), Image.Resampling.LANCZOS)
        x = 40 + i % 2 * 780
        y = 110 + i // 2 * 585
        overview.paste(im, (x + (750 - im.width) // 2, y))
        draw.text((x, y + 547), r["title"], font=font, fill=INK)
    overview.save(output / "overview.jpg", quality=94)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=ROOT / "output/manosaba")
    parser.add_argument(
        "--skip-business",
        action="store_true",
        help="Reuse previously rendered business PNGs.",
    )
    args = parser.parse_args()
    output = args.output_dir.resolve()
    output.mkdir(parents=True, exist_ok=True)
    records = feature_gallery(output)
    if not args.skip_business:
        from preview_kasumi_surfaces import _render_gallery

        _, failures = _render_gallery(output / "business", "manosaba")
        if failures:
            raise RuntimeError("\n".join(failures))
        from plugins.tour.render.leaderboard import render_leaderboard

        render_leaderboard(
            {
                "初级": [("樱羽艾玛", 42.13), ("二阶堂希罗", 46.8)],
                "中级": [("新玩家", 123.45)],
            },
            ManosabaKit(),
        ).save(output / "business/54-tour-leaderboard.png")
    for path in sorted((output / "business").glob("*.png")):
        number = int(path.name.split("-")[0])
        with Image.open(path) as image:
            size = list(image.size)
        records.append(
            {
                "file": str(path.relative_to(output)),
                "title": BUSINESS_LABELS[number - 1],
                "api": path.stem,
                "group": "业务页面",
                "size": size,
            }
        )
    write_gallery(output, records)
    print(f"Delivered {len(records)} full-size PNGs: {output / 'index.html'}")


if __name__ == "__main__":
    main()
