import time

from nonebot import require
from nonebot import on_command
from nonebot.params import CommandArg
from nonebot.exception import MatcherException
from nonebot.adapters.satori import Message
from nonebot.adapters.satori import MessageEvent
from nonebot.adapters.satori import MessageSegment

from utils.avatar import get_avatar
from utils.images import image_segment_async
from utils.images import render_image_segment
from utils.theming import kit_for_user
from utils.identity import identity_for
from utils.error_handler import handle_error

require("nonebot_plugin_waiter")
require("daily_task")
from nonebot_plugin_waiter import waiter  # noqa: E402

from utils import get_today_birthday  # noqa: E402
from utils.passive_generator import PassiveGenerator as PG  # noqa: E402
from utils.passive_generator import generators as gens  # noqa: E402

from .. import monetary  # noqa: E402
from .models import MoveResult  # noqa: E402
from .models import OneStrokeGame  # noqa: E402
from .render import OneStrokeResultData  # noqa: E402
from .render import render  # noqa: E402
from .render import result_page  # noqa: E402
from .render import render_leaderboard  # noqa: E402
from .session import GameManager  # noqa: E402
from .database import get_session as get_db_session  # noqa: E402
from .database import get_leaderboard  # noqa: E402
from .database import get_personal_best  # noqa: E402
from .messages import Messages  # noqa: E402
from ..nickname import get as get_nickname  # noqa: E402
from .difficulty import apply_time_decay  # noqa: E402
from .difficulty import calculate_reward  # noqa: E402
from .difficulty import time_decay_factor  # noqa: E402
from ..daily_task import check_progress  # noqa: E402
from ..daily_task import get_today_task  # noqa: E402
from .graph_generator import generate_graph  # noqa: E402
from .graph_generator import parse_difficulty  # noqa: E402
from ..monetary.level_service import LEVEL_UP_STICKERS  # noqa: E402
from ..inventory.season_service import get_current_season_bounds  # noqa: E402

game_manager = GameManager()


async def _render_image(
    session, kit=None, identity=None, detail=None
) -> MessageSegment:
    return await render_image_segment(
        render, session, kit=kit, identity=identity, detail=detail
    )


def _mask_user_id(user_id: str) -> str:
    if len(user_id) <= 6:
        return user_id
    return f"{user_id[:4]}..."


def _build_leaderboard_rows(
    difficulty: str, season_bounds: tuple[int, int]
) -> list[tuple[str, float]]:
    rows = get_leaderboard(
        difficulty=difficulty,
        limit=10,
        start_time=season_bounds[0],
        end_time=season_bounds[1],
    )
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
    season_bounds = get_current_season_bounds()
    if season_bounds is None:
        await leaderboard_cmd.finish(
            "当前赛季尚未开启，一笔画赛季排行榜会在开季后开始统计。"
            + passive_generator.element,
            referrer=passive_generator.event.referrer,
        )
        return
    easy_rows = _build_leaderboard_rows("简单", season_bounds)
    normal_rows = _build_leaderboard_rows("普通", season_bounds)
    hard_rows = _build_leaderboard_rows("困难", season_bounds)
    image = await render_image_segment(
        render_leaderboard, easy_rows, normal_rows, hard_rows
    )
    await leaderboard_cmd.finish(
        image + passive_generator.element,
        referrer=passive_generator.event.referrer,
    )


@game_start.handle()
async def handle_start(event: MessageEvent, arg: Message = CommandArg()):
    current_pg = PG(event)
    gens[event.message.id] = current_pg

    @waiter(waits=["message"], matcher=game_start, block=False, keep_session=True)
    async def check(event_: MessageEvent) -> MessageEvent:
        return event_

    difficulty_text = arg.extract_plain_text().strip()

    if difficulty_text.lower() in {"h", "--help", "help", "-h"}:
        await game_start.finish(
            Messages.HELP + current_pg.element,
            referrer=current_pg.event.referrer,
        )

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
                "你已经在进行一笔画挑战了。" + current_pg.element,
                referrer=current_pg.event.referrer,
            )

        # Resolved once per game on the event-loop thread, then passed into
        # every render below; renderers never resolve theme or identity. The
        # avatar is fetched once here — the cache makes per-move renders cheap
        # — and None keeps the initial-badge fallback.
        kit = kit_for_user(event.get_user_id())
        avatar = await get_avatar(event.get_user_id())
        identity = identity_for(event.get_user_id(), avatar=avatar)
        detail = f"难度 {config.label} · 奖励 {reward} Pt"

        await game_start.send(
            await _render_image(session, kit=kit, identity=identity, detail=detail)
            + MessageSegment.text(
                Messages.START
                + "\n"
                + f"当前难度：{config.label}，预计奖励：{reward} 个Pt。"
                + "\n"
                + Messages.PROMPT
            )
            + current_pg.element,
            referrer=current_pg.event.referrer,
        )
        session.restart_timer()

        while True:
            resp = await check.wait(timeout=300)
            if resp is None:
                game_manager.end_game(event.get_user_id())
                await game_start.finish(
                    Messages.TIMEOUT + current_pg.element,
                    referrer=current_pg.event.referrer,
                )

            current_pg = PG(resp)
            gens[resp.message.id] = current_pg
            msg = str(resp.get_message()).strip().upper()

            if msg == "Q":
                game_manager.end_game(event.get_user_id())
                await game_start.finish(
                    Messages.GIVE_UP + current_pg.element,
                    referrer=current_pg.event.referrer,
                )

            if msg == "R":
                session.reset()
                await game_start.send(
                    await _render_image(
                        session, kit=kit, identity=identity, detail=detail
                    )
                    + MessageSegment.text(Messages.RESET + "\n" + Messages.PROMPT)
                    + current_pg.element,
                    referrer=current_pg.event.referrer,
                )
                continue

            if not msg or any(ch not in {"W", "A", "S", "D"} for ch in msg):
                await game_start.send(
                    Messages.INVALID_INPUT + current_pg.element,
                    referrer=current_pg.event.referrer,
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
                decay_factor = time_decay_factor(elapsed_seconds, session.graph)
                birthday_characters = get_today_birthday()
                if birthday_characters:
                    final_reward *= 2

                # Personal best BEFORE this round is recorded, so the run is
                # compared against history (read-only; ambition review #8).
                season_bounds = get_current_season_bounds()
                previous_best = get_personal_best(
                    event.get_user_id(),
                    session.difficulty_name,
                    **(
                        {
                            "start_time": season_bounds[0],
                            "end_time": season_bounds[1],
                        }
                        if season_bounds is not None
                        else {}
                    ),
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

                # The completed board first — the finished figure is the
                # trophy; the result card that follows carries the outcome.
                await game_start.send(
                    await _render_image(
                        session, kit=kit, identity=identity, detail=detail
                    )
                    + current_pg.element,
                    referrer=current_pg.event.referrer,
                )

                # Daily task: its completion text becomes card rows, so keep
                # only the structured name/reward of the task just completed.
                task_name: str | None = None
                task_reward = 0
                task_msg = await check_progress(
                    event.get_user_id(),
                    "one_stroke_time",
                    {"difficulty": session.difficulty_name, "time": elapsed_seconds},
                )
                if task_msg:
                    try:
                        task_config = get_today_task(event.get_user_id())
                        task_name = task_config.name
                        task_reward = task_config.reward
                    except Exception:
                        task_name = "每日任务"

                # Level-up: read the level around add_xp so the card gets
                # numbers rather than the service's preformatted text.
                old_level = monetary.get_level(event.get_user_id())
                level_msg = await monetary.add_xp(event.get_user_id(), final_reward)
                new_level = (
                    monetary.get_level(event.get_user_id())
                    if level_msg
                    else old_level
                )
                leveled = new_level > old_level

                result_data = OneStrokeResultData(
                    difficulty=session.difficulty_name,
                    elapsed_seconds=elapsed_seconds,
                    base_reward=session.reward,
                    decay_factor=decay_factor,
                    final_reward=final_reward,
                    balance=balance,
                    birthday_characters=tuple(birthday_characters),
                    previous_best_seconds=previous_best,
                    is_new_record=previous_best is None
                    or elapsed_seconds < previous_best,
                    task_name=task_name,
                    task_reward=task_reward,
                    old_level=old_level if leveled else None,
                    new_level=new_level if leveled else None,
                    level_stickers=(new_level - old_level) * LEVEL_UP_STICKERS
                    if leveled
                    else 0,
                )
                # Re-resolve the identity so a level-up this round already
                # shows on the card's strip; the avatar fetched at game start
                # is reused.
                result_image = await result_page(
                    result_data,
                    kit=kit,
                    identity=identity_for(event.get_user_id(), avatar=avatar),
                ).render_async()
                await game_start.send(
                    await image_segment_async(result_image)
                    + current_pg.element,
                    referrer=current_pg.event.referrer,
                )

                await game_start.finish(referrer=event.referrer)

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
                await _render_image(
                    session, kit=kit, identity=identity, detail=detail
                )
                + MessageSegment.text(status_text)
                + current_pg.element,
                referrer=current_pg.event.referrer,
            )

    except MatcherException:
        raise
    except Exception as e:
        game_manager.end_game(event.get_user_id())
        code = handle_error(e, context="one_stroke", user_id=event.get_user_id())
        await game_start.finish(
            MessageSegment.text("错误码：{}\n".format(code))
            + Messages.ERROR
            + current_pg.element,
            referrer=current_pg.event.referrer,
        )
