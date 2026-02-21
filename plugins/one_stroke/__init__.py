from __future__ import annotations

import io
import time

from PIL import Image
from nonebot.log import logger
from nonebot.params import CommandArg
from nonebot import on_command, require
from nonebot.exception import MatcherException
from nonebot.adapters.satori import Message, MessageEvent, MessageSegment

require("nonebot_plugin_waiter")
from nonebot_plugin_waiter import waiter  # noqa: E402

from utils.passive_generator import generators as gens  # noqa: E402
from utils.passive_generator import PassiveGenerator as PG  # noqa: E402

from .. import monetary  # noqa: E402
from .messages import Messages  # noqa: E402
from .session import GameManager  # noqa: E402
from ..nickname import get as get_nickname  # noqa: E402
from .models import MoveResult, OneStrokeGame  # noqa: E402
from .render import render, render_leaderboard  # noqa: E402
from .difficulty import apply_time_decay, calculate_reward  # noqa: E402
from .graph_generator import generate_graph, parse_difficulty  # noqa: E402
from .database import get_leaderboard, get_session as get_db_session  # noqa: E402


game_manager = GameManager()


def _image_segment(img: Image.Image) -> MessageSegment:
    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    return MessageSegment.image(raw=buffer, mime="image/png")


def _render_image(session) -> MessageSegment:
    return _image_segment(render(session))


def _mask_user_id(user_id: str) -> str:
    if len(user_id) <= 6:
        return user_id
    return f"{user_id[:4]}..."


def _build_leaderboard_rows(difficulty: str) -> list[tuple[str, float]]:
    rows = get_leaderboard(difficulty=difficulty, limit=10)
    result: list[tuple[str, float]] = []
    for item in rows:
        nickname = get_nickname(item.user_id)
        display_name = nickname if nickname else _mask_user_id(item.user_id)
        result.append((display_name, item.elapsed_seconds))
    return result


def not_in_game(event: MessageEvent) -> bool:
    return not game_manager.is_in_game(event.get_user_id())


game_start = on_command(
    "一笔画",
    aliases={"onestroke", "yibihua", "os"},
    priority=10,
    block=True,
    rule=not_in_game,
)

leaderboard_cmd = on_command(
    "一笔画排行榜",
    aliases={"一笔画排行", "osr", "一笔画rank"},
    priority=10,
    block=True,
)


@leaderboard_cmd.handle()
async def handle_leaderboard(event: MessageEvent):
    passive_generator = PG(event)
    easy_rows = _build_leaderboard_rows("简单")
    normal_rows = _build_leaderboard_rows("普通")
    hard_rows = _build_leaderboard_rows("困难")
    image = render_leaderboard(easy_rows, normal_rows, hard_rows)
    await leaderboard_cmd.finish(_image_segment(image) + passive_generator.element)


@game_start.handle()
async def handle_start(event: MessageEvent, arg: Message = CommandArg()):
    gens[event.message.id] = PG(event)
    latest_message_id = event.message.id

    @waiter(waits=["message"], matcher=game_start, block=False, keep_session=True)
    async def check(event_: MessageEvent) -> MessageEvent:
        return event_

    difficulty_text = arg.extract_plain_text().strip()

    if difficulty_text.lower() in {"h", "--help", "help", "-h"}:
        await game_start.finish(Messages.HELP + gens[latest_message_id].element)

    config = parse_difficulty(difficulty_text)

    try:
        graph = generate_graph(config)
        reward = calculate_reward(graph)
        session = game_manager.create_session(
            event.get_user_id(),
            event.channel.id,
            config.label,
            reward,
            graph,
        )
        if session is None:
            await game_start.finish(
                "你已经在进行一笔画挑战了。" + gens[latest_message_id].element
            )

        await game_start.send(
            _render_image(session)
            + MessageSegment.text(
                Messages.START
                + "\n"
                + f"当前难度：{config.label}，预计奖励：{reward} 个碎片。"
                + "\n"
                + Messages.PROMPT
            )
            + gens[latest_message_id].element
        )
        session.restart_timer()

        while True:
            resp = await check.wait(timeout=300)
            if resp is None:
                game_manager.end_game(event.get_user_id())
                await game_start.finish(
                    Messages.TIMEOUT + gens[latest_message_id].element
                )

            latest_message_id = resp.message.id
            gens[latest_message_id] = PG(resp)
            msg = str(resp.get_message()).strip().upper()

            if msg == "Q":
                game_manager.end_game(event.get_user_id())
                await game_start.finish(
                    Messages.GIVE_UP + gens[latest_message_id].element
                )

            if msg == "R":
                session.reset()
                await game_start.send(
                    _render_image(session)
                    + MessageSegment.text(Messages.RESET + "\n" + Messages.PROMPT)
                    + gens[latest_message_id].element
                )
                continue

            if not msg or any(ch not in {"W", "A", "S", "D"} for ch in msg):
                await game_start.send(
                    Messages.INVALID_INPUT + gens[latest_message_id].element
                )
                continue

            fail_text = ""
            for idx, step in enumerate(msg, start=1):
                result = session.move(step)
                if result == MoveResult.SUCCESS:
                    continue
                if result == MoveResult.NO_EDGE:
                    fail_text = Messages.MOVE_FAIL_NO_EDGE.format(step=idx)
                elif result == MoveResult.ALREADY_DRAWN:
                    fail_text = Messages.MOVE_FAIL_REPEAT.format(step=idx)
                else:
                    fail_text = Messages.MOVE_FAIL_OOB.format(step=idx)
                break

            if session.is_complete:
                elapsed_seconds = session.elapsed_seconds()
                final_reward = apply_time_decay(
                    base_reward=session.reward,
                    elapsed_seconds=elapsed_seconds,
                    graph=session.graph,
                )
                db = get_db_session()
                db.add(
                    OneStrokeGame(
                        user_id=event.get_user_id(),
                        difficulty=session.difficulty_name,
                        elapsed_seconds=elapsed_seconds,
                        reward=final_reward,
                        base_reward=session.reward,
                        timestamp=int(time.time()),
                    )
                )
                db.commit()
                monetary.add(event.get_user_id(), final_reward, "one_stroke")
                balance = monetary.get(event.get_user_id())
                game_manager.end_game(event.get_user_id())
                await game_start.finish(
                    _render_image(session)
                    + MessageSegment.text(
                        Messages.WIN.format(
                            elapsed_seconds=round(elapsed_seconds, 2),
                            reward=final_reward,
                            balance=balance,
                        )
                    )
                    + gens[latest_message_id].element
                )

            status_text = (
                Messages.PROGRESS.format(
                    drawn=session.drawn_count, total=session.total_edges
                )
                + "\n"
                + Messages.PROMPT
            )
            if fail_text:
                status_text = fail_text + "\n" + status_text

            await game_start.send(
                _render_image(session)
                + MessageSegment.text(status_text)
                + gens[latest_message_id].element
            )

    except MatcherException:
        raise
    except Exception as e:
        logger.error(f"一笔画插件发生错误: {e}", exc_info=True)
        game_manager.end_game(event.get_user_id())
        await game_start.finish(Messages.ERROR + gens[latest_message_id].element)
