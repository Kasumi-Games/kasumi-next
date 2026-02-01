import cv2
import json
from pathlib import Path
from nonebot.log import logger
from nonebot.params import CommandArg
from typing import Optional
from nonebot.exception import MatcherException
from nonebot import on_command, require, get_driver
from nonebot.adapters.satori import MessageEvent, Message, MessageSegment

require("cck")  # for card images
require("nonebot_plugin_waiter")
require("nonebot_plugin_localstore")

from nonebot_plugin_waiter import waiter  # noqa: E402

from .. import monetary  # noqa: E402
from ..cck import card_manager  # noqa: E402
from utils.passive_generator import generators as gens  # noqa: E402
from utils.passive_generator import PassiveGenerator as PG  # noqa: E402

from .database import init_database  # noqa: E402
from .render import BlackjackRenderer  # noqa: E402
from .models import Hand  # noqa: E402
from .stats_service import get_blackjack_stats, create_win_loss_chart  # noqa: E402
from .session import GameManager  # noqa: E402
from .messages import Messages  # noqa: E402
from .handlers import (  # noqa: E402
    get_bet_amount,
    handle_initial_blackjack,
    handle_split_decision,
    handle_split_game,
    handle_normal_game,
)


HELP_MESSAGE = MessageSegment.image(
    raw=Path("plugins/blackjack/recourses/instruction.png").read_bytes(),
    mime="image/png",
)

game_manager = GameManager()
renderer: BlackjackRenderer = None


def not_in_game(event: MessageEvent) -> bool:
    return not game_manager.is_in_game(event.get_user_id())


game_start = on_command(
    "黑香澄",
    aliases={
        "blackjack",
        "blackkasumi",
        "blackasumi",
        "bk",
        "bj",
        "黑杰克",
        "二十一点",
    },
    priority=10,
    block=True,
    rule=not_in_game,
)
game_stats = on_command(
    "黑香澄统计",
    aliases={
        "bkstats",
        "bjstats",
        "bk统计",
        "bj统计",
        "bks",
        "bjs",
    },
    priority=10,
    block=True,
)


@get_driver().on_startup
async def init_blackjack():
    global renderer

    # Initialize database
    init_database()

    # Initialize renderer
    renderer = BlackjackRenderer(
        resource_dir="plugins/blackjack/recourses",
        card_data=card_manager.__summary_data__,
        character_data=json.loads(
            Path("plugins/blackjack/recourses/character_data.json").read_text(
                encoding="utf-8"
            )
        ),
        face_positions=json.loads(
            Path("plugins/blackjack/recourses/face_positions.json").read_text(
                encoding="utf-8"
            )
        ),
        cascade=cv2.CascadeClassifier(
            "plugins/blackjack/recourses/lbpcascade_animeface.xml"
        ),
    )
    game_manager.set_renderer(renderer)


@get_driver().on_shutdown
async def shutdown_blackjack():
    # 返还正在进行游戏中的玩家碎片
    logger.info("返还正在进行游戏中的玩家碎片")
    for user_id in game_manager.get_active_players():
        game_manager.refund_game(user_id)


@game_start.handle()
async def handle_start(event: MessageEvent, arg: Optional[Message] = CommandArg()):
    gens[event.message.id] = PG(event)
    latest_message_id = event.message.id

    @waiter(waits=["message"], matcher=game_start, block=False, keep_session=True)
    async def check(event_: MessageEvent) -> MessageEvent:
        return event_

    arg_text = arg.extract_plain_text().strip()

    if arg_text in ["h", "-h", "--help", "help"]:
        await game_start.finish(HELP_MESSAGE + gens[latest_message_id].element)

    try:
        bet_amount, latest_message_id = await get_bet_amount(
            arg_text, latest_message_id, check, game_start
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

        if game_manager.reshuffle_if_needed(event.channel.id):
            await game_start.send(Messages.RESHUFFLE + gens[latest_message_id].element)

        player_hand = Hand()
        dealer_hand = Hand()

        player_hand.add_card(game_manager.get_shoe(event.channel.id).deal())
        dealer_hand.add_card(game_manager.get_shoe(event.channel.id).deal())
        player_hand.add_card(game_manager.get_shoe(event.channel.id).deal())
        dealer_hand.add_card(game_manager.get_shoe(event.channel.id).deal())

        session = game_manager.create_session(
            event.get_user_id(),
            event.channel.id,
            bet_amount,
            player_hand,
            dealer_hand,
        )

        if await handle_initial_blackjack(
            session, bet_amount, latest_message_id, game_start, game_manager
        ):
            return

        split_card, bet_amount, latest_message_id = await handle_split_decision(
            session,
            bet_amount,
            event,
            latest_message_id,
            check,
            game_start,
            game_manager,
        )
        session.bet_amount = bet_amount

        if split_card:
            await handle_split_game(
                session,
                bet_amount,
                event,
                latest_message_id,
                check,
                game_start,
                game_manager,
            )
        else:
            await handle_normal_game(
                session,
                bet_amount,
                event,
                latest_message_id,
                check,
                game_start,
                game_manager,
            )
    except MatcherException:
        raise
    except Exception as e:
        # 发生错误时退还下注金额
        game_manager.refund_game(event.get_user_id())
        logger.error("Blackjack error: " + str(e), exc_info=True)
        logger.exception(e)
        await game_start.finish(
            "发生意外错误！下注已退回给你，再试一次吧？"
            + gens[latest_message_id].element
        )


@game_stats.handle()
async def handle_stats(event: MessageEvent):
    """处理黑香澄统计信息查询"""
    user_id = event.get_user_id()
    gens[event.message.id] = PG(event)

    try:
        # 获取玩家的blackjack统计数据
        stats = get_blackjack_stats(user_id)

        if stats.total_games == 0:
            await game_stats.finish(
                "你还没有玩过黑香澄游戏哦，快来试试吧！"
                + gens[event.message.id].element
            )

        # 构建统计信息文本
        stats_text = f"""🎴 黑香澄游戏统计
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
            response_message += MessageSegment.text("\n📊 图表生成失败")

        response_message += gens[event.message.id].element
        await game_stats.finish(response_message)

    except MatcherException:
        raise
    except Exception as e:
        logger.error(f"获取blackjack统计信息时出错: {e}", exc_info=True)
        await game_stats.finish(
            "获取统计信息时出现错误，请稍后再试" + gens[event.message.id].element
        )
