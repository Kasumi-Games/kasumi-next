import json
from typing import Optional
from pathlib import Path

import cv2
from nonebot import require
from nonebot import get_driver
from nonebot import on_command
from nonebot.log import logger
from nonebot.params import CommandArg
from nonebot.exception import MatcherException
from nonebot.adapters.satori import Message
from nonebot.adapters.satori import MessageEvent
from nonebot.adapters.satori import MessageSegment

from utils.images import image_segment
from utils.theming import kit_for_user
from utils.identity import identity_for
from utils.error_handler import handle_error

require("cck")  # for card images
require("nonebot_plugin_waiter")
require("nonebot_plugin_localstore")

from nonebot_plugin_waiter import waiter  # noqa: E402

from utils.passive_generator import PassiveGenerator as PG  # noqa: E402
from utils.passive_generator import generators as gens  # noqa: E402

from .. import monetary  # noqa: E402
from ..cck import card_manager  # noqa: E402
from .models import Hand  # noqa: E402
from .render import BlackjackRenderer  # noqa: E402
from .session import GameManager  # noqa: E402
from .database import init_database  # noqa: E402
from .handlers import get_bet_amount  # noqa: E402
from .handlers import handle_split_game  # noqa: E402
from .handlers import handle_normal_game  # noqa: E402
from .handlers import handle_split_decision  # noqa: E402
from .handlers import handle_initial_blackjack  # noqa: E402
from .messages import Messages  # noqa: E402
from .stats_render import stats_page  # noqa: E402
from .stats_render import stats_card_data  # noqa: E402
from .stats_service import get_blackjack_stats  # noqa: E402

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
    # 返还正在进行游戏中的玩家Pt
    logger.info("返还正在进行游戏中的玩家Pt")
    for user_id in game_manager.get_active_players():
        game_manager.refund_game(user_id)


@game_start.handle()
async def handle_start(event: MessageEvent, arg: Optional[Message] = CommandArg()):
    gens[event.message.id] = PG(event)
    latest_message_id = event.message.id

    @waiter(waits=["message"], matcher=game_start, block=True, keep_session=True)
    async def check(event_: MessageEvent) -> MessageEvent:
        return event_

    arg_text = arg.extract_plain_text().strip()

    if arg_text in ["h", "-h", "--help", "help"]:
        await game_start.finish(
            HELP_MESSAGE + gens[latest_message_id].element,
            referrer=gens[latest_message_id].event.referrer,
        )

    try:
        bet_amount, latest_message_id = await get_bet_amount(
            arg_text, latest_message_id, check, game_start
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

        # Resolved once per game on the event-loop thread, then passed into
        # every table/hand render; the renderer never resolves identity.
        identity = identity_for(event.get_user_id())

        if await handle_initial_blackjack(
            session,
            bet_amount,
            latest_message_id,
            game_start,
            game_manager,
            identity=identity,
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
            identity=identity,
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
                identity=identity,
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
                identity=identity,
            )
    except MatcherException:
        raise
    except Exception as e:
        # 发生错误时退还下注金额
        game_manager.refund_half_game(event.get_user_id())
        code = handle_error(e, context="blackjack", user_id=event.get_user_id())
        await game_start.finish(
            "发生意外错误！已退回一半的下注Pt给你，再试一次吧？\n错误码：{}".format(
                code
            )
            + gens[latest_message_id].element,
            referrer=gens[latest_message_id].event.referrer,
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
                + gens[event.message.id].element,
                referrer=gens[event.message.id].event.referrer,
            )

        # 主题与身份都在事件循环线程解析，渲染函数只收现成数据
        kit = kit_for_user(user_id)
        identity = identity_for(user_id)
        image = await stats_page(stats_card_data(stats, identity), kit).render_async()

        await game_stats.finish(
            image_segment(image) + gens[event.message.id].element,
            referrer=gens[event.message.id].event.referrer,
        )

    except MatcherException:
        raise
    except Exception as e:
        code = handle_error(e, context="blackjack_stats", user_id=event.get_user_id())
        await game_stats.finish(
            "获取统计信息时出现错误，请稍后再试\n错误码：{}".format(code)
            + gens[event.message.id].element,
            referrer=gens[event.message.id].event.referrer,
        )
