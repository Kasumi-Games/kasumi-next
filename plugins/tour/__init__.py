"""巡演小游戏。

The domain state lives in :mod:`plugins.tour.session`; this module only wires
that state to NoneBot, the economy and the themed image surfaces.
"""

from __future__ import annotations

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

from utils import get_today_birthday
from utils.avatar import get_avatar
from utils.images import image_segment_async
from utils.images import render_image_segment
from utils.theming import kit_for_user
from utils.identity import identity_for
from utils.waiter_rules import same_channel
from utils.waiter_rules import is_force_stop_message
from utils.error_handler import handle_error
from utils.passive_generator import PassiveGenerator as PG
from utils.passive_generator import generators as gens

require("nonebot_plugin_waiter")
require("daily_task")

from nonebot_plugin_waiter import waiter  # noqa: E402

from .. import monetary  # noqa: E402
from .rules import difficulty_help  # noqa: E402
from .rules import difficulty_for_command  # noqa: E402
from .rules import parse_display_mode_request  # noqa: E402
from .models import TourOutcome  # noqa: E402
from .models import TourDisplayMode  # noqa: E402
from .render import render_help  # noqa: E402
from .render import render_state  # noqa: E402
from .render import render_result  # noqa: E402
from .render import render_leaderboard  # noqa: E402
from .service import record_result  # noqa: E402
from .service import get_leaderboard  # noqa: E402
from .service import get_display_mode  # noqa: E402
from .service import set_display_mode  # noqa: E402
from .session import TourSession  # noqa: E402
from .session import TourGameManager  # noqa: E402
from .database import init_database  # noqa: E402
from .messages import Messages  # noqa: E402
from ..nickname import get as get_nickname  # noqa: E402
from ..daily_task import check_progress  # noqa: E402
from ..daily_task import get_today_task  # noqa: E402
from .render.state import TourRenderData  # noqa: E402
from .render.result import TourResultData  # noqa: E402
from ..monetary.level_service import LEVEL_UP_STICKERS  # noqa: E402
from ..inventory.season_service import get_current_season_bounds  # noqa: E402

game_manager = TourGameManager()


def not_in_game(event: MessageEvent) -> bool:
    return not game_manager.is_in_game(event.get_user_id())


tour_start = on_command(
    "巡演",
    aliases={
        "tour",
        "xy",
        "初级巡演",
        "中级巡演",
        "高级巡演",
        "超级巡演",
        "xyez",
        "xynm",
        "xyhd",
        "xyex",
    },
    priority=10,
    block=True,
    rule=not_in_game,
)

leaderboard_cmd = on_command(
    "巡演排行榜",
    aliases={"巡演排行", "xyr", "tourrank"},
    priority=10,
    block=True,
)


@get_driver().on_startup
async def init_tour() -> None:
    init_database()


def _plain(event: MessageEvent) -> PG:
    current = PG(event)
    gens[event.message.id] = current
    return current


def _text(resp: MessageEvent) -> str:
    return str(resp.get_message()).strip()


def _force_stop(text: str) -> bool:
    return is_force_stop_message(
        text,
        {
            "巡演",
            "tour",
            "xy",
            "初级巡演",
            "中级巡演",
            "高级巡演",
            "超级巡演",
            "xyez",
            "xynm",
            "xyhd",
            "xyex",
        },
    )


def _mode_label(mode: TourDisplayMode) -> str:
    return "图片" if mode is TourDisplayMode.IMAGE else "文本"


def _mode_status_text(mode: TourDisplayMode) -> str:
    return (
        f"当前巡演显示模式：{_mode_label(mode)}。\n"
        "使用「巡演 模式 图片」或「巡演 模式 文本」切换。"
    )


def _mode_confirmation_text(mode: TourDisplayMode) -> str:
    detail = (
        "之后的巡演局面和结算将使用图片发送。"
        if mode is TourDisplayMode.IMAGE
        else "之后的巡演局面和结算将直接使用文本发送。"
    )
    return f"已切换为巡演{_mode_label(mode)}模式。{detail}"


def _mask_user_id(user_id: str) -> str:
    if len(user_id) <= 6:
        return user_id
    return f"{user_id[:4]}..."


def _leaderboard_rows(
    difficulty: str,
    season_bounds: tuple[int, int],
) -> list[tuple[str, float]]:
    records = get_leaderboard(
        difficulty,
        limit=10,
        start_time=season_bounds[0],
        end_time=season_bounds[1],
    )
    return [
        (
            get_nickname(record.user_id) or _mask_user_id(record.user_id),
            record.elapsed_seconds,
        )
        for record in records
    ]


@leaderboard_cmd.handle()
async def handle_leaderboard(event: MessageEvent) -> None:
    pg = _plain(event)
    season_bounds = get_current_season_bounds()
    if season_bounds is None:
        await leaderboard_cmd.finish(
            "当前赛季尚未开启，巡演赛季排行榜会在开季后开始统计。"
            + pg.element,
            referrer=pg.event.referrer,
        )
        return
    rows_by_difficulty = {
        difficulty: _leaderboard_rows(difficulty, season_bounds)
        for difficulty in ("初级", "中级", "高级", "超级")
    }
    image = await render_image_segment(
        render_leaderboard,
        rows_by_difficulty,
        kit=kit_for_user(event.get_user_id()),
    )
    await leaderboard_cmd.finish(
        image + pg.element,
        referrer=pg.event.referrer,
    )


def _state_data(session: TourSession) -> TourRenderData:
    return TourRenderData(snapshot=session.snapshot())


def _status_text(session: TourSession, result=None) -> str:
    lines: list[str] = []
    if result is not None:
        for action in result.performed:
            if action.kind == "tour":
                lines.append(
                    f"巡演{action.card_name}（消耗体力{action.amount}）"
                )
            elif action.kind == "instrument":
                lines.append(f"已装备{action.card_name}。")
            elif action.kind == "food":
                if action.amount:
                    lines.append(f"品尝了{action.card_name}，体力+{action.amount}")
                else:
                    lines.append(f"{action.card_name}（今天已经吃过了，未恢复体力）")
            elif action.kind == "instrument_toggle":
                lines.append(action.card_name)
            elif action.kind == "rest":
                lines.append("休息了一天，日程已排至最后。")

    if result is not None and result.invalid_reason:
        lines.append(
            Messages.invalid_reason(
                result.invalid_reason,
                result.invalid_step,
                can_discard=not session.config.allow_unequip,
            )
        )
    if result is not None and result.ignored_suffix:
        if result.invalid_reason:
            lines.append(f"未执行后缀：{result.ignored_suffix}")
        else:
            lines.append(
                f"第 {result.invalid_step} 步后本日行动已满，"
                f"未执行后缀：{result.ignored_suffix}"
            )
    return "\n".join(lines)


async def _send_state(
    matcher,
    session: TourSession,
    *,
    pg: PG,
    notice: str = "",
    kit=None,
    identity=None,
    referrer=None,
    display_mode: TourDisplayMode = TourDisplayMode.IMAGE,
) -> None:
    snapshot = session.snapshot()
    if display_mode is TourDisplayMode.TEXT:
        await matcher.send(
            (notice + "\n" if notice else "")
            + Messages.status_text(snapshot)
            + "\n"
            + Messages.prompt(snapshot)
            + pg.element,
            referrer=referrer,
        )
        return

    kit = kit or kit_for_user(session.user_id)
    identity = identity or identity_for(session.user_id)
    detail = (
        f"{session.difficulty} · 第 {session.day} 天 · "
        f"{session.tour_played_count}/26"
    )
    try:
        image = await render_image_segment(
            render_state,
            _state_data(session),
            kit=kit,
            identity=identity,
            detail=detail,
        )
        await matcher.send(
            image
            + MessageSegment.text(
                (notice + "\n" if notice else "") + Messages.prompt(snapshot)
            )
            + pg.element,
            referrer=referrer,
        )
    except Exception:
        logger.opt(exception=True).warning("tour state render failed")
        await matcher.send(
            (notice + "\n" if notice else "")
            + Messages.status_text(snapshot)
            + "\n"
            + Messages.prompt(snapshot)
            + pg.element,
            referrer=referrer,
        )


async def _send_help(matcher, event: MessageEvent, pg: PG) -> None:
    try:
        image = await image_segment_async(render_help(kit_for_user(event.get_user_id())))
    except Exception:
        await matcher.finish(Messages.HELP + pg.element, referrer=pg.event.referrer)
        return
    await matcher.finish(image + pg.element, referrer=pg.event.referrer)


async def _settle(
    session: TourSession,
    outcome: TourOutcome,
) -> TourResultData:
    if session.settlement_done:
        return TourResultData(
            snapshot=session.snapshot(),
            outcome=outcome,
            reward_pt=session.settlement_reward_pt,
            balance=monetary.get(session.user_id),
            elapsed_seconds=session.elapsed_seconds(),
            base_reward_pt=session.settlement_base_reward_pt,
            birthday_names=session.settlement_birthday_names,
            multiplier=session.settlement_multiplier,
        )

    base_reward = (
        session.config.reward_pt
        if outcome is TourOutcome.WIN
        else session.tour_played_count
        if outcome in {TourOutcome.STAMINA, TourOutcome.TIMEOUT}
        else 0
    )
    birthday_names = tuple(get_today_birthday()) if outcome.value == "win" else ()
    multiplier = 2 if birthday_names else 1
    reward = base_reward * multiplier
    record_result(session, outcome, reward)
    session.settlement_base_reward_pt = base_reward
    session.settlement_reward_pt = reward
    session.settlement_birthday_names = birthday_names
    session.settlement_multiplier = multiplier
    session.settlement_done = True

    task_name: str | None = None
    task_reward = 0
    old_level = monetary.get_level(session.user_id)
    new_level = old_level
    if reward:
        monetary.add(
            session.user_id,
            reward,
            "tour",
            idempotency_key=f"tour:{session.run_id}:pt",
        )
    if outcome is TourOutcome.WIN:
        try:
            await monetary.add_xp(session.user_id, reward)
            new_level = monetary.get_level(session.user_id)
        except Exception:
            logger.opt(exception=True).warning("巡演经验结算失败")
    try:
        task_msg = await check_progress(
            session.user_id,
            "tour_progress",
            {
                "tours_completed": session.tour_played_count,
                "day": session.day,
            },
        )
        if task_msg:
            try:
                task_config = get_today_task(session.user_id)
                task_name = task_config.name
                task_reward = task_config.reward
            except Exception:
                task_name = "每日任务"
    except Exception:
        logger.opt(exception=True).warning("巡演每日任务结算失败")

    result_data = TourResultData(
        snapshot=session.snapshot(),
        outcome=outcome,
        reward_pt=reward,
        balance=monetary.get(session.user_id),
        elapsed_seconds=session.elapsed_seconds(),
        base_reward_pt=base_reward,
        birthday_names=birthday_names,
        multiplier=multiplier,
        task_name=task_name,
        task_reward=task_reward,
        old_level=old_level if new_level > old_level else None,
        new_level=new_level if new_level > old_level else None,
        level_stickers=(new_level - old_level) * LEVEL_UP_STICKERS
        if new_level > old_level
        else 0,
    )
    return result_data


async def _finish_result(
    session: TourSession,
    outcome: TourOutcome,
    *,
    pg: PG,
    display_mode: TourDisplayMode,
    kit=None,
    identity=None,
) -> None:
    result_data = await _settle(session, outcome)
    if display_mode is TourDisplayMode.TEXT:
        await tour_start.finish(
            Messages.result_text(result_data) + pg.element,
            referrer=pg.event.referrer,
        )
        return
    try:
        image = await image_segment_async(
            render_result(
                result_data,
                kit=kit,
                identity=identity,
            )
        )
    except Exception:
        logger.opt(exception=True).warning("tour result render failed")
        await tour_start.finish(
            Messages.result_text(result_data) + pg.element,
            referrer=pg.event.referrer,
        )
        return
    await tour_start.finish(
        image + pg.element,
        referrer=pg.event.referrer,
    )


@tour_start.handle()
async def handle_start(
    event: MessageEvent,
    arg: Optional[Message] = CommandArg(),
) -> None:
    pg = _plain(event)
    raw_arg = arg.extract_plain_text().strip() if arg else ""
    command_text = str(event.get_message()).strip()

    if raw_arg.casefold() in {"h", "-h", "--help", "help"}:
        await _send_help(tour_start, event, pg)
        return

    mode_request = parse_display_mode_request(raw_arg)
    if mode_request.kind != "none":
        if mode_request.kind == "invalid":
            await tour_start.finish(
                "用法：巡演 模式 <图片|文本>。" + pg.element,
                referrer=pg.event.referrer,
            )
            return
        if mode_request.kind == "query":
            current_mode = get_display_mode(event.get_user_id())
            await tour_start.finish(
                _mode_status_text(current_mode) + pg.element,
                referrer=pg.event.referrer,
            )
            return
        mode = set_display_mode(event.get_user_id(), mode_request.mode)
        await tour_start.finish(
            _mode_confirmation_text(mode) + pg.element,
            referrer=pg.event.referrer,
        )
        return

    if _force_stop(command_text):
        await tour_start.finish(
            "当前没有进行中的巡演。" + pg.element,
            referrer=pg.event.referrer,
        )
        return

    difficulty = difficulty_for_command(command_text, raw_arg)
    if difficulty is None:
        await tour_start.finish(
            difficulty_help() + pg.element,
            referrer=pg.event.referrer,
        )
        return

    session = game_manager.start(event.get_user_id(), difficulty)
    if session is None:
        await tour_start.finish(
            Messages.ALREADY_IN_GAME + pg.element,
            referrer=pg.event.referrer,
        )

    @waiter(
        waits=["message"],
        matcher=tour_start,
        block=False,
        keep_session=True,
        rule=same_channel(event.channel.id),
    )
    async def check(event_: MessageEvent) -> MessageEvent:
        return event_

    display_mode = get_display_mode(event.get_user_id())
    kit = None
    identity = None
    try:
        if display_mode is TourDisplayMode.IMAGE:
            kit = kit_for_user(event.get_user_id())
            avatar = await get_avatar(event.get_user_id())
            identity = identity_for(event.get_user_id(), avatar=avatar)
        await _send_state(
            tour_start,
            session,
            pg=pg,
            notice=Messages.START,
            kit=kit,
            identity=identity,
            referrer=pg.event.referrer,
            display_mode=display_mode,
        )

        while True:
            resp = await check.wait(timeout=600)
            if resp is None:
                session.mark_terminal("timeout")
                game_manager.end(session.user_id)
                await _finish_result(
                    session,
                    TourOutcome.TIMEOUT,
                    pg=pg,
                    display_mode=display_mode,
                    kit=kit,
                    identity=identity,
                )

            pg = _plain(resp)
            text = _text(resp)
            mode_request = parse_display_mode_request(text)
            if mode_request.kind != "none":
                if mode_request.kind == "invalid":
                    await tour_start.send(
                        "用法：巡演 模式 <图片|文本>。" + pg.element,
                        referrer=pg.event.referrer,
                    )
                    continue
                if mode_request.kind == "query":
                    await tour_start.send(
                        _mode_status_text(display_mode) + pg.element,
                        referrer=pg.event.referrer,
                    )
                    continue

                display_mode = set_display_mode(
                    session.user_id,
                    mode_request.mode,
                )
                if display_mode is TourDisplayMode.IMAGE and kit is None:
                    kit = kit_for_user(session.user_id)
                    avatar = await get_avatar(session.user_id)
                    identity = identity_for(session.user_id, avatar=avatar)
                await _send_state(
                    tour_start,
                    session,
                    pg=pg,
                    notice=_mode_confirmation_text(display_mode),
                    kit=kit,
                    identity=identity,
                    referrer=pg.event.referrer,
                    display_mode=display_mode,
                )
                continue

            if _force_stop(text):
                session.mark_terminal("quit")
                game_manager.end(session.user_id)
                record_result(session, session.outcome, 0)
                await tour_start.finish(
                    Messages.GIVE_UP + pg.element,
                    referrer=pg.event.referrer,
                )

            if text.casefold() in {"q", "quit"}:
                session.mark_terminal("quit")
                game_manager.end(session.user_id)
                record_result(session, session.outcome, 0)
                await tour_start.finish(
                    Messages.GIVE_UP + pg.element,
                    referrer=pg.event.referrer,
                )

            result = session.apply(text)
            if result.terminal:
                outcome = result.outcome
                assert outcome is not None
                game_manager.end(session.user_id)
                await _finish_result(
                    session,
                    outcome,
                    pg=pg,
                    display_mode=display_mode,
                    kit=kit,
                    identity=identity,
                )

            task_notice = ""
            if result.changed:
                try:
                    task_notice = await check_progress(
                        session.user_id,
                        "tour_progress",
                        {
                            "tours_completed": session.tour_played_count,
                            "day": session.day,
                        },
                    ) or ""
                except Exception:
                    logger.opt(exception=True).warning("巡演每日任务进度检查失败")

            notice = _status_text(session, result)
            if task_notice:
                notice = "\n".join(part for part in (notice, task_notice) if part)
            if not result.changed:
                await tour_start.send(
                    (notice or Messages.INVALID_INPUT) + pg.element,
                    referrer=pg.event.referrer,
                )
                continue
            await _send_state(
                tour_start,
                session,
                pg=pg,
                notice=notice,
                kit=kit,
                identity=identity,
                referrer=pg.event.referrer,
                display_mode=display_mode,
            )
    except MatcherException:
        game_manager.end(session.user_id)
        raise
    except Exception as exc:
        game_manager.end(session.user_id)
        code = handle_error(exc, context="tour", user_id=session.user_id)
        await tour_start.finish(
            f"错误码：{code}\n{Messages.ERROR}" + pg.element,
            referrer=pg.event.referrer,
        )


__all__ = ["game_manager", "tour_start"]
