import io
import random
from typing import List
from typing import Optional
from pathlib import Path

from PIL import Image
from nonebot import require
from nonebot import get_driver
from nonebot import on_command
from nonebot import get_plugin_config
from bestdori import songs
from bestdori import settings
from nonebot.log import logger
from nonebot.params import Depends
from nonebot.params import CommandArg
from bestdori.charts import Chart

# The alias is load-bearing: importing the local ``.render`` package below
# binds a MODULE named ``render`` onto this package's namespace (this file's
# globals), which would silently overwrite a plain ``render`` function and
# crash the handler with "'module' object is not callable".
from bestdori.render import render as render_chart
from nonebot.adapters.satori import Message
from nonebot.adapters.satori import MessageEvent
from nonebot.adapters.satori import MessageSegment

from utils.error_handler import handle_error

require("daily_task")
require("nonebot_plugin_waiter")
require("nonebot_plugin_apscheduler")

from nonebot_plugin_waiter import waiter  # noqa: E402
from nonebot_plugin_apscheduler import scheduler  # noqa: E402

from utils import get_today_birthday  # noqa: E402
from utils.avatar import get_avatar  # noqa: E402
from utils.images import image_segment_async  # noqa: E402
from utils.theming import kit_for_user  # noqa: E402
from utils.identity import identity_for  # noqa: E402
from utils.image_tasks import run_image_task  # noqa: E402
from utils.waiter_rules import same_channel  # noqa: E402
from utils.waiter_rules import is_force_stop_message  # noqa: E402
from utils.passive_generator import PassiveGenerator as PG  # noqa: E402
from utils.passive_generator import generators as gens  # noqa: E402

from .. import monetary  # noqa: E402
from .store import BandStore  # noqa: E402
from .store import SongStore  # noqa: E402
from .store import GamersStore  # noqa: E402
from .utils import diff_num  # noqa: E402
from .utils import fuzzy_match  # noqa: E402
from .utils import get_difficulty  # noqa: E402
from .utils import get_jacket_image  # noqa: E402
from .utils import read_csv_to_dict  # noqa: E402
from .utils import render_to_slices  # noqa: E402
from .utils import flatten_song_data  # noqa: E402
from .utils import sort_by_difficulty  # noqa: E402
from .utils import get_value_from_list  # noqa: E402
from .utils import build_enriched_dictionary  # noqa: E402
from .config import Config  # noqa: E402
from .render import LevelGain  # noqa: E402
from .render import TaskCompletion  # noqa: E402
from .render import GuessChartRevealData  # noqa: E402
from .render import reveal_page  # noqa: E402
from ..daily_task import check_progress  # noqa: E402
from ..daily_task import get_today_task  # noqa: E402
from ..monetary.level_service import LEVEL_UP_STICKERS  # noqa: E402

plugin_config = get_plugin_config(Config)
settings.proxy = plugin_config.bestdori_proxy

nickname_song = read_csv_to_dict(Path(__file__).parent / "nickname_song.csv")


song_store = SongStore()
band_store = BandStore()
gamers_store = GamersStore()

_FORCE_STOP_COMMANDS = {"猜谱面", "猜谱", "cpm", "谱面挑战"}


def _stop_if_force_stop(message: str, channel_id: str) -> bool:
    """Consume a force-stop command and clear the channel's active game."""

    if not is_force_stop_message(message, _FORCE_STOP_COMMANDS):
        return False
    gamers_store.remove(channel_id)
    return True


async def is_gaming(event: MessageEvent) -> bool:
    return event.channel.id in gamers_store.get()


game_start = on_command(
    "猜谱面",
    aliases={"猜谱", "cpm", "谱面挑战"},
    priority=10,
    block=True,
    rule=lambda: plugin_config.enable_guess_chart,
)


def _completed_task(user_id: str) -> Optional[TaskCompletion]:
    """Structured info for the task ``check_progress`` just completed.

    ``check_progress`` only returns a preformatted string, so the name and
    reward come from today's task config instead of being parsed back out.
    """

    try:
        config = get_today_task(user_id)
        return TaskCompletion(name=config.name, reward=config.reward)
    except Exception:
        logger.opt(exception=True).warning("daily task config unavailable for reveal")
        return None


def _level_gain(old_level: int, new_level: int) -> Optional[LevelGain]:
    if new_level <= old_level:
        return None
    return LevelGain(
        old_level=old_level,
        new_level=new_level,
        stickers=(new_level - old_level) * LEVEL_UP_STICKERS,
    )


def _decode_jacket(jacket_image: bytes) -> Optional[Image.Image]:
    """Decode the fetched jacket bytes; the card tolerates ``None``."""

    try:
        jacket = Image.open(io.BytesIO(jacket_image))
        jacket.load()
        return jacket
    except Exception:
        logger.opt(exception=True).warning("jacket image decode failed")
        return None


async def _send_reveal_card(
    data: GuessChartRevealData,
    kit,
    pg: PG,
    fallback_text: str,
    jacket_image: bytes,
) -> None:
    """Render and send the round-exit card as one message.

    On a render failure the round must still resolve, so this falls back to
    the pre-card shape: the answer as text plus the raw jacket image.
    """

    try:
        image = await reveal_page(data, kit).render_async()
    except Exception:
        logger.opt(exception=True).warning(
            "guess_chart reveal render failed; sending text"
        )
        await game_start.send(
            fallback_text + pg.element, referrer=pg.event.referrer
        )
        await game_start.send(
            MessageSegment.image(raw=jacket_image, mime="image/png") + pg.element,
            referrer=pg.event.referrer,
        )
        return
    await game_start.send(
        await image_segment_async(image) + pg.element, referrer=pg.event.referrer
    )


if plugin_config.enable_guess_chart:

    @get_driver().on_startup
    @scheduler.scheduled_job("cron", hour=0, minute=0)
    async def refresh_data():
        await song_store.update()
        await band_store.update()


@game_start.handle()
async def handle_start(
    event: MessageEvent,
    arg: Optional[Message] = CommandArg(),
    song_data: dict = Depends(song_store.get),
    band_data: dict = Depends(band_store.get),
    game_difficulty: str = Depends(get_difficulty),
    song_raw_data: dict = Depends(song_store.get_raw),
):
    current_pg = PG(event)
    gens[event.message.id] = current_pg

    if (
        arg is not None
        and arg.extract_plain_text().strip() == "-f"
        and await is_gaming(event)
    ):
        gamers_store.remove(event.channel.id)
        await game_start.finish(
            "已强制退出猜谱面" + current_pg.element,
            referrer=current_pg.event.referrer,
        )

    if arg is not None and arg.extract_plain_text().strip() == "-f":
        await game_start.finish(
            "没有正在进行的猜谱面" + current_pg.element,
            referrer=current_pg.event.referrer,
        )

    if await is_gaming(event):
        await game_start.finish(
            "已经在猜谱面了哦，如果有异常，请使用 @Kasumi /猜谱面 -f 以强制结束游戏"
            + current_pg.element,
            referrer=current_pg.event.referrer,
        )

    session_token = gamers_store.add(event.channel.id)

    await game_start.send(
        "正在加载谱面..." + current_pg.element,
        referrer=current_pg.event.referrer,
    )

    flat_song_data: list = flatten_song_data(song_data)
    sorted_song_data = sort_by_difficulty(flat_song_data)

    potential_song_number = 0
    max_song_num = max([len(v) for v in sorted_song_data.values()])  # about 271
    max_amount = 12

    if arg.extract_plain_text().strip().isdigit():
        # 指定特定难度的谱面
        game_type = "given_play_level"
        song_difficulty = int(arg.extract_plain_text().strip())
        filtered_song_data = [
            song for song in flat_song_data if song["play_level"] == song_difficulty
        ]
        if (song_num := len(filtered_song_data)) <= 3:
            gamers_store.remove(event.channel.id)
            await game_start.finish(
                f"{song_difficulty} 的曲子一共只有 {song_num} 首，太简单了哦！试试换个等级吧"
                + current_pg.element,
                referrer=current_pg.event.referrer,
            )
        potential_song_number = song_num
    elif game_difficulty == "easy":
        # 在 28 级及以上的歌曲中抽取
        game_type = "given_game_difficulty"
        filtered_song_data = [
            song for song in flat_song_data if song["play_level"] >= 28
        ]
        potential_song_number = len(filtered_song_data)
    elif game_difficulty == "normal":
        # 在 27 级及以上的歌曲中抽取
        game_type = "given_game_difficulty"
        filtered_song_data = [
            song for song in flat_song_data if song["play_level"] >= 27
        ]
        potential_song_number = len(filtered_song_data)
    else:
        game_type = "given_game_difficulty"
        filtered_song_data = flat_song_data
        potential_song_number = len(filtered_song_data)

    if not filtered_song_data:
        gamers_store.remove(event.channel.id)
        await game_start.finish(
            "没有符合条件的谱面" + current_pg.element,
            referrer=current_pg.event.referrer,
        )

    song = random.choice(filtered_song_data)

    song_id = int(song["song_id"])

    try:
        song_detail = songs.Song(song_id)

        chart_difficulty = song["difficulty"]
        chart = await Chart.get_chart_async(song_id, chart_difficulty)
        chart_statistics = chart.count()

        if game_difficulty in ["easy", "normal"]:
            img = await run_image_task(lambda: render_chart(chart))
        else:
            img = await run_image_task(render_to_slices, chart, game_difficulty)

        diff: str = chart_difficulty
        song_info = await song_detail.get_info_async()
        level = (
            song_info.get("difficulty", {})
            .get(diff_num[diff], {})
            .get("playLevel")
        )
        song_name = song["song_name"]

        # The note count no longer needs to stay hidden: the reveal card shows it
        # once the round is over (the chart image itself remains the only in-round
        # source).
        note_num = int(chart_statistics.notes)

        band_id: int = song_info["bandId"]
        band_name = get_value_from_list(band_data[str(band_id)]["bandName"])

        jacket_image = await get_jacket_image(int(song_id), song_info)
        jacket_pil = await run_image_task(_decode_jacket, jacket_image)
        main_bpm = int(chart_statistics.main_bpm)
    except Exception as e:
        gamers_store.remove(event.channel.id)
        code = handle_error(e, context="guess_chart", user_id=event.get_user_id())
        await game_start.finish(
            "发生错误！重新开一把吧\n错误码：{}".format(code)
            + current_pg.element,
            referrer=current_pg.event.referrer,
        )

    correct_chart_id: str = str(song_id)

    tips: List[str] = [
        f"这首曲子是 {level} 级的哦",
        f"这首曲子的 BPM 是 {int(chart_statistics.main_bpm)} 哦",
        f"这首曲子是 {band_name} 的哦",
    ]

    logger.debug(f"谱面：{song_name} {diff.upper()} LV.{level}")

    def _reveal_data(outcome: str, **kwargs) -> GuessChartRevealData:
        return GuessChartRevealData(
            outcome=outcome,
            song_name=song_name,
            band_name=band_name,
            difficulty=diff,
            play_level=level,
            bpm=main_bpm,
            notes=note_num,
            pool_size=potential_song_number,
            hints_used=3 - len(tips),
            jacket=jacket_pil,
            **kwargs,
        )

    await game_start.send(
        await image_segment_async(img)
        + "获取帮助: @Kasumi /help 猜谱面"
        + current_pg.element,
        referrer=current_pg.event.referrer,
    )

    @waiter(
        waits=["message"],
        matcher=game_start,
        block=False,
        rule=same_channel(event.channel.id),
    )
    async def check(event_: MessageEvent) -> MessageEvent:
        return event_

    async for resp in check(timeout=180):
        # ``/猜谱面 -f`` may be handled by the outer command matcher before
        # this waiter resumes.  In that case the waiter is still registered,
        # so reject any late response from this round before it can emit a
        # hint into the next round.
        if not gamers_store.is_current(event.channel.id, session_token):
            break

        if resp is None:
            gamers_store.remove(event.channel.id)
            await _send_reveal_card(
                _reveal_data("timeout"),
                kit_for_user(event.get_user_id()),
                current_pg,
                f"时间到了哦\n谱面：{song_name} {diff.upper()} LV.{level}",
                jacket_image,
            )
            break

        msg, user_id, message_id = (
            str(resp.get_message()),
            resp.get_user_id(),
            resp.message.id,
        )
        current_pg = PG(resp)
        gens[message_id] = current_pg

        if _stop_if_force_stop(msg, event.channel.id):
            break

        if msg.isdigit():
            guessed_chart_id = msg
        else:
            if msg == "提示":
                if game_type == "given_game_difficulty":
                    if game_difficulty in {"hard", "expert"}:
                        await game_start.send(
                            "hard 和 expert 难度没有提示哦" + current_pg.element,
                            referrer=current_pg.event.referrer,
                        )
                        continue
                if not tips:
                    await game_start.send(
                        "没有更多提示了哦" + current_pg.element,
                        referrer=current_pg.event.referrer,
                    )
                else:
                    await game_start.send(
                        tips[0] + current_pg.element,
                        referrer=current_pg.event.referrer,
                    )
                    tips.pop(0)
                continue
            elif msg == "bzd" or msg == "不知道":
                gamers_store.remove(event.channel.id)
                await _send_reveal_card(
                    _reveal_data("bzd"),
                    kit_for_user(event.get_user_id()),
                    current_pg,
                    f"要再试一次吗？\n谱面：{song_name} {diff.upper()} LV.{level}",
                    jacket_image,
                )
                break

            enriched_song = build_enriched_dictionary(nickname_song, song_raw_data)
            guessed_chart_id = fuzzy_match(msg, enriched_song)

        if guessed_chart_id == correct_chart_id:
            gamers_store.remove(event.channel.id)
            if game_type == "given_game_difficulty":
                amount = (
                    (max_amount / max_song_num) * potential_song_number
                ).__ceil__()
                if game_difficulty == "hard":
                    amount *= 1.5
                elif game_difficulty == "expert":
                    amount *= 1.5 * 2.5
                amount = amount.__ceil__()
            elif game_type == "given_play_level":
                amount = (
                    (max_amount / max_song_num) * potential_song_number
                ).__ceil__()
            else:
                await game_start.finish(
                    "未知游戏类型！" + current_pg.element,
                    referrer=current_pg.event.referrer,
                )

            base_amount = amount
            birthday_characters = get_today_birthday()
            multiplier = 2 if birthday_characters else 1
            amount *= multiplier

            monetary.add(user_id, amount, "guess_chart")

            # Daily task callback for guess_chart win
            task_msg = await check_progress(
                user_id,
                "guess_chart_win",
                {"difficulty": game_difficulty},
            )

            # Level-up
            old_level = monetary.get_level(user_id)
            await monetary.add_xp(user_id, amount)
            new_level = monetary.get_level(user_id)

            # One card replaces the old answer text + task_msg + level_msg +
            # trailing jacket sequence. It renders in the WINNER's theme with
            # their name on the signature — winning shows the theme off.
            winner = identity_for(user_id, avatar=await get_avatar(user_id))
            await _send_reveal_card(
                _reveal_data(
                    "win",
                    winner=winner,
                    base_amount=base_amount,
                    final_amount=amount,
                    birthday_names=tuple(birthday_characters),
                    multiplier=multiplier,
                    task=_completed_task(user_id) if task_msg else None,
                    level=_level_gain(old_level, new_level),
                    owner_name=winner.nickname,
                ),
                kit_for_user(user_id),
                current_pg,
                f"回答正确！奖励你 {amount} 个Pt\n谱面：{song_name} {diff.upper()} LV.{level}",
                jacket_image,
            )
            break
        else:
            logger.debug(
                f"用户猜了 {msg} -> {guessed_chart_id}, 正确答案是 {correct_chart_id}"
            )
