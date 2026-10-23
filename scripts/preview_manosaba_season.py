"""Render the real S4 configuration with sample player state, without a bot DB."""

from __future__ import annotations

import html
import json
from types import SimpleNamespace
from pathlib import Path
from datetime import datetime

# Isolated test bootstrap: initializes NoneBot without startup/network or live data.
import preview_kasumi_surfaces  # noqa: F401
from PIL import Image
from PIL import ImageOps
from PIL import ImageDraw

from plugins.render import RenderContext
from plugins.render import PlayerIdentity
from plugins.render import PullRevealItem
from plugins.render.kits import ManosabaKit
from plugins.gacha.render import PullPageData
from plugins.gacha.render import pull_page
from plugins.gacha.render import banner_page
from plugins.gacha.render import banner_page_data
from plugins.gacha.service import _banner_from_season
from plugins.render.primitives import load_font
from plugins.inventory.render.profile import ProfileData
from plugins.inventory.render.profile import profile_page
from plugins.inventory.render.season_info import SeasonInfoData
from plugins.inventory.render.season_info import SeasonRewardRow
from plugins.inventory.render.season_info import season_info_page
from plugins.render.kits.manosaba.components import SERIF

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "output/manosaba-season"


def main():
    OUTPUT.mkdir(parents=True, exist_ok=True)
    config = json.loads((ROOT / "plugins/inventory/seasons.json").read_text())
    season = next(s for s in config["seasons"] if s["season_key"] == "2026-s04")
    catalog = {
        i["item_id"]: i
        for i in json.loads((ROOT / "plugins/inventory/items.json").read_text())[
            "items"
        ]
    }
    names = {key: item["name"] for key, item in catalog.items()}
    art = {
        key: ROOT / item["metadata"]["art"]
        for key, item in catalog.items()
        if item.get("metadata", {}).get("art")
    }
    row = SimpleNamespace(
        season_key=season["season_key"],
        name=season["name"],
        metadata_json=json.dumps(season),
    )
    banner = _banner_from_season(row)
    kit = ManosabaKit()
    records = []

    def save(label, name, page):
        image = page.render(RenderContext(pixel_ratio=2))
        image.save(OUTPUT / name)
        records.append((label, name))
        print(f"{name}: {image.width}x{image.height}", flush=True)

    bundle = (season["gacha_character_frame_item_id"], season["gacha_theme_item_id"])
    data = banner_page_data(
        banner, pity_count=0, bundle_item_ids=bundle, item_names=names, item_art=art
    )
    save("限定卡池 · 双六星", "banner.png", banner_page(data, kit))
    recipe = json.loads(
        (
            ROOT
            / "plugins/inventory/resources/items/standing_art/manosaba/recipes.json"
        ).read_text()
    )
    for item in banner.entries[:2]:
        result = PullRevealItem(
            name=item.name,
            rarity=6,
            image=art[item.item_id],
            is_new=True,
            featured=True,
        )
        save(
            f"单抽 · {item.name}",
            f"single-{item.character_id}.png",
            pull_page(
                PullPageData(
                    banner.name,
                    (result,),
                    0,
                    banner.hard_pity,
                    tuple(names[i] for i in bundle),
                ),
                kit,
            ),
        )
    batch = tuple(
        PullRevealItem(
            name=e.name,
            rarity=e.rarity,
            image=art[e.item_id],
            is_new=True,
            featured=e.featured,
        )
        for e in [*banner.entries[4:13], banner.entries[1]]
    )
    save(
        "十连 · 示例结果",
        "ten-pull.png",
        pull_page(
            PullPageData(
                banner.name, batch, 0, banner.hard_pity, tuple(names[i] for i in bundle)
            ),
            kit,
        ),
    )
    rewards = tuple(
        SeasonRewardRow(
            t["title"],
            tuple(
                names[i["item_id"]]
                + (f" × {i['quantity']}" if i["quantity"] != 1 else "")
                for i in t["items"]
            ),
        )
        for t in season["reward_tiers"]
    )
    starts = int(datetime.fromisoformat(season["starts_at"]).timestamp())
    ends = int(datetime.fromisoformat(season["ends_at"]).timestamp())
    save(
        "赛季预告",
        "season.png",
        season_info_page(
            SeasonInfoData(
                season["name"],
                "upcoming",
                starts,
                ends,
                starts - 86400,
                None,
                None,
                rewards,
                banner.name,
                tuple(c["name"] for c in season["featured_characters"]),
            ),
            kit,
        ),
    )
    ema = Image.open(art["standing_art_manosaba_ema"]).convert("RGBA")
    avatar = ema.crop((0, 0, ema.width, round(ema.height * 0.25)))
    save(
        "装备后的档案 · 示例玩家",
        "profile.png",
        profile_page(
            ProfileData(
                PlayerIdentity("示例玩家", 24, avatar=avatar),
                100,
                description="愿每一份证言，都能抵达真相。",
                star_stickers=120,
                bonsai=60,
                season_name=season["name"],
                equipped=(
                    ("头像框", names[bundle[0]]),
                    ("主题", names[bundle[1]]),
                    ("立绘", names["standing_art_manosaba_ema"]),
                ),
                standing_art=art["standing_art_manosaba_ema"],
                avatar_frame=art[bundle[0]],
            ),
            kit,
        ),
    )
    # Native frame layering: 416px avatar disc under a 512px cosmetic.
    frames = ["champion", "podium", "top10", "top50", "character"]
    board = Image.new("RGB", (1440, 1230), "#e8dbd6")
    draw = ImageDraw.Draw(board)
    for i, kind in enumerate(frames):
        x = 30 + i % 3 * 480
        y = 70 + i // 3 * 570
        frame = Image.open(art[f"frame_manosaba_{kind}"]).convert("RGBA")
        layer = Image.new("RGBA", (512, 512))
        face = ImageOps.fit(avatar, (416, 416), method=Image.Resampling.LANCZOS)
        mask = Image.new("L", (416, 416))
        ImageDraw.Draw(mask).ellipse((0, 0, 415, 415), fill=255)
        layer.paste(face, (48, 48), mask)
        layer.alpha_composite(frame)
        large = layer.resize((360, 360), Image.Resampling.LANCZOS)
        board.paste(large, (x + 36, y), large)
        draw.text(
            (x + 10, y + 375),
            names[f"frame_manosaba_{kind}"],
            font=load_font(25, SERIF),
            fill="#882b41",
        )
        for j, (size, bg) in enumerate([(96, "#2b2227"), (64, "#f7ede5")]):
            draw.rectangle(
                (x + 64 + j * 160, y + 432, x + 200 + j * 160, y + 554), fill=bg
            )
            small = layer.resize((size, size), Image.Resampling.LANCZOS)
            board.paste(
                small,
                (x + 64 + j * 160 + (136 - size) // 2, y + 432 + (122 - size) // 2),
                small,
            )
    draw.text(
        (38, 14),
        "头像框 · 完整尺寸与聊天缩略尺寸",
        font=load_font(32, SERIF),
        fill="#2b2227",
    )
    board.save(OUTPUT / "frames.jpg", quality=95)
    records.append(("五款头像框 · 含 64/96px 效果", "frames.jpg"))
    cast = Image.new("RGB", (1500, 1560), "#e8dbd6")
    draw = ImageDraw.Draw(cast)
    for i, r in enumerate(recipe):
        im = Image.open(art[f"standing_art_manosaba_{r['prefab'].lower()}"]).convert(
            "RGBA"
        )
        im.thumbnail((270, 425), Image.Resampling.LANCZOS)
        x = i % 5 * 300
        y = i // 5 * 520
        cast.paste(im, (x + (300 - im.width) // 2, y + 14), im)
        draw.text(
            (x + 16, y + 450),
            "★" * r["rarity"],
            font=load_font(21, SERIF),
            fill="#882b41",
        )
        draw.text(
            (x + 16, y + 482),
            r["name"].split(" ")[0],
            font=load_font(26, SERIF),
            fill="#2b2227",
        )
    cast.save(OUTPUT / "cast.jpg", quality=95)
    records.append(("13 位角色 · 完整卡池", "cast.jpg"))
    cards = "".join(
        f'<a href="{name}"><img src="{name}"><p>{html.escape(label)}</p></a>'
        for label, name in records
    )
    tier_rows = []
    for rarity, rate in sorted(banner.base_rates.items(), reverse=True):
        entries = [e for e in banner.entries if e.rarity == rarity]
        names_in_tier = "、".join(e.name.split(" ")[0] for e in entries)
        per_character = rate / len(entries)
        tier_rows.append(
            f"<tr><td>{'★' * rarity}</td><td>{html.escape(names_in_tier)}</td><td>{rate:.0%}</td><td>{per_character:.2%}</td></tr>"
        )
    tier_table = (
        "<section class='rates'><table><caption>基础出率 · 同星级角色等权，本期不设三星</caption><thead><tr><th>星级</th><th>角色</th><th>合计</th><th>每位</th></tr></thead><tbody>"
        + "".join(tier_rows)
        + "</tbody></table><p>进入软保底后，六星出率提升，其他档位相应减少。</p></section>"
    )
    (OUTPUT / "index.html").write_text(
        f"""<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>S4 · 未竟的证言</title><style>body{{margin:0;background:#e8dbd6;color:#2b2227;font:18px Georgia,"Songti SC",serif}}header{{padding:40px 6vw;background:#2b2227;color:#f7ede5}}h1{{font-size:42px}}header p{{line-height:1.8}}main{{padding:30px 5vw;display:grid;grid-template-columns:repeat(auto-fit,minmax(360px,1fr));gap:26px}}a{{color:inherit;text-decoration:none;border:1px solid #a78a90;padding:18px;background:#f7ede5}}img{{width:100%;height:520px;object-fit:contain}}p{{margin:18px 0 4px}}.rates{{padding:24px 6vw}}table{{width:100%;border-collapse:collapse;text-align:left}}th,td{{padding:14px;border-bottom:1px solid #a78a90}}caption{{text-align:left;padding:12px 0;color:#882b41}}footer{{padding:30px 6vw;line-height:1.8}}</style><header><small>MANOSABA / SEASON 04</small><h1>{season["name"]}</h1><p>2026-10-27 00:00 至 2026-11-24 00:00 · 北京时间 UTC+8<br>双六星艾玛 / 希罗 · 13 位角色 · 5 款头像框 · 魔女审判主题</p></header>{tier_table}<main>{cards}</main><footer>采用实际赛季配置与渲染器。十连、背包和玩家数值为预览示例，不代表实际抽取或发放。<br>单抽 120 / 十连 1200 星星贴纸；基础出率：六星 1% / 五星 20% / 四星 79%；六星每位 0.5%、五星每位 5%、四星每位约 11.29%；70 抽软保底、90 抽硬保底。<br>首次六星附赠双生誓约头像框及主题；第二位六星只发立绘；重复六星立绘补偿 60 盆栽。<br>立绘由本机 manosaba-sprite-synth 分层合成；原始角色美术版权归原作权利人。此页为本地赛季准备预览。</footer></html>"""
    )
    overview = Image.new("RGB", (1600, 1250), "#e8dbd6")
    draw = ImageDraw.Draw(overview)
    draw.text(
        (35, 20),
        "第 4 赛季 · 魔女审判 · 未竟的证言",
        font=load_font(39, SERIF),
        fill="#2b2227",
    )
    for i, name in enumerate(["banner.png", "frames.jpg", "cast.jpg", "season.png"]):
        im = Image.open(OUTPUT / name).convert("RGB")
        im.thumbnail((750, 530), Image.Resampling.LANCZOS)
        overview.paste(
            im, (40 + i % 2 * 780 + (750 - im.width) // 2, 100 + i // 2 * 565)
        )
    overview.save(OUTPUT / "overview.jpg", quality=95)
    print(OUTPUT / "index.html")


if __name__ == "__main__":
    main()
