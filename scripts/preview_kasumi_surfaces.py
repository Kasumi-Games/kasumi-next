"""Render a visual census of every player-facing image in the Kasumi kit.

This script deliberately reuses the representative, handler-shaped fixtures
from the render tests.  That keeps the preview gallery aligned with the actual
cards without inventing a second set of stale demo models.
"""

from __future__ import annotations

import argparse
import os
import runpy
import sys
from collections.abc import Callable
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_DIR = ROOT / ".cache" / "render-previews" / "kasumi-all"

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


def _render_gallery(output_dir: Path) -> tuple[list[Path], list[str]]:
    from plugins.render import PlayerIdentity
    from plugins.render.kits import KasumiKit

    kit = KasumiKit()
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

    gacha = _test_namespace("test_gacha_render.py")
    from plugins.gacha.render import pull_page_data
    from plugins.gacha.render import render_pull

    kasumi_art = gacha["KASUMI_ART"]
    pull_art = {
        "standing_art_kasumi_starbeat": kasumi_art,
        "standing_art_placeholder_r3_001": (
            ROOT
            / "plugins"
            / "gacha"
            / "resources"
            / "standing"
            / "ran_tiptoe_after_training.png"
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
    from scripts.preview_renderers import preview_blackjack

    blackjack_stats = _test_namespace("test_blackjack_stats_render.py")
    emit("blackjack-help", lambda: render_blackjack_help(kit))
    blackjack_paths = preview_blackjack("kasumi", output_dir)
    for slug, original in zip(
        ("blackjack-hand", "blackjack-table"), blackjack_paths, strict=True
    ):
        emit(slug, lambda original=original: Image.open(original).convert("RGBA"))
        original.unlink(missing_ok=True)
    emit(
        "blackjack-stats",
        lambda: render_blackjack_stats(
            stats_card_data(
                blackjack_stats["_stats"](),
                blackjack_stats["_identity"](),
            ),
            kit,
        ),
    )

    # Mines board, both settlements, and stats.
    from plugins.mines.models import GameResult
    from plugins.mines.render.result import render_result as render_mines_result
    from plugins.mines.render.stats import render_stats as render_mines_stats
    from scripts.preview_renderers import preview_mines

    mines = _test_namespace("test_mines_render.py")
    mines_paths = preview_mines("kasumi", output_dir)
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
    from scripts.preview_renderers import preview_one_stroke

    stroke_paths = preview_one_stroke("kasumi", output_dir)
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

    return outputs, failures


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Render every representative player-facing image in the Kasumi kit."
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help="Directory for the generated PNG gallery.",
    )
    args = parser.parse_args()

    outputs, failures = _render_gallery(args.output_dir.resolve())
    print(f"\nGenerated {len(outputs)} images in {args.output_dir.resolve()}")
    if failures:
        print(f"{len(failures)} render(s) failed:")
        for failure in failures:
            print(f"  - {failure}")
        raise SystemExit(1)


if __name__ == "__main__":
    main()
