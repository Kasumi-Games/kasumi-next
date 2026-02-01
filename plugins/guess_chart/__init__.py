import random
from pathlib import Path
from bestdori import songs
from bestdori import settings
from nonebot.log import logger
from bestdori.charts import Chart
from bestdori.render import render
from nonebot import get_plugin_config
from typing import Optional, List, Union
from nonebot.params import Depends, CommandArg
from nonebot import on_command, require, get_driver
from nonebot.adapters.satori import MessageSegment, MessageEvent, Message

require("nonebot_plugin_waiter")
require("nonebot_plugin_apscheduler")

from nonebot_plugin_waiter import waiter  # noqa: E402
from nonebot_plugin_apscheduler import scheduler  # noqa: E402

from .. import monetary  # noqa: E402
from utils import get_today_birthday  # noqa: E402
from utils.passive_generator import generators as gens  # noqa: E402
from utils.passive_generator import PassiveGenerator as PG  # noqa: E402

from .config import Config  # noqa: E402
from .store import SongStore, BandStore, GamersStore  # noqa: E402
from .utils import (  # noqa: E402
    diff_num,
    fuzzy_match,
    get_difficulty,
    read_csv_to_dict,
    get_jacket_image,
    render_to_slices,
    flatten_song_data,
    sort_by_difficulty,
    pil_image_to_bytes,
    get_value_from_list,
    compare_origin_songname,
)


plugin_config = get_plugin_config(Config)
settings.proxy = plugin_config.bestdori_proxy

nickname_song = read_csv_to_dict(Path(__file__).parent / "nickname_song.csv")


song_store = SongStore()
band_store = BandStore()
gamers_store = GamersStore()


async def is_gaming(event: MessageEvent) -> bool:
    return event.channel.id in gamers_store.get()


game_start = on_command(
    "猜谱面",
    aliases={"猜谱", "cpm", "谱面挑战"},
    priority=10,
    block=True,
    rule=lambda: plugin_config.enable_guess_chart,
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
    gens[event.message.id] = PG(event)
    latest_message_id = event.message.id

    if (
        arg is not None
        and arg.extract_plain_text().strip() == "-f"
        and await is_gaming(event)
    ):
        gamers_store.remove(event.channel.id)
        await game_start.finish("已强制退出猜谱面" + gens[event.message.id].element)

    if arg is not None and arg.extract_plain_text().strip() == "-f":
        await game_start.finish("没有正在进行的猜谱面" + gens[event.message.id].element)

    if await is_gaming(event):
        await game_start.finish(
            "已经在猜谱面了哦，如果有异常，请使用 @Kasumi /猜谱面 -f 以强制结束游戏"
            + gens[event.message.id].element
        )

    gamers_store.add(event.channel.id)

    await game_start.send("正在加载谱面..." + gens[event.message.id].element)

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
                + gens[event.message.id].element
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
        await game_start.finish("没有符合条件的谱面" + gens[event.message.id].element)

    song = random.choice(filtered_song_data)

    song_id = int(song["song_id"])

    try:
        song_detail = songs.Song(song_id)

        chart_difficulty = song["difficulty"]
        chart = await Chart.get_chart_async(song_id, chart_difficulty)
        chart_statistics = chart.count()
    except Exception as e:
        logger.error(f"猜谱面：{e}", exc_info=True)
        gamers_store.remove(event.channel.id)
        await game_start.finish(
            "发生错误！重新开一把吧" + gens[event.message.id].element
        )

    try:
        if game_difficulty in ["easy", "normal"]:
            img = render(chart)
        else:
            img = render_to_slices(chart, game_difficulty)
    except MemoryError:
        gamers_store.remove(event.channel.id)
        await game_start.finish(
            "发生谱面渲染错误！重新开一把吧" + gens[event.message.id].element
        )

    correct_chart_id: str = str(song_id)
    diff: str = chart_difficulty
    song_info = await song_detail.get_info_async()
    level = song_info.get("difficulty", {}).get(diff_num[diff], {}).get("playLevel")
    song_name = song["song_name"]

    # note_num = chart_statistics.notes
    # note_num_range = num_to_range(note_num)
    # removed because the information can be found in the chart image

    band_id: int = song_info["bandId"]
    band_name = get_value_from_list(band_data[str(band_id)]["bandName"])

    jacket_image = await get_jacket_image(int(song_id), song_info)

    tips: List[str] = [
        f"这首曲子是 {level} 级的哦",
        f"这首曲子的 BPM 是 {int(chart_statistics.main_bpm)} 哦",
        f"这首曲子是 {band_name} 的哦",
    ]

    logger.debug(f"谱面：{song_name} {diff.upper()} LV.{level}")

    await game_start.send(
        MessageSegment.image(raw=pil_image_to_bytes(img), mime="image/png")
        + "获取帮助: @Kasumi /help 猜谱面"
        + gens[event.message.id].element
    )

    @waiter(waits=["message"], matcher=game_start, block=False)
    async def check(event_: MessageEvent) -> Union[Optional[MessageEvent], bool]:
        if event_.channel.id != event.channel.id:
            return False
        return event_

    async for resp in check(timeout=180):
        if resp is False:
            continue

        if resp is True:
            raise Exception("Unexpected response")

        if resp is None:
            gamers_store.remove(event.channel.id)
            await game_start.send(
                f"时间到了哦\n谱面：{song_name} "
                f"{diff.upper()} LV.{level}" + gens[latest_message_id].element
            )
            await game_start.send(
                MessageSegment.image(raw=jacket_image, mime="image/png")
                + gens[latest_message_id].element
            )
            break

        msg, user_id, message_id = (
            str(resp.get_message()),
            resp.get_user_id(),
            resp.message.id,
        )
        gens[message_id] = PG(resp)
        latest_message_id = message_id

        if msg.isdigit():
            guessed_chart_id = msg
        else:
            if msg == "提示":
                if game_type == "given_game_difficulty":
                    if game_difficulty in {"hard", "expert"}:
                        await game_start.send(
                            "hard 和 expert 难度没有提示哦" + gens[message_id].element
                        )
                        continue
                if not tips:
                    await game_start.send("没有更多提示了哦" + gens[message_id].element)
                else:
                    await game_start.send(tips[0] + gens[message_id].element)
                    tips.pop(0)
                continue
            elif msg == "bzd":
                gamers_store.remove(event.channel.id)
                await game_start.send(
                    "要再试一次吗？\n"
                    f"谱面：{song_name} "
                    f"{diff.upper()} LV.{level}" + gens[message_id].element
                )
                await game_start.send(
                    MessageSegment.image(raw=jacket_image, mime="image/png")
                    + gens[message_id].element
                )
                break

            guessed_chart_id = fuzzy_match(msg, nickname_song)
            if guessed_chart_id is None:
                guessed_chart_id = compare_origin_songname(msg.strip(), song_raw_data)

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
                await game_start.finish("未知游戏类型！" + gens[message_id].element)

            msg = Message()

            birthday_characters = get_today_birthday()
            birthday_characters_str = "和".join(birthday_characters)

            if birthday_characters:
                msg += f"回答正确！因为今天是{birthday_characters_str}的生日，奖励你 {amount} × 2 个星之碎片！\n"
                amount *= 2
            else:
                msg += f"回答正确！奖励你 {amount} 个星之碎片\n"

            monetary.add(user_id, amount, "guess_chart")
            await game_start.send(
                msg + f"谱面：{song_name} "
                f"{diff.upper()} LV.{level}" + gens[message_id].element
            )
            await game_start.send(
                MessageSegment.image(raw=jacket_image, mime="image/png")
                + gens[message_id].element
            )
            break
        else:
            logger.debug(
                f"用户猜了 {msg} -> {guessed_chart_id}, 正确答案是 {correct_chart_id}"
            )
