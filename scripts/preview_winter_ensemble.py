"""Render actual S5 config plus all business fixtures using isolated test data."""

from __future__ import annotations

import html
import json
from types import SimpleNamespace
from pathlib import Path
from datetime import datetime
from datetime import timezone
from unittest.mock import patch

import preview_kasumi_surfaces as census
from PIL import Image
from PIL import ImageDraw

from plugins.render import Frame
from plugins.render import VStack
from plugins.render import AutoPage
from plugins.render import PlayerIdentity
from plugins.render import PullRevealItem
from plugins.render.kits import WinterEnsembleKit
from plugins.gacha.render import PullPageData
from plugins.gacha.render import pull_page
from plugins.gacha.render import banner_page
from plugins.gacha.render import banner_page_data
from plugins.gacha.service import _banner_from_season
from plugins.render.primitives import load_font
from plugins.inventory.render.profile import ProfileData
from plugins.inventory.render.profile import profile_page
from plugins.render.kits.mewtype.fonts import CHINESE_BODY_FONT
from plugins.inventory.render.season_info import SeasonInfoData
from plugins.inventory.render.season_info import SeasonRewardRow
from plugins.inventory.render.season_info import season_info_page

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / ".cache/render-previews/winter-ensemble"


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    season = next(
        s
        for s in json.loads((ROOT / "plugins/inventory/seasons.json").read_text())[
            "seasons"
        ]
        if s["season_key"] == "2026-s05"
    )
    catalog = {
        i["item_id"]: i
        for i in json.loads((ROOT / "plugins/inventory/items.json").read_text())[
            "items"
        ]
    }
    names = {k: i["name"] for k, i in catalog.items()}
    art = {
        k: ROOT / i["metadata"]["art"]
        for k, i in catalog.items()
        if i.get("metadata", {}).get("art")
    }
    b = _banner_from_season(
        SimpleNamespace(
            season_key=season["season_key"],
            name=season["name"],
            metadata_json=json.dumps(season),
        )
    )
    kit = WinterEnsembleKit()
    records = []

    def save(name, label, page):
        im = page.render()
        im.save(OUT / name)
        records.append((name, label))
        print(name, im.size, flush=True)

    bundle = (season["gacha_character_frame_item_id"], season["gacha_theme_item_id"])
    save(
        "banner.png",
        "实际限定卡池",
        banner_page(
            banner_page_data(
                b, pity_count=0, bundle_item_ids=bundle, item_names=names, item_art=art
            ),
            kit,
        ),
    )
    for e in b.entries[:2]:
        save(
            f"single-{e.character_id}.png",
            e.name,
            pull_page(
                PullPageData(
                    b.name,
                    (PullRevealItem(e.name, e.rarity, True, True, art[e.item_id]),),
                    0,
                    90,
                    tuple(names[i] for i in bundle),
                ),
                kit,
            ),
        )
    save(
        "ten.png",
        "示例十连",
        pull_page(
            PullPageData(
                b.name,
                tuple(
                    PullRevealItem(
                        e.name,
                        e.rarity,
                        j % 2 == 0,
                        e.featured,
                        art[e.item_id],
                        "" if j % 2 == 0 else f"盆栽 +{e.rarity * 10}",
                    )
                    for j, e in enumerate(b.entries[:10])
                ),
                0,
                90,
            ),
            kit,
        ),
    )
    rewards = tuple(
        SeasonRewardRow(
            t["title"],
            tuple(f"{names[i['item_id']]} × {i['quantity']}" for i in t["items"]),
        )
        for t in season["reward_tiers"]
    )
    start = int(datetime.fromisoformat(season["starts_at"]).timestamp())
    end = int(datetime.fromisoformat(season["ends_at"]).timestamp())
    save(
        "season.png",
        "实际赛季排期及奖励",
        season_info_page(
            SeasonInfoData(
                b.season_name,
                "upcoming",
                start,
                end,
                start - 86400,
                None,
                None,
                rewards,
                b.name,
                tuple(c["name"] for c in season["featured_characters"]),
            ),
            kit,
        ),
    )
    save(
        "profile.png",
        "示例玩家装备效果",
        profile_page(
            ProfileData(
                PlayerIdentity("示例玩家", 24),
                100,
                description="一起去排练吧。",
                star_stickers=120,
                bonsai=60,
                season_name=b.season_name,
                equipped=(("头像框", names[bundle[0]]), ("主题", names[bundle[1]])),
                standing_art=art[b.entries[0].item_id],
                avatar_frame=art[bundle[0]],
            ),
            kit,
        ),
    )
    from datetime import timedelta

    from plugins.mailbox.models import ServiceMail
    from plugins.mailbox.models import ServiceMailAttachment
    from plugins.mailbox.render import mail_page
    from plugins.inventory.models import GrantResult

    mail = ServiceMail(
        id=1,
        title="冬日合奏 · 冠军奖励",
        content="赛季已结算。最终排名第 1 名，感谢参与。",
        star_kakeras=0,
        star_stickers=0,
        attachments=[
            ServiceMailAttachment(item_id=i["item_id"], quantity=i["quantity"])
            for i in season["reward_tiers"][0]["items"]
        ],
        sender_id="system",
        created_at=datetime(2027, 1, 1),
        expire_time=datetime(2027, 1, 1) + timedelta(days=30),
        is_broadcast=False,
        is_read=False,
        read_at=None,
    )
    with patch(
        "plugins.mailbox.render.inbox.bot_now",
        return_value=datetime.fromtimestamp(end, tz=timezone(timedelta(hours=8))),
    ):
        save(
            "reward-mail.png",
            "示例排名奖励邮件",
            mail_page(
                mail,
                [
                    GrantResult(
                        i["item_id"], i["quantity"], i["quantity"], i["quantity"]
                    )
                    for i in season["reward_tiers"][0]["items"]
                ],
                kit,
            ),
        )
    # Actual frame shapes at full size and the two chat scales; no fake avatar.
    frames = ["character", "champion", "podium", "top10", "top50"]
    board = Image.new("RGB", (1200, 810), "#e5edf2")
    draw = ImageDraw.Draw(board)
    for j, k in enumerate(frames):
        im = Image.open(art[f"frame_winter_{k}"]).convert("RGBA")
        x = j % 3 * 400
        y = j // 3 * 400
        im.thumbnail((260, 260))
        board.paste(im, (x + 65, y + 10), im)
        draw.text(
            (x + 25, y + 275),
            names[f"frame_winter_{k}"],
            font=load_font(22, CHINESE_BODY_FONT),
            fill="#243b53",
        )
        for q, size in enumerate((64, 96)):
            small = im.resize((size, size), Image.Resampling.LANCZOS)
            board.paste(small, (x + 60 + q * 140, y + 310), small)
    board.save(OUT / "frames.png")
    records.append(("frames.png", "五款框与 64/96px 效果"))
    # The same isolated, handler-shaped fixtures cover all remaining surfaces.
    business = OUT / "business"
    business.mkdir(exist_ok=True)
    outputs, failures = census._render_gallery(business, "winter_ensemble")
    if failures:
        raise RuntimeError(f"Business previews failed: {failures}")
    records.extend(
        (f"business/{path.name}", f"业务示例 · {path.stem}") for path in outputs
    )

    links = "".join(
        f'<a href="{n}"><h2>{html.escape(label)}</h2><img loading="lazy" src="{n}"></a>'
        for n, label in records
    )
    (OUT / "index.html").write_text(
        '<!doctype html><meta charset="utf-8"><title>冬日合奏 · 验收预览</title><style>body{background:#e5edf2;color:#243b53;font:20px sans-serif;padding:32px}main{display:grid;grid-template-columns:repeat(auto-fit,minmax(360px,1fr));gap:24px}a{color:inherit}img{width:100%;max-height:850px;object-fit:contain}</style><h1>冬日合奏 · 实际配置预览</h1><p>2026-11-24 00:00 至 2027-01-01 00:00，北京时间；结束不包含。示例玩家及抽取结果仅用于预览。</p><main>'
        + links
        + "</main>"
    )


if __name__ == "__main__":
    main()
