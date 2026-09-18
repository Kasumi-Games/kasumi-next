"""Render a visual census of every player-facing image in any render kit.

This script deliberately reuses the representative, handler-shaped fixtures
from the render tests.  That keeps the preview gallery aligned with the actual
cards without inventing a second set of stale demo models.
"""

from __future__ import annotations

import argparse
import os
import random
import runpy
import sys
from collections.abc import Callable
from dataclasses import replace
from pathlib import Path

from PIL import Image
from PIL import ImageDraw
from PIL import ImageFont

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# Matplotlib is used by the season trend card.  Keep its cache inside the
# workspace so the preview works in the same sandbox as the bot.
os.environ.setdefault("MPLCONFIGDIR", str(ROOT / ".cache" / "matplotlib"))
Path(os.environ["MPLCONFIGDIR"]).mkdir(parents=True, exist_ok=True)

# Several plugin packages expect NoneBot to have been initialised before they
# are imported.  The test bootstrap does exactly that, without starting a bot.
runpy.run_path(str(ROOT / "tests" / "conftest.py"))


def _test_namespace(filename: str) -> dict[str, object]:
    return runpy.run_path(str(ROOT / "tests" / filename))


def _preview_card(
    label: str,
    fill: tuple[int, int, int, int],
) -> Image.Image:
    """Create deterministic stand-in playing-card art for the game census."""

    width, height = 640, 896
    image = Image.new("RGBA", (width, height), (255, 255, 255, 0))
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((0, 0, width - 1, height - 1), radius=36, fill=fill)
    draw.rounded_rectangle(
        (18, 18, width - 19, height - 19),
        radius=28,
        outline=(255, 255, 255, 230),
        width=8,
    )
    try:
        font = ImageFont.truetype(
            str(ROOT / "plugins" / "blackjack" / "recourses" / "old.ttf"),
            120,
        )
    except OSError:
        font = ImageFont.load_default()
    bbox = draw.textbbox((0, 0), label, font=font)
    draw.text(
        (
            (width - (bbox[2] - bbox[0])) // 2,
            (height - (bbox[3] - bbox[1])) // 2 - bbox[1],
        ),
        label,
        font=font,
        fill=(255, 255, 255, 255),
    )
    return image


def _preview_blackjack(kit_name: str, output_dir: Path) -> list[Path]:
    from plugins.blackjack.models import Card
    from plugins.blackjack.models import Hand
    from plugins.blackjack.render import BlackjackRenderer
    from plugins.render import PlayerIdentity
    from plugins.render.kits import KITS

    renderer = object.__new__(BlackjackRenderer)
    renderer.kit = KITS[kit_name]()
    renderer.card_back = _preview_card("?", (55, 55, 65, 255))
    renderer.get_font = lambda size: ImageFont.truetype(
        str(ROOT / "plugins" / "blackjack" / "recourses" / "old.ttf"), size
    )
    identity = PlayerIdentity(nickname="香澄", level=42)

    def card(rank: str, suit: str, fill: tuple[int, int, int, int]) -> Card:
        item = Card(suit, rank)
        item._get_image = lambda ace_value=None: _preview_card(rank, fill)
        return item

    dealer = Hand()
    dealer.add_card(card("A", "cool", (234, 78, 116, 255)))
    dealer.add_card(card("10", "happy", (66, 133, 244, 255)))
    dealer.add_card(card("K", "pure", (76, 175, 80, 255)))

    player = Hand()
    player.add_card(card("8", "powerful", (255, 124, 85, 255)))
    player.add_card(card("7", "cool", (184, 130, 225, 255)))

    outputs = [
        output_dir / f"blackjack-hand-{kit_name}.png",
        output_dir / f"blackjack-table-{kit_name}.png",
    ]
    renderer.generate_hand(
        dealer,
        second_card_back=True,
        identity=identity,
        detail="庄家回合 · 押注 120 Pt",
    ).save(outputs[0])
    renderer.generate_table(
        dealer,
        player,
        dealer_card_back=True,
        identity=identity,
        detail="押注 120 Pt · 玩家 15 点",
    ).save(outputs[1])
    return outputs


def _preview_mines(kit_name: str, output_dir: Path) -> list[Path]:
    from plugins.mines.models import Field
    from plugins.mines.render.field import render
    from plugins.render import PlayerIdentity
    from plugins.render.kits import KITS

    random.seed(7)
    field = Field(width=5, height=5, mines=4)
    for index in (0, 3, 6, 12, 18):
        field.reveal_block(index)
    field.reveal_all_mines()

    output = output_dir / f"mines-{kit_name}.png"
    render(
        field,
        kit=KITS[kit_name](),
        identity=PlayerIdentity(nickname="香澄", level=42),
        detail="押注 120 Pt · 剩 4 雷",
    ).save(output)
    return [output]


def _preview_one_stroke(kit_name: str, output_dir: Path) -> list[Path]:
    from plugins.one_stroke.models import Graph
    from plugins.one_stroke.render.graph import render
    from plugins.one_stroke.render.leaderboard import render_leaderboard
    from plugins.one_stroke.session import GameSession
    from plugins.render import PlayerIdentity
    from plugins.render.kits import KITS

    nodes = {(row, column) for row in range(4) for column in range(4)}
    path = [
        (0, 0),
        (0, 1),
        (0, 2),
        (0, 3),
        (1, 3),
        (1, 2),
        (1, 1),
        (1, 0),
        (2, 0),
        (2, 1),
        (2, 2),
        (2, 3),
        (3, 3),
    ]
    edges = {frozenset((start, end)) for start, end in zip(path, path[1:])}
    graph = Graph(rows=4, cols=4, nodes=nodes, edges=edges, start_node=path[0])
    session = GameSession(
        user_id="preview",
        channel_id="preview",
        difficulty_name="普通",
        reward=120,
        graph=graph,
    )
    for next_node in path[1:7]:
        edge = frozenset((session.current_pos, next_node))
        session.drawn_edges.add(edge)
        session.current_pos = next_node
        session.visited_nodes.add(next_node)

    board_output = output_dir / f"one-stroke-{kit_name}.png"
    leaderboard_output = output_dir / f"one-stroke-leaderboard-{kit_name}.png"
    render(
        session,
        kit=KITS[kit_name](),
        identity=PlayerIdentity(nickname="香澄", level=42),
        detail="难度 普通 · 奖励 120 Pt",
    ).save(board_output)
    render_leaderboard(
        [("kasumi", 12.34), ("arisa", 16.78), ("tae", 20.12)],
        [("a very very long player name", 23.45), ("rimi", 25.67)],
        [("saaya", 31.23)],
        kit=KITS[kit_name](),
    ).save(leaderboard_output)
    return [board_output, leaderboard_output]


def _render_gallery(
    output_dir: Path,
    kit_name: str = "kasumi",
) -> tuple[list[Path], list[str]]:
    from plugins.render import PlayerIdentity
    from plugins.render.kits import KITS

    kit = KITS[kit_name]()
    output_dir.mkdir(parents=True, exist_ok=True)
    outputs: list[Path] = []
    failures: list[str] = []
    sequence = 0

    def emit(slug: str, render: Callable[[], Image.Image]) -> None:
        nonlocal sequence
        sequence += 1
        path = output_dir / f"{sequence:02d}-{slug}.png"
        try:
            image = render()
            if image.mode != "RGBA":
                image = image.convert("RGBA")
            image.save(path)
            outputs.append(path)
            print(f"OK  {path.name:<42} {image.width}x{image.height}")
        except Exception as error:  # Render the rest so visual QA can continue.
            failures.append(f"{path.name}: {type(error).__name__}: {error}")
            print(f"ERR {path.name:<42} {type(error).__name__}: {error}")

    # Profile, daily activity, and season surfaces.
    profile = _test_namespace("test_profile_render.py")
    from plugins.inventory.render import render_profile

    emit("profile-full", lambda: render_profile(profile["_data"](), kit))
    emit(
        "profile-empty",
        lambda: render_profile(
            profile["_data"](
                identity=PlayerIdentity(nickname="新玩家", level=0),
                current_pt=0,
                description="",
                star_stickers=0,
                bonsai=0,
                season_name=None,
                season_rank=None,
                equipped=(),
            ),
            kit,
        ),
    )

    daily = _test_namespace("test_daily_render.py")
    from plugins.daily.render import render_checkin
    from plugins.daily.render import render_rank

    emit("daily-checkin", lambda: render_checkin(daily["_checkin"](), kit))
    emit(
        "daily-checkin-bonus",
        lambda: render_checkin(
            daily["_checkin"](
                streak=28,
                streak_bonus=120,
                old_level=23,
                new_level=24,
                level_stickers=120,
                offseason=True,
                unread_mails=3,
                task_done=True,
            ),
            kit,
        ),
    )
    emit("level-rank", lambda: render_rank(daily["_rank"](), kit))

    season_rank = _test_namespace("test_season_rank_render.py")
    from plugins.inventory.render import render_season_rank

    emit(
        "season-rank",
        lambda: render_season_rank(season_rank["_data"](), kit),
    )

    season_trend = _test_namespace("test_season_trend_render.py")
    from plugins.inventory.season_render import render_season_trend

    emit(
        "season-trend",
        lambda: render_season_trend(season_trend["_data"](), kit),
    )

    season_info = _test_namespace("test_season_info_render.py")
    from plugins.inventory.render import render_season_info

    emit(
        "season-info",
        lambda: render_season_info(season_info["_active_data"](), kit),
    )

    listing = _test_namespace("test_inventory_listing_render.py")
    from plugins.inventory.render import render_inventory_list

    emit(
        "inventory-listing",
        lambda: render_inventory_list(listing["_data"](), kit),
    )

    # Help census and command detail.
    help_test = _test_namespace("test_help_render.py")
    from plugins.help import HELP_ENTRIES
    from plugins.help.entries import find_entries
    from plugins.help.render import render_board
    from plugins.help.render import render_detail

    emit("help-board", lambda: render_board(HELP_ENTRIES, kit))
    emit(
        "help-detail",
        lambda: render_detail(find_entries(HELP_ENTRIES, "猜卡面")[0], kit),
    )

    # Gacha showcase, single/ten reveals, and history.
    gacha_banner = _test_namespace("test_gacha_banner_showcase.py")
    from plugins.gacha.render import render_banner

    emit(
        "gacha-banner",
        lambda: render_banner(gacha_banner["_showcase_data"](), kit),
    )
    emit(
        "gacha-banner-artless",
        lambda: render_banner(
            gacha_banner["_showcase_data"](featured_art=None),
            kit,
        ),
    )

    gacha = _test_namespace("test_gacha_render.py")
    from plugins.gacha.render import pull_page_data
    from plugins.gacha.render import render_pull

    kasumi_art = gacha["KASUMI_ART"]
    pull_art = {
        "standing_art_kasumi_starbeat": kasumi_art,
        "standing_art_placeholder_r3_001": (
            ROOT
            / "plugins"
            / "render"
            / "kits"
            / "kasumi"
            / "resources"
            / "standing"
            / "kasumi_starry_normal.png"
        ),
    }
    banner = gacha["_banner"]()
    featured = gacha["_result"](
        "standing_art_kasumi_starbeat",
        "户山香澄 抬头看，星星在跳动立绘",
        6,
        pity_after=0,
    )
    emit(
        "gacha-single",
        lambda: render_pull(
            pull_page_data(
                [featured],
                banner,
                item_art=pull_art,
            ),
            kit,
        ),
    )
    emit(
        "gacha-ten",
        lambda: render_pull(
            pull_page_data(
                gacha["_ten_results"](),
                banner,
                item_art=pull_art,
            ),
            kit,
        ),
    )

    history = _test_namespace("test_gacha_history_card.py")
    from plugins.gacha.render import render_history

    emit(
        "gacha-history",
        lambda: render_history(history["_display_data"](), kit),
    )

    # Mailbox list/detail/claim variants.
    mailbox = _test_namespace("test_mailbox_render.py")
    from plugins.inventory.models import GrantResult
    from plugins.mailbox.models import ClaimOutcome
    from plugins.mailbox.models import ClaimTotal
    from plugins.mailbox.models import ClaimedMail
    from plugins.mailbox.render import render_claim_all
    from plugins.mailbox.render import render_inbox
    from plugins.mailbox.render import render_mail

    mails = [
        mailbox["_mail"](1, "维护补偿", attachments=[("season_point", 100)]),
        mailbox["_mail"](2, "赛季公告", days=1),
        mailbox["_mail"](
            3,
            "旧奖励",
            attachments=[("star_sticker", 20)],
            is_read=True,
        ),
    ]
    emit("mailbox-inbox", lambda: render_inbox(mails, kit))
    emit("mailbox-inbox-dense", lambda: render_inbox(mails * 4, kit))
    emit("mailbox-empty", lambda: render_inbox([], kit))
    grant = GrantResult("season_point", 100, 100, 100)
    emit("mail-detail-claimed", lambda: render_mail(mails[0], [grant], kit))
    emit("mail-detail-read", lambda: render_mail(mails[2], [], kit))
    claim_outcome = ClaimOutcome(
        claimed=(ClaimedMail(mail=mails[0], results=(grant,)),),
        totals=(ClaimTotal("season_point", 100),),
        remaining_notices=1,
        total_mails=3,
    )
    emit(
        "mail-claim-all",
        lambda: render_claim_all(claim_outcome, kit),
    )
    emit(
        "mail-claim-all-empty",
        lambda: render_claim_all(ClaimOutcome(total_mails=3), kit),
    )

    # Red envelopes: creation, active list, empty list, completion.
    envelopes = _test_namespace("test_red_envelope_render.py")
    from plugins.red_envelope.render import render_completion
    from plugins.red_envelope.render import render_create
    from plugins.red_envelope.render import render_list

    emit(
        "red-envelope-create",
        lambda: render_create(envelopes["_create_data"](), kit),
    )
    emit(
        "red-envelope-list",
        lambda: render_list(
            [
                envelopes["_list_item"](1),
                envelopes["_list_item"](2, urgent=True),
            ],
            kit,
        ),
    )
    emit("red-envelope-list-empty", lambda: render_list([], kit))
    emit(
        "red-envelope-completion",
        lambda: render_completion(envelopes["_completion_data"](), kit),
    )
    capped_claims = tuple(
        envelopes["ClaimRow"](
            name=f"成员{index}",
            amount=50 if index == 15 else index,
            is_lucky_king=index == 15,
        )
        for index in range(1, 16)
    )
    emit(
        "red-envelope-completion-capped",
        lambda: render_completion(
            envelopes["_completion_data"](
                claims=capped_claims,
                total_amount=sum(claim.amount for claim in capped_claims),
                total_count=len(capped_claims),
                lucky_king_name="成员15",
                lucky_king_amount=50,
            ),
            kit,
        ),
    )

    # Blackjack help/table/stats.
    from plugins.blackjack.help_render import render_help as render_blackjack_help
    from plugins.blackjack.stats_render import render_stats as render_blackjack_stats
    from plugins.blackjack.stats_render import stats_card_data

    blackjack_stats = _test_namespace("test_blackjack_stats_render.py")
    emit("blackjack-help", lambda: render_blackjack_help(kit))
    blackjack_paths = _preview_blackjack(kit_name, output_dir)
    for slug, original in zip(
        ("blackjack-hand", "blackjack-table"), blackjack_paths, strict=True
    ):
        emit(slug, lambda original=original: Image.open(original).convert("RGBA"))
        original.unlink(missing_ok=True)
    emit(
        "blackjack-stats",
        lambda: render_blackjack_stats(
            stats_card_data(
                blackjack_stats["_stats"](
                    recent_games=blackjack_stats["_records"](
                        [120, -200, 0, 340, -100, 400, -200]
                    )
                ),
                blackjack_stats["_identity"](),
            ),
            kit,
        ),
    )

    # Mines board, both settlements, and stats.
    from plugins.mines.models import GameResult
    from plugins.mines.render.result import render_result as render_mines_result
    from plugins.mines.render.stats import render_stats as render_mines_stats

    mines = _test_namespace("test_mines_render.py")
    mines_paths = _preview_mines(kit_name, output_dir)
    emit(
        "mines-board",
        lambda: Image.open(mines_paths[0]).convert("RGBA"),
    )
    mines_paths[0].unlink(missing_ok=True)
    emit(
        "mines-result-cashout",
        lambda: render_mines_result(
            mines["_result_data"](
                task_name="见好就收",
                task_reward=80,
                old_level=41,
                new_level=42,
                level_stickers=120,
            ),
            kit,
            identity=mines["_identity"](),
        ),
    )
    emit(
        "mines-result-loss",
        lambda: render_mines_result(
            mines["_result_data"](
                outcome=GameResult.LOSE,
                payout=0,
                multiplier=3.32,
                balance=1231,
            ),
            kit,
            identity=mines["_identity"](),
        ),
    )
    emit(
        "mines-stats",
        lambda: render_mines_stats(
            mines["_stats"](
                mines["_records"]([120, -200, 0, 340, -80, 900, -60])
            ),
            kit,
        ),
    )

    # One-stroke in-progress board, leaderboard, and full settlement.
    from plugins.one_stroke.render.result import OneStrokeResultData
    from plugins.one_stroke.render.result import render_result as render_stroke_result

    stroke_paths = _preview_one_stroke(kit_name, output_dir)
    for slug, original in zip(
        ("one-stroke-board", "one-stroke-leaderboard"),
        stroke_paths,
        strict=True,
    ):
        emit(slug, lambda original=original: Image.open(original).convert("RGBA"))
        original.unlink(missing_ok=True)
    emit(
        "one-stroke-result",
        lambda: render_stroke_result(
            OneStrokeResultData(
                difficulty="普通",
                elapsed_seconds=12.34,
                base_reward=120,
                decay_factor=0.86,
                final_reward=206,
                balance=3296,
                birthday_characters=("香澄",),
                previous_best_seconds=15.67,
                is_new_record=True,
                task_name="一气呵成",
                task_reward=80,
                old_level=41,
                new_level=42,
                level_stickers=120,
            ),
            kit,
            identity=PlayerIdentity(nickname="香澄", level=42),
        ),
    )

    # Other game reveal cards: win and timeout shapes.
    games = _test_namespace("test_games_other_reveals.py")
    from plugins.cck.render import render_reveal as render_cck_reveal
    from plugins.guess_chart.render import render_reveal as render_chart_reveal

    emit("cck-win", lambda: render_cck_reveal(games["_cck_win_data"](), kit))
    emit(
        "cck-timeout",
        lambda: render_cck_reveal(games["_cck_loss_data"]("timeout"), kit),
    )
    emit(
        "guess-chart-win",
        lambda: render_chart_reveal(games["_guess_chart_win_data"](), kit),
    )
    emit(
        "guess-chart-timeout",
        lambda: render_chart_reveal(
            games["_guess_chart_loss_data"](
                "timeout",
                jacket=games["_jacket"](),
            ),
            kit,
        ),
    )

    # Tour surfaces: rules, in-progress state, and settlement.
    # ``plugins.tour`` calls ``require("daily_task")`` while importing.
    import importlib

    importlib.import_module("plugins.daily_task")
    importlib.import_module("plugins.tour")
    from plugins.tour.models import TourOutcome
    from plugins.tour.render import TourRenderData
    from plugins.tour.render import TourResultData
    from plugins.tour.render import render_help as render_tour_help
    from plugins.tour.render import render_result as render_tour_result
    from plugins.tour.render import render_state as render_tour_state
    from plugins.tour.rules import DIFFICULTIES
    from plugins.tour.session import TourSession

    tour_snapshot = TourSession("preview", DIFFICULTIES["初级"], seed=13).snapshot()
    emit("tour-help", lambda: render_tour_help(kit))
    emit(
        "tour-state",
        lambda: render_tour_state(TourRenderData(tour_snapshot), kit),
    )
    emit(
        "tour-result",
        lambda: render_tour_result(
            TourResultData(
                snapshot=tour_snapshot,
                outcome=TourOutcome.WIN,
                reward_pt=24,
                balance=100,
                elapsed_seconds=42,
                base_reward_pt=12,
                birthday_names=("香澄",),
                multiplier=2,
                task_name="巡演开场",
                task_reward=80,
            ),
            kit,
        ),
    )

    # Ryuseido home, catalogs, theme states, and season bonus pull.
    from plugins.inventory.render import InventoryListData
    from plugins.inventory.render import InventoryListRow
    from plugins.inventory.render import render_inventory_list
    from plugins.ryuseido.render import ThemePreviewData
    from plugins.ryuseido.render import render_theme_preview

    shop_home = InventoryListData(
        title="流星堂",
        subtitle="旧藏流转",
        page=1,
        total_pages=1,
        rows=(
            InventoryListRow(
                index="A",
                name="立绘",
                detail="17 件 · 500–1400 盆",
                kind="立绘",
                show_art_slot=False,
                show_trailing=False,
            ),
            InventoryListRow(
                index="F",
                name="头像框",
                detail="2 件 · 1200–1800 盆",
                kind="头像框",
                show_art_slot=False,
                show_trailing=False,
            ),
            InventoryListRow(
                index="T",
                name="主题",
                detail="1 件 · 3000 盆",
                kind="主题",
                show_art_slot=False,
                show_trailing=False,
            ),
            InventoryListRow(
                index="P",
                name="本季加抽",
                detail="400 盆/抽 · 本季 2/5",
                kind="加抽",
                show_art_slot=False,
                show_trailing=False,
            ),
        ),
        footer="/流星堂 立绘 · 头像框 · 主题 · 加抽",
        wordmark_title="SHOP",
    )
    emit("shop-home", lambda: render_inventory_list(shop_home, kit))

    shop_standing_art = InventoryListData(
        title="流星堂",
        subtitle="立绘",
        page=1,
        total_pages=3,
        rows=(
            InventoryListRow(
                index="A01",
                name="牛込里美 守望着的应援",
                detail="500 盆栽",
                kind="立绘",
                rarity=3,
                art=kasumi_art,
            ),
            InventoryListRow(
                index="A03",
                name="青叶摩卡 温暖的时刻",
                detail="500 盆栽",
                kind="立绘",
                rarity=3,
                art=kasumi_art,
            ),
            InventoryListRow(
                index="A07",
                name="高松灯 不可思议的小动物",
                detail="已拥有",
                kind="立绘",
                rarity=4,
                art=kasumi_art,
                equipped=True,
            ),
        ),
        equipped_summary="已购入 A07",
        panel_footer="第 1/3 页",
        footer="/流星堂 立绘 <页码> · /流星堂 购买 <编号>",
        wordmark_title="SHOP",
    )
    emit(
        "shop-standing-art",
        lambda: render_inventory_list(shop_standing_art, kit),
    )

    frame_stardust = (
        ROOT
        / "plugins"
        / "inventory"
        / "resources"
        / "items"
        / "avatar_frames"
        / "frame_shop_stardust.png"
    )
    frame_azure = frame_stardust.with_name("frame_shop_azure_rhythm.png")
    shop_avatar_frames = InventoryListData(
        title="流星堂",
        subtitle="头像框",
        page=1,
        total_pages=1,
        rows=(
            InventoryListRow(
                index="F01",
                name="星屑玻璃",
                detail="1200 盆栽",
                kind="头像框",
                rarity=4,
                art=frame_stardust,
            ),
            InventoryListRow(
                index="F02",
                name="舞萌DX",
                detail="1800 盆栽",
                kind="头像框",
                rarity=5,
                art=frame_azure,
            ),
        ),
        panel_footer="第 1/1 页",
        footer="/流星堂 购买 <编号>",
        wordmark_title="SHOP",
    )
    emit(
        "shop-avatar-frame",
        lambda: render_inventory_list(shop_avatar_frames, kit),
    )

    shop_themes = InventoryListData(
        title="流星堂",
        subtitle="主题",
        page=1,
        total_pages=1,
        rows=(
            InventoryListRow(
                index="T01",
                name="樱色",
                detail="3000 盆栽",
                kind="主题",
                rarity=6,
                show_art_slot=False,
            ),
        ),
        panel_footer="第 1/1 页",
        footer="/流星堂 预览 <编号> · /流星堂 购买 <编号>",
        wordmark_title="SHOP",
    )
    emit("shop-theme-list", lambda: render_inventory_list(shop_themes, kit))

    from plugins.render.kits import KIT_DISPLAY_NAMES

    preview_data = ThemePreviewData(
        sku="T01",
        name=KIT_DISPLAY_NAMES[kit_name],
        description="使用本主题的实际背景、字体、面板和强调色。",
        price=3000,
    )
    emit(
        "shop-theme-preview",
        lambda: render_theme_preview(preview_data, kit),
    )
    emit(
        "shop-theme-preview-owned",
        lambda: render_theme_preview(
            replace(preview_data, owned=True, notice="已购入"),
            kit,
        ),
    )

    bonus_pull = replace(
        pull_page_data([featured], banner, item_art=pull_art),
        banner_name=f"流星堂 · {banner.name}",
    )
    emit(
        "shop-bonus-pull",
        lambda: render_pull(bonus_pull, kit),
    )

    return outputs, failures


def main() -> None:
    from plugins.render.kits import KITS

    parser = argparse.ArgumentParser(
        description="Render every representative player-facing image in one kit."
    )
    parser.add_argument(
        "--kit",
        default="kasumi",
        choices=sorted(KITS),
        help="Render kit used for every preview.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="Directory for the generated PNG gallery.",
    )
    args = parser.parse_args()

    output_dir = (
        args.output_dir
        or ROOT / ".cache" / "render-previews" / f"{args.kit}-all"
    ).resolve()
    outputs, failures = _render_gallery(output_dir, args.kit)
    print(f"\nGenerated {len(outputs)} images in {output_dir}")
    if failures:
        print(f"{len(failures)} render(s) failed:")
        for failure in failures:
            print(f"  - {failure}")
        raise SystemExit(1)


if __name__ == "__main__":
    main()
