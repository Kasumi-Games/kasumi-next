import random
from pathlib import Path
from bestdori import songs
from nonebot.log import logger
from bestdori.charts import Chart
from bestdori.render import render
from nonebot.params import Depends
from typing import Optional, List, Union
from nonebot_plugin_waiter import waiter
from nonebot import on_command, require, get_driver
from nonebot.adapters.satori import MessageSegment, MessageEvent


require("nonebot_plugin_apscheduler")

from nonebot_plugin_apscheduler import scheduler

from .. import monetary
from .store import SongStore, BandStore, GamersStore
from .utils import (
    diff_num,
    fuzzy_match,
    num_to_range,
    get_difficulty,
    read_csv_to_dict,
    get_jacket_image,
    render_to_slices,
    pil_image_to_bytes,
    get_value_from_list,
    compare_origin_songname,
)


nickname_song = read_csv_to_dict(Path(__file__).parent / "nickname_song.csv")


diff_to_amount = {
    "easy": (1, 2),
    "normal": (2, 3),
    "hard": (3, 6),
    "expert": (6, 12),
}


song_store = SongStore()
band_store = BandStore()
gamers_store = GamersStore()


async def is_gaming(event: MessageEvent) -> bool:
    return event.channel.id in gamers_store.get()


game_start = on_command(
    "猜谱面", aliases={"猜谱", "cpm", "谱面挑战"}, priority=10, block=True
)


@get_driver().on_startup
@scheduler.scheduled_job("cron", hour=0, minute=0)
async def refresh_data():
    await song_store.update()
    await band_store.update()


@game_start.handle()
async def handle_start(
    event: MessageEvent,
    song_data: dict = Depends(song_store.get),
    band_data: dict = Depends(band_store.get),
    game_difficulty: str = Depends(get_difficulty),
    song_raw_data: dict = Depends(song_store.get_raw),
):
    if await is_gaming(event):
        await game_start.finish("已经在猜谱面了哦")

    gamers_store.add(event.channel.id)

    await game_start.send("正在加载谱面...")

    if game_difficulty == "easy":
        # 在 28 级及以上的歌曲中抽取
        filtered_song_data = {
            k: v
            for k, v in song_data.items()
            if v.get("difficulty", {}).get(diff_num["expert"], {}).get("playLevel", 0)
            >= 28
            or v.get("difficulty", {}).get(diff_num["special"], {}).get("playLevel", 0)
            >= 28
        }
    elif game_difficulty == "normal":
        # 在 27 级及以上的歌曲中抽取
        filtered_song_data = {
            k: v
            for k, v in song_data.items()
            if v.get("difficulty", {}).get(diff_num["expert"], {}).get("playLevel", 0)
            >= 27
            or v.get("difficulty", {}).get(diff_num["special"], {}).get("playLevel", 0)
            >= 27
        }
    else:
        filtered_song_data = song_data

    song_id, song_basic_info = random.choice(list(filtered_song_data.items()))

    song_detail = songs.Song(song_id)

    if song_data[song_id]["difficulty"].get(diff_num["special"]):
        chart_difficulty = random.choice(["expert", "special"])
    else:
        chart_difficulty = "expert"

    chart = await Chart.get_chart_async(song_id, chart_difficulty)
    chart_statistics = chart.count()

    try:
        if game_difficulty in ["easy", "normal"]:
            img = render(chart)
        else:
            img = render_to_slices(chart, game_difficulty)
    except MemoryError:
        await game_start.finish("发生谱面渲染错误！重新开一把吧")

    await game_start.send(
        MessageSegment.image(raw=pil_image_to_bytes(img), mime="image/png")
        + "获取帮助: @Kasumi /help 猜谱面"
    )

    correct_chart_id: str = song_id
    diff: str = chart_difficulty
    song_info = await song_detail.get_info_async()
    level = song_info.get("difficulty", {}).get(diff_num[diff], {}).get("playLevel")
    song_name = get_value_from_list(song_basic_info.get("musicTitle", []))

    note_num = chart_statistics.notes
    note_num_range = num_to_range(note_num)

    band_id: int = song_info["bandId"]
    band_name = get_value_from_list(band_data[str(band_id)]["bandName"])

    jacket_image = await get_jacket_image(int(song_id), song_info)

    tips: List[str] = [
        f"这首曲子是 {level} 级的哦",
        f"这首曲子的物量是 {note_num_range[0]} 到 {note_num_range[1]} 哦",
        f"这首曲子是 {band_name} 的哦",
    ]

    logger.debug(f"谱面：{song_name} " f"{diff.upper()} LV.{level}")

    @waiter(waits=["message"], matcher=game_start)
    async def check(event_: MessageEvent) -> Union[Optional[str], bool]:
        if event_.channel.id != event.channel.id:
            return False
        return str(event_.get_message())

    async for resp in check(timeout=300):
        if resp is False:
            continue
        if resp is None:
            gamers_store.remove(event.channel.id)
            await game_start.send(
                f"时间到了哦\n谱面：{song_name} " f"{diff.upper()} LV.{level}"
            )
            await game_start.send(
                MessageSegment.image(raw=jacket_image, mime="image/png")
            )
            break
        if resp.isdigit():
            guessed_chart_id = resp
        else:
            if resp == "提示":
                if not tips:
                    await game_start.send("没有更多提示了哦")
                else:
                    await game_start.send(tips[0])
                    tips.pop(0)
                continue
            elif resp == "bzd":
                gamers_store.remove(event.channel.id)
                await game_start.send(
                    "要再试一次吗？\n"
                    f"谱面：{song_name} "
                    f"{diff.upper()} LV.{level}"
                )
                await game_start.send(
                    MessageSegment.image(raw=jacket_image, mime="image/png")
                )
                break

            guessed_chart_id = fuzzy_match(resp, nickname_song)
            if guessed_chart_id is None:
                guessed_chart_id = compare_origin_songname(resp.strip(), song_raw_data)

        if guessed_chart_id == correct_chart_id:
            gamers_store.remove(event.channel.id)
            amount = random.randint(*diff_to_amount[game_difficulty])
            user_id = event.get_user_id()
            monetary.add(user_id, amount)
            await game_start.send(
                f"回答正确！奖励你 {amount} 个星之碎片"
                f"谱面：{song_name} "
                f"{diff.upper()} LV.{level}"
            )
            await game_start.send(
                MessageSegment.image(raw=jacket_image, mime="image/png")
            )
            break
