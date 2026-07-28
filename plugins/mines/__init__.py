from typing import Tuple
from typing import Optional

from nonebot import require
from nonebot import get_driver
from nonebot import on_command
from nonebot.log import logger
from nonebot.params import CommandArg
from nonebot.exception import MatcherException
from nonebot.adapters.satori import Message
from nonebot.adapters.satori import MessageEvent
from nonebot.adapters.satori import MessageSegment

from utils.avatar import get_avatar
from utils.images import image_segment
from utils.theming import kit_for_user
from plugins.render import BaseKit
from plugins.render import PlayerIdentity
from utils.identity import identity_for
from utils.error_handler import handle_error

require("daily_task")
require("nonebot_plugin_waiter")

from nonebot_plugin_waiter import waiter  # noqa: E402

from utils.passive_generator import PassiveGenerator as PG  # noqa: E402
from utils.passive_generator import generators as gens  # noqa: E402

from .. import monetary  # noqa: E402
from ..inventory.season_service import get_current_season_bounds  # noqa: E402
from .models import BlockType  # noqa: E402
from .models import GameResult  # noqa: E402
from .render import MinesResultData  # noqa: E402
from .render import render  # noqa: E402
from .render import stats_page  # noqa: E402
from .render import result_page  # noqa: E402
from .session import GameManager  # noqa: E402
from .session import GameSession  # noqa: E402
from .database import init_database  # noqa: E402
from .messages import Messages  # noqa: E402
from ..daily_task import check_progress  # noqa: E402
from ..daily_task import get_today_task  # noqa: E402
from .stats_service import get_mines_stats  # noqa: E402
from ..monetary.level_service import LEVEL_UP_STICKERS  # noqa: E402

game_manager = GameManager()


def _render_field_image(
    field, kit=None, identity=None, detail=None
) -> MessageSegment:
    """Render the game field to an image MessageSegment."""
    return image_segment(render(field, kit=kit, identity=identity, detail=detail))


async def _send_result_card(
    matcher,
    session: GameSession,
    result: GameResult,
    payout: int,
    multiplier: float,
    kit: BaseKit,
    identity: PlayerIdentity,
    pg: PG,
) -> None:
    """Award round rewards, then send the single round-end result card.

    Collapses what used to be three sends (result text, daily-task notice,
    level-up notice) into one card. The reward services are awaited BEFORE
    rendering, each individually guarded: a task/level failure degrades to a
    card without that row, never to a missing result.
    """
    user_id = session.user_id
    task_name: Optional[str] = None
    task_reward: Optional[int] = None
    old_level: Optional[int] = None
    new_level: Optional[int] = None
    level_stickers: Optional[int] = None

    if result is not GameResult.LOSE:
        try:
            task_msg = await check_progress(
                user_id, "mines_cashout", {"multiplier": multiplier}
            )
            if task_msg:
                task_cfg = get_today_task(user_id)
                task_name = task_cfg.name
                task_reward = task_cfg.reward
        except Exception:
            logger.opt(exception=True).warning("探险每日任务结算失败")

        # XP scales with multiplier: starts at 5 at 2.0x
        if multiplier >= 2.0:
            try:
                level_before = monetary.get_level(user_id)
                leveled = await monetary.add_xp(user_id, int(multiplier * 2.5))
                level_after = monetary.get_level(user_id)
                if leveled and level_after > level_before:
                    old_level = level_before
                    new_level = level_after
                    level_stickers = (level_after - level_before) * LEVEL_UP_STICKERS
            except Exception:
                logger.opt(exception=True).warning("探险经验结算失败")

    data = MinesResultData(
        outcome=result,
        bet_amount=session.bet_amount,
        payout=payout,
        multiplier=multiplier,
        revealed_count=session.revealed_count,
        safe_cells=session.safe_cells,
        mines=session.mines,
        balance=monetary.get(user_id),
        task_name=task_name,
        task_reward=task_reward,
        old_level=old_level,
        new_level=new_level,
        level_stickers=level_stickers,
    )
    image = await result_page(data, kit, identity=identity).render_async()
    await matcher.send(
        image_segment(image) + pg.element,
        referrer=pg.event.referrer,
    )


@get_driver().on_startup
async def init_mines():
    init_database()
    logger.info("扫雷插件初始化完成")


def not_in_game(event: MessageEvent) -> bool:
    return not game_manager.is_in_game(event.get_user_id())


game_start = on_command(
    "扫雷",
    aliases={"mines", "探险", "mk"},
    priority=10,
    block=True,
    rule=not_in_game,
)
game_stats = on_command(
    "扫雷统计",
    aliases={"minesstats", "探险统计", "mks"},
    priority=10,
    block=True,
)


def _format_status(session) -> str:
    payout = session.get_payout()
    return (
        f"已翻开 {session.revealed_count}/{session.safe_cells} | "
        f"当前倍率 {session.multiplier:.4f}x | 可结算 {payout} 个Pt"
    )


def _parse_args(arg_text: str) -> Tuple[Optional[int], Optional[int]]:
    parts = [part for part in arg_text.split() if part]
    if not parts:
        return None, None

    bet_amount = None
    mines = None
    try:
        bet_amount = int(parts[0])
    except ValueError:
        bet_amount = None

    if len(parts) >= 2:
        try:
            mines = int(parts[1])
        except ValueError:
            mines = None

    return bet_amount, mines


async def _get_bet_amount(
    bet_amount: Optional[int],
    latest_message_id: str,
    check,
    matcher,
) -> Tuple[int, str]:
    if bet_amount is None:
        await matcher.send(
            Messages.BET_PROMPT + gens[latest_message_id].element,
            referrer=gens[latest_message_id].event.referrer,
        )
        resp = await check.wait(timeout=60)
        if resp is None:
            await matcher.finish(
                Messages.BET_TIMEOUT + gens[latest_message_id].element,
                referrer=gens[latest_message_id].event.referrer,
            )
        latest_message_id = resp.message.id
        gens[latest_message_id] = PG(resp)
        try:
            bet_amount = int(str(resp.get_message()).strip())
        except ValueError:
            await matcher.finish(
                Messages.BET_INVALID + gens[latest_message_id].element,
                referrer=gens[latest_message_id].event.referrer,
            )

    if bet_amount <= 0:
        await matcher.finish(
            Messages.BET_TOO_SMALL + gens[latest_message_id].element,
            referrer=gens[latest_message_id].event.referrer,
        )

    return bet_amount, latest_message_id


@game_start.handle()
async def handle_start(event: MessageEvent, arg: Optional[Message] = CommandArg()):
    gens[event.message.id] = PG(event)
    latest_message_id = event.message.id

    @waiter(waits=["message"], matcher=game_start, block=True, keep_session=True)
    async def check(event_: MessageEvent) -> MessageEvent:
        return event_

    arg_text = arg.extract_plain_text().strip()

    if arg_text in ["h", "--help", "help", "-h"]:
        await game_start.finish(
            Messages.HELP + gens[latest_message_id].element,
            referrer=gens[latest_message_id].event.referrer,
        )

    if arg_text in ["f", "-f"]:
        session = game_manager.get_session(event.get_user_id())
        if session is None:
            await game_start.finish(
                "没有正在进行的扫雷游戏" + gens[latest_message_id].element,
                referrer=gens[latest_message_id].event.referrer,
            )
        game_manager.refund_game(event.get_user_id())
        await game_start.finish(
            "已强制退出扫雷游戏" + gens[latest_message_id].element,
            referrer=gens[latest_message_id].event.referrer,
        )

    parts = [part for part in arg_text.split() if part]
    bet_amount, mines = _parse_args(arg_text)

    try:
        bet_amount, latest_message_id = await _get_bet_amount(
            bet_amount, latest_message_id, check, game_start
        )

        if len(parts) >= 2 and mines is None:
            await game_start.finish(
                Messages.MINES_INVALID + gens[latest_message_id].element,
                referrer=gens[latest_message_id].event.referrer,
            )
        if mines is None:
            mines = 5
        if mines <= 0:
            await game_start.finish(
                Messages.MINES_TOO_SMALL + gens[latest_message_id].element,
                referrer=gens[latest_message_id].event.referrer,
            )
        if mines >= 25:
            await game_start.finish(
                Messages.MINES_TOO_LARGE + gens[latest_message_id].element,
                referrer=gens[latest_message_id].event.referrer,
            )

        if not game_manager.start_game(event.get_user_id(), bet_amount):
            if game_manager.is_in_game(event.get_user_id()):
                await game_start.finish(
                    Messages.ALREADY_IN_GAME + gens[latest_message_id].element,
                    referrer=gens[latest_message_id].event.referrer,
                )
            await game_start.finish(
                Messages.BET_NOT_ENOUGH.format(amount=monetary.get(event.get_user_id()))
                + gens[latest_message_id].element,
                referrer=gens[latest_message_id].event.referrer,
            )

        session = game_manager.create_session(
            event.get_user_id(), event.channel.id, bet_amount, mines
        )

        # Resolved once per game on the event-loop thread, then passed into
        # every render below; renderers never resolve theme or identity. The
        # avatar is fetched once here — the cache makes per-dig renders cheap
        # — and None keeps the initial-badge fallback.
        kit = kit_for_user(event.get_user_id())
        avatar = await get_avatar(event.get_user_id())
        identity = identity_for(event.get_user_id(), avatar=avatar)
        detail = f"押注 {bet_amount} Pt · 剩 {mines} 雷"

        await game_start.send(
            _render_field_image(session.field, kit=kit, identity=identity, detail=detail)
            + MessageSegment.text(
                Messages.START.format(number=mines)
                + "\n"
                + _format_status(session)
                + "\n"
                + Messages.PROMPT
            )
            + gens[latest_message_id].element,
            referrer=gens[latest_message_id].event.referrer,
        )

        while True:
            resp = await check.wait(timeout=180)
            if resp is None:
                game_manager.end_game(event.get_user_id(), GameResult.TIMEOUT, payout=0)
                await game_start.finish(
                    Messages.TIMEOUT + gens[latest_message_id].element,
                    referrer=gens[latest_message_id].event.referrer,
                )

            msg = str(resp.get_message()).strip()
            latest_message_id = resp.message.id
            gens[latest_message_id] = PG(resp)

            if msg in ["f", "-f"]:
                game_manager.refund_game(event.get_user_id())
                await game_start.finish(
                    "已强制退出扫雷游戏" + gens[latest_message_id].element,
                    referrer=gens[latest_message_id].event.referrer,
                )

            if msg in {"收手", "结算", "stop", "s"}:
                payout = session.get_payout()
                cashout_multiplier = session.multiplier  # Save before end_game
                game_manager.end_game(
                    event.get_user_id(), GameResult.CASHOUT, payout=payout
                )
                session.field.reveal_all_mines()

                # The final revealed board is the game state and keeps its
                # own send; everything else collapses into one result card.
                await game_start.send(
                    _render_field_image(
                        session.field, kit=kit, identity=identity, detail=detail
                    )
                    + gens[latest_message_id].element,
                    referrer=gens[latest_message_id].event.referrer,
                )
                await _send_result_card(
                    game_start,
                    session,
                    GameResult.CASHOUT,
                    payout,
                    cashout_multiplier,
                    kit,
                    identity,
                    gens[latest_message_id],
                )
                await game_start.finish(referrer=event.referrer)

            if not msg.isdigit():
                await game_start.send(
                    Messages.INPUT_INVALID + gens[latest_message_id].element,
                    referrer=gens[latest_message_id].event.referrer,
                )
                continue

            index = int(msg) - 1
            if index < 0 or index >= 25:
                await game_start.send(
                    Messages.INPUT_INVALID + gens[latest_message_id].element,
                    referrer=gens[latest_message_id].event.referrer,
                )
                continue

            if index in session.revealed_indices:
                await game_start.send(
                    Messages.ALREADY_REVEALED + gens[latest_message_id].element,
                    referrer=gens[latest_message_id].event.referrer,
                )
                continue

            block = session.field.reveal_block(index)
            if block == BlockType.MINE:
                session.field.reveal_all_mines()
                game_manager.end_game(event.get_user_id(), GameResult.LOSE, payout=0)
                await game_start.send(
                    _render_field_image(
                        session.field, kit=kit, identity=identity, detail=detail
                    )
                    + gens[latest_message_id].element,
                    referrer=gens[latest_message_id].event.referrer,
                )
                await _send_result_card(
                    game_start,
                    session,
                    GameResult.LOSE,
                    0,
                    session.multiplier,
                    kit,
                    identity,
                    gens[latest_message_id],
                )
                await game_start.finish(referrer=event.referrer)

            session.revealed_indices.add(index)
            session.update_multiplier()

            if session.revealed_count >= session.safe_cells:
                payout = session.get_payout()
                win_multiplier = session.multiplier
                game_manager.end_game(
                    event.get_user_id(), GameResult.WIN, payout=payout
                )
                session.field.reveal_all_mines()

                # The final revealed board is the game state and keeps its
                # own send; everything else collapses into one result card.
                await game_start.send(
                    _render_field_image(
                        session.field, kit=kit, identity=identity, detail=detail
                    )
                    + gens[latest_message_id].element,
                    referrer=gens[latest_message_id].event.referrer,
                )
                await _send_result_card(
                    game_start,
                    session,
                    GameResult.WIN,
                    payout,
                    win_multiplier,
                    kit,
                    identity,
                    gens[latest_message_id],
                )
                await game_start.finish(referrer=event.referrer)

            await game_start.send(
                _render_field_image(
                    session.field, kit=kit, identity=identity, detail=detail
                )
                + MessageSegment.text(
                    Messages.SAFE_REVEAL
                    + "\n"
                    + _format_status(session)
                    + "\n"
                    + Messages.PROMPT
                )
                + gens[latest_message_id].element,
                referrer=gens[latest_message_id].event.referrer,
            )

    except MatcherException:
        raise
    except Exception as e:
        game_manager.refund_game(event.get_user_id())
        code = handle_error(e, context="mines", user_id=event.get_user_id())
        await game_start.finish(
            MessageSegment.text("错误码：{}\n".format(code))
            + Messages.ERROR
            + gens[latest_message_id].element,
            referrer=gens[latest_message_id].event.referrer,
        )


@game_stats.handle()
async def handle_stats(event: MessageEvent):
    """处理地下室探险统计信息查询"""
    user_id = event.get_user_id()
    gens[event.message.id] = PG(event)

    try:
        season_bounds = get_current_season_bounds()
        if season_bounds is None:
            await game_stats.finish(
                "当前赛季尚未开启，赛季战绩会在开季后开始统计。"
                + gens[event.message.id].element,
                referrer=gens[event.message.id].event.referrer,
            )

        # Only completed games inside the current season count towards this card.
        stats = get_mines_stats(
            user_id, start_time=season_bounds[0], end_time=season_bounds[1]
        )

        if stats.total_games == 0:
            await game_stats.finish(
                "本赛季还没有探险记录，快来试试吧！"
                + gens[event.message.id].element,
                referrer=gens[event.message.id].event.referrer,
            )

        # Theme resolved on the event loop thread; the renderer only draws.
        kit = kit_for_user(user_id)
        image = await stats_page(stats, kit).render_async()
        await game_stats.finish(
            image_segment(image) + gens[event.message.id].element,
            referrer=event.referrer,
        )

    except MatcherException:
        raise
    except Exception as e:
        code = handle_error(e, context="mines_stats", user_id=event.get_user_id())
        await game_stats.finish(
            "统计查询失败，请稍后再试\n错误码：{}".format(code)
            + gens[event.message.id].element,
            referrer=gens[event.message.id].event.referrer,
        )
