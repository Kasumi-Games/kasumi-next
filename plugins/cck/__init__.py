import json
import random
from PIL import Image
from .. import monetary
from pathlib import Path
from nonebot_plugin_waiter import waiter
from typing import Any, Dict, List, Union
from nonebot import on_command, get_driver, require
from nonebot.adapters.satori import MessageEvent, MessageSegment

require("nonebot_plugin_localstore")

import nonebot_plugin_localstore as localstore

from .card import Card
from .store import GamersStore
from .draw import random_crop_image, image_to_message


cut_name_to_amount = {
    "[easy]": (1, 2),
    "[normal]": (2, 3),
    "[hard]": (3, 4),
    "[expert]": (4, 6),
    "[hard++]": (4, 5),
    "[expert++]": (5, 6),
    "[黑白木筏]": (6, 12),
    "[高闪大图]": (7, 12),
    "[五只小猫]": (7, 12),
    "[超级猫猫]": (8, 12),
    "[寻找记忆]": (5, 10),
    "[6块床板]": (5, 10),
}

data_path = localstore.get_data_dir("cck")
cache_path = localstore.get_cache_dir("cck")

card_manager = Card()
gamers_store = GamersStore()


image_cut_settings: List[Dict[str, Any]] = json.loads(
    (Path(__file__).parent / "image_cut_settings.json").read_text("utf-8")
)
character_data: Dict[str, List[str]] = json.loads(
    (Path(__file__).parent / "character_data.json").read_text("utf-8")
)


@get_driver().on_startup
async def init_card():
    await card_manager.initialize(data_path, cache_path)


start_cck = on_command("cck", aliases={"猜卡面", "cck", "gbc"}, priority=10, block=True)


@start_cck.handle()
async def handle_cck(event: MessageEvent):
    if event.channel.id in gamers_store.get():
        await start_cck.finish("你已经在猜卡面咯")

    gamers_store.add(event.channel.id)

    character_id, card_id, image_path = await card_manager.random_card_image()
    image_cut_setting = random.choice(image_cut_settings)

    character_name = character_data[character_id][0]

    pil_full_image = Image.open(image_path)
    full_image = image_to_message(pil_full_image)
    image = random_crop_image(
        pil_full_image,
        image_cut_setting["cut_width"],
        image_cut_setting["cut_length"],
        image_cut_setting["is_black"],
        image_cut_setting["cut_counts"],
    )

    await start_cck.send(image + f"{image_cut_setting['cut_name']}获取帮助: @Kasumi /help 猜猜看")

    @waiter(waits=["message"], matcher=start_cck)
    async def check(event_: MessageEvent) -> Union[Tuple[str, str], bool, None]:
        if event_.channel.id != event.channel.id:
            return False
        return str(event_.get_message()), event_.get_user_id()

    player_counts: Dict[str, int] = {}

    async for resp in check(timeout=300):
        if resp is False:
            continue

        if resp is None:
            gamers_store.remove(event.channel.id)
            await start_cck.send(f"时间到！答案是———{character_name}card_id: {card_id}")
            await start_cck.send(full_image)
            break

        resp, user_id = resp

        if resp == "bzd":
            gamers_store.remove(event.channel.id)
            await start_cck.send(f"答案是———{character_name}card_id: {card_id}")
            await start_cck.send(full_image)
            break

        found_characters = [
            key for key, values in character_data.items() if resp in values
        ]

        if not found_characters:
            continue

        if user_id not in player_counts.keys():
            player_counts[user_id] = 0

        if player_counts[user_id] >= 2:
            await start_cck.send(MessageSegment.at(user_id) + f"你已经回答三次啦，可以回复 bzd 查看答案～")
            continue

        if found_characters[0] != character_id:
            player_counts[user_id] += 1
            continue

        gamers_store.remove(event.channel.id)
        amount = random.randint(*cut_name_to_amount[image_cut_setting["cut_name"]])
        monetary.add(user_id, amount)
        await start_cck.send(MessageSegment.at(user_id) + f"正确！奖励你 {amount} 个星之碎片！答案是———{character_name} card_id: {card_id}")
        await start_cck.send(full_image)
        break
