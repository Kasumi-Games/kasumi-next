from __future__ import annotations

import io
from typing import Optional, Tuple

from PIL import Image
from nonebot.log import logger
from nonebot.params import CommandArg
from nonebot.exception import MatcherException
from nonebot import get_driver, on_command, require
from nonebot.adapters.satori import Message, MessageEvent, MessageSegment

require("nonebot_plugin_waiter")

from nonebot_plugin_waiter import waiter  # noqa: E402

from utils.passive_generator import generators as gens  # noqa: E402
from utils.passive_generator import PassiveGenerator as PG  # noqa: E402

from .. import monetary  # noqa: E402
from .render import render  # noqa: E402
from .messages import Messages  # noqa: E402
from .session import GameManager  # noqa: E402
from .database import init_database  # noqa: E402
from .models import BlockType, GameResult  # noqa: E402
from .stats_service import get_mines_stats, create_win_loss_chart  # noqa: E402

game_manager = GameManager()


def _render_field_image(field) -> MessageSegment:
    """Render the game field to an image MessageSegment."""
    img: Image.Image = render(field)
    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    return MessageSegment.image(raw=buffer, mime="image/png")


@get_driver().on_startup
async def init_mines():
    init_database()
    logger.info("扫雷插件初始化完成")


def not_in_game(event: MessageEvent) -> bool:
    return not game_manager.is_in_game(event.get_user_id())


game_start = on_command(
    "扫雷",
    aliases={"mines", "探险", "m"},
    priority=10,
    block=True,
    rule=not_in_game,
)
game_stats = on_command(
    "扫雷统计",
    aliases={"minesstats", "探险统计", "ms"},
    priority=10,
    block=True,
)


def _format_status(session) -> str:
    payout = session.get_payout()
    return (
        f"已翻开 {session.revealed_count}/{session.safe_cells} | "
        f"当前倍率 {session.multiplier:.4f}x | 可结算 {payout} 个星之碎片"
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
        await matcher.send(Messages.BET_PROMPT + gens[latest_message_id].element)
        resp = await check.wait(timeout=60)
        if resp is None:
            await matcher.finish(Messages.BET_TIMEOUT + gens[latest_message_id].element)
        latest_message_id = resp.message.id
        gens[latest_message_id] = PG(resp)
        try:
            bet_amount = int(str(resp.get_message()).strip())
        except ValueError:
            await matcher.finish(Messages.BET_INVALID + gens[latest_message_id].element)

    if bet_amount <= 0:
        await matcher.finish(Messages.BET_TOO_SMALL + gens[latest_message_id].element)

    return bet_amount, latest_message_id


@game_start.handle()
async def handle_start(event: MessageEvent, arg: Optional[Message] = CommandArg()):
    gens[event.message.id] = PG(event)
    latest_message_id = event.message.id

    @waiter(waits=["message"], matcher=game_start, block=False, keep_session=True)
    async def check(event_: MessageEvent) -> MessageEvent:
        return event_

    arg_text = arg.extract_plain_text().strip()

    if arg_text in ["h", "--help", "help", "-h"]:
        await game_start.finish(Messages.HELP + gens[latest_message_id].element)

    parts = [part for part in arg_text.split() if part]
    bet_amount, mines = _parse_args(arg_text)

    try:
        bet_amount, latest_message_id = await _get_bet_amount(
            bet_amount, latest_message_id, check, game_start
        )

        if len(parts) >= 2 and mines is None:
            await game_start.finish(
                Messages.MINES_INVALID + gens[latest_message_id].element
            )
        if mines is None:
            mines = 5
        if mines <= 0:
            await game_start.finish(
                Messages.MINES_TOO_SMALL + gens[latest_message_id].element
            )
        if mines >= 25:
            await game_start.finish(
                Messages.MINES_TOO_LARGE + gens[latest_message_id].element
            )

        if not game_manager.start_game(event.get_user_id(), bet_amount):
            if game_manager.is_in_game(event.get_user_id()):
                await game_start.finish(
                    Messages.ALREADY_IN_GAME + gens[latest_message_id].element
                )
            await game_start.finish(
                Messages.BET_NOT_ENOUGH.format(amount=monetary.get(event.get_user_id()))
                + gens[latest_message_id].element
            )

        session = game_manager.create_session(
            event.get_user_id(), event.channel.id, bet_amount, mines
        )

        await game_start.send(
            _render_field_image(session.field)
            + MessageSegment.text(
                Messages.START.format(number=mines)
                + "\n"
                + _format_status(session)
                + "\n"
                + Messages.PROMPT
            )
            + gens[latest_message_id].element
        )

        while True:
            resp = await check.wait(timeout=180)
            if resp is None:
                game_manager.end_game(event.get_user_id(), GameResult.TIMEOUT, payout=0)
                await game_start.finish(
                    Messages.TIMEOUT + gens[latest_message_id].element
                )

            msg = str(resp.get_message()).strip()
            latest_message_id = resp.message.id
            gens[latest_message_id] = PG(resp)

            if msg in {"收手", "结算", "stop", "s"}:
                payout = session.get_payout()
                game_manager.end_game(
                    event.get_user_id(), GameResult.CASHOUT, payout=payout
                )
                session.field.reveal_all_mines()
                await game_start.finish(
                    _render_field_image(session.field)
                    + MessageSegment.text(
                        Messages.CASHOUT
                        + "\n"
                        + f"获得 {payout} 个星之碎片，"
                        + f"现在有 {monetary.get(event.get_user_id())} 个碎片"
                    )
                    + gens[latest_message_id].element
                )

            if not msg.isdigit():
                await game_start.send(
                    Messages.INPUT_INVALID + gens[latest_message_id].element
                )
                continue

            index = int(msg) - 1
            if index < 0 or index >= 25:
                await game_start.send(
                    Messages.INPUT_INVALID + gens[latest_message_id].element
                )
                continue

            if index in session.revealed_indices:
                await game_start.send(
                    Messages.ALREADY_REVEALED + gens[latest_message_id].element
                )
                continue

            block = session.field.reveal_block(index)
            if block == BlockType.MINE:
                session.field.reveal_all_mines()
                game_manager.end_game(event.get_user_id(), GameResult.LOSE, payout=0)
                await game_start.finish(
                    _render_field_image(session.field)
                    + MessageSegment.text(
                        Messages.HIT_MINE
                        + "\n"
                        + f"损失 {session.bet_amount} 个星之碎片，"
                        + f"现在有 {monetary.get(event.get_user_id())} 个碎片"
                    )
                    + gens[latest_message_id].element
                )

            session.revealed_indices.add(index)
            session.update_multiplier()

            if session.revealed_count >= session.safe_cells:
                payout = session.get_payout()
                game_manager.end_game(
                    event.get_user_id(), GameResult.WIN, payout=payout
                )
                session.field.reveal_all_mines()
                await game_start.finish(
                    _render_field_image(session.field)
                    + MessageSegment.text(
                        Messages.CASHOUT
                        + "\n"
                        + f"获得 {payout} 个星之碎片，"
                        + f"现在有 {monetary.get(event.get_user_id())} 个碎片"
                    )
                    + gens[latest_message_id].element
                )

            await game_start.send(
                _render_field_image(session.field)
                + MessageSegment.text(
                    Messages.SAFE_REVEAL
                    + "\n"
                    + _format_status(session)
                    + "\n"
                    + Messages.PROMPT
                )
                + gens[latest_message_id].element
            )

    except MatcherException:
        raise
    except Exception as e:
        logger.error(f"扫雷游戏发生错误: {e}", exc_info=True)
        game_manager.refund_game(event.get_user_id())
        await game_start.finish(Messages.ERROR + gens[latest_message_id].element)


@game_stats.handle()
async def handle_stats(event: MessageEvent):
    """处理地下室探险统计信息查询"""
    user_id = event.get_user_id()
    gens[event.message.id] = PG(event)

    try:
        # 获取玩家的mines统计数据
        stats = get_mines_stats(user_id)

        if stats.total_games == 0:
            await game_stats.finish(
                Messages.STATS_EMPTY + gens[event.message.id].element
            )

        # 构建统计信息文本
        stats_text = f"""🏚️ 地下室探险统计
📊 {stats.total_games}局 | 胜{stats.wins} 负{stats.losses} | 胜率{stats.win_rate:.1%}
💰 投入{stats.total_wagered} | 得{stats.total_won} 失{stats.total_lost} | 净收益{stats.net_profit:+d}
🎰 平均赌注{stats.avg_bet:.1f} | 平均赢{stats.avg_win:.1f} | 平均输{stats.avg_loss:.1f}
🏆 最高赢{stats.biggest_win} | 最高输{stats.biggest_loss}"""

        # 尝试生成图表
        chart_bytes = create_win_loss_chart(stats)

        # 发送统计信息
        response_message = MessageSegment.text(stats_text)

        if chart_bytes:
            # 如果成功生成图表，添加图表
            response_message += MessageSegment.image(raw=chart_bytes, mime="image/png")
        else:
            response_message += MessageSegment.text("\n📊 图表生成需要至少2局游戏记录")

        response_message += gens[event.message.id].element
        await game_stats.finish(response_message)

    except MatcherException:
        raise
    except Exception as e:
        logger.error(f"扫雷统计发生错误: {e}", exc_info=True)
        await game_stats.finish(
            "统计查询失败，请稍后再试" + gens[event.message.id].element
        )
