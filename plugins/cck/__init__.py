import json
import random
from typing import Any
from typing import Dict
from typing import List
from typing import Union
from pathlib import Path

from PIL import Image
from nonebot import require
from nonebot import get_driver
from nonebot import on_command
from nonebot import get_plugin_config
from nonebot.log import logger
from nonebot.params import CommandArg
from nonebot.adapters.satori import Message
from nonebot.adapters.satori import MessageEvent
from nonebot.adapters.satori import MessageSegment

require("daily_task")
require("nonebot_plugin_waiter")
require("nonebot_plugin_localstore")
require("nonebot_plugin_apscheduler")

import nonebot_plugin_localstore as localstore  # noqa: E402
from nonebot_plugin_waiter import waiter  # noqa: E402

from utils import get_today_birthday  # noqa: E402
from utils.avatar import get_avatar  # noqa: E402
from utils.images import image_segment  # noqa: E402
from utils.theming import kit_for_user  # noqa: E402
from utils.identity import identity_for  # noqa: E402
from utils.passive_generator import PassiveGenerator as PG  # noqa: E402
from utils.passive_generator import generators as gens  # noqa: E402

from .. import monetary  # noqa: E402
from .card import Card  # noqa: E402
from .draw import image_to_message  # noqa: E402
from .draw import random_crop_image  # noqa: E402
from .store import GamersStore  # noqa: E402
from .config import Config  # noqa: E402
from .render import LevelGain  # noqa: E402
from .render import CckRevealData  # noqa: E402
from .render import TaskCompletion  # noqa: E402
from .render import reveal_page  # noqa: E402
from ..daily_task import check_progress  # noqa: E402
from ..daily_task import get_today_task  # noqa: E402
from ..monetary.level_service import LEVEL_UP_STICKERS  # noqa: E402

plugin_config = get_plugin_config(Config)

cut_name_to_amount = {
    "[easy]": (1, 2),
    "[normal]": (2, 3),
    "[hard]": (3, 4),
    "[expert]": (4, 6),
    "[hard++]": (4, 5),
    "[expert++]": (5, 7),
    "[黑白木筏]": (5, 7),
    "[高闪大图]": (2, 4),
    "[五只小猫]": (6, 9),
    "[超级猫猫]": (8, 12),
    "[寻找记忆]": (5, 7),
    "[6块床板]": (5, 8),
}

data_path = localstore.get_data_dir("cck")
cache_path = localstore.get_cache_dir("cck")

card_manager = Card(plugin_config.bestdori_proxy)
gamers_store = GamersStore()


image_cut_settings: List[Dict[str, Any]] = json.loads(
    (Path(__file__).parent / "image_cut_settings.json").read_text("utf-8")
)
difficulty_settings: Dict[str, List[Dict[str, Any]]] = {}
for setting in image_cut_settings:
    difficulty_name = setting["cut_name"].strip("[]")
    if difficulty_name not in difficulty_settings:
        difficulty_settings[difficulty_name] = []
    difficulty_settings[difficulty_name].append(setting)
available_difficulties = "、".join(difficulty_settings.keys())

character_data: Dict[str, List[str]] = json.loads(
    (Path(__file__).parent / "character_data.json").read_text("utf-8")
)

for k, v in character_data.items():
    character_data[k] = [str(i).lower() for i in v]

if plugin_config.enable_cck:

    @get_driver().on_startup
    async def init_card():
        await card_manager.initialize(data_path, cache_path)

    # scheduler.scheduled_job("cron", hour=0, minute=0)(card_manager._get_data)
    # 运行 _get_data 后会阻塞，不清楚为什么，所以暂时注释掉，有空重启 Kasumi 就能更新


#: Per-server value pick order, matching ``Card._get_res_info``.
_SERVER_PICK_ORDER = (0, 3, 2, 1, 4)


def _localized(values) -> str | None:
    """First non-empty per-server value from a bestdori 5-tuple, or ``None``."""

    if not isinstance(values, (list, tuple)):
        return None
    for index in _SERVER_PICK_ORDER:
        if index < len(values) and values[index]:
            return str(values[index])
    return None


def _completed_task(user_id: str) -> TaskCompletion | None:
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


def _level_gain(old_level: int, new_level: int) -> LevelGain | None:
    if new_level <= old_level:
        return None
    return LevelGain(
        old_level=old_level,
        new_level=new_level,
        stickers=(new_level - old_level) * LEVEL_UP_STICKERS,
    )


start_cck = on_command(
    "猜卡面",
    aliases={"猜猜看", "cck"},
    priority=10,
    block=True,
    rule=lambda: plugin_config.enable_cck,
)


async def _send_reveal_card(
    data: CckRevealData,
    kit,
    pg: PG,
    fallback_text: str,
    fallback_image: MessageSegment,
) -> None:
    """Render and send the round-exit card as one message.

    On a render failure the round must still resolve, so this falls back to
    the pre-card shape: the answer as text plus the raw full card image.
    """

    try:
        image = await reveal_page(data, kit).render_async()
    except Exception:
        logger.opt(exception=True).warning("cck reveal render failed; sending text")
        await start_cck.send(
            fallback_text + pg.element, referrer=pg.event.referrer
        )
        await start_cck.send(
            fallback_image + pg.element, referrer=pg.event.referrer
        )
        return
    await start_cck.send(
        image_segment(image) + pg.element, referrer=pg.event.referrer
    )


@start_cck.handle()
async def handle_cck(event: MessageEvent, arg: Message = CommandArg()):
    arg_text = arg.extract_plain_text().strip()
    gens[event.message.id] = PG(event)

    if arg_text == "-h":
        await start_cck.finish(
            (
                "猜卡面玩法：\n"
                "/猜卡面：随机难度开始\n"
                "/猜卡面 <难度>：指定难度开始\n"
                "/猜卡面 -f：强制结束当前游戏\n"
                f"可用难度：{available_difficulties}\n"
                "游戏开始后，请发送你猜到的角色名称或昵称，每个人最多可猜三次\n"
                "如果猜不出来，可以发送 bzd 查看答案"
            )
            .replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;")
            + gens[event.message.id].element,
            referrer=gens[event.message.id].event.referrer,
        )

    if arg_text == "-f" and event.channel.id in gamers_store.get():
        gamers_store.remove(event.channel.id)
        await start_cck.finish(
            "已强制结束猜卡面" + gens[event.message.id].element,
            referrer=gens[event.message.id].event.referrer,
        )

    if arg_text == "-f":
        await start_cck.finish(
            "没有正在进行的猜卡面，你可以直接使用 @Kasumi /猜卡面 来开始"
            + gens[event.message.id].element,
            referrer=gens[event.message.id].event.referrer,
        )

    image_cut_setting: Dict[str, Any]
    if arg_text == "":
        image_cut_setting = random.choice(image_cut_settings)
    elif arg_text in difficulty_settings:
        image_cut_setting = random.choice(difficulty_settings[arg_text])
    else:
        await start_cck.finish(
            f"未知难度：{arg_text}\n"
            f"可用难度：{available_difficulties}\n"
            "可使用 /猜卡面 -h 查看帮助" + gens[event.message.id].element,
            referrer=gens[event.message.id].event.referrer,
        )

    if event.channel.id in gamers_store.get():
        await start_cck.finish(
            "你已经在猜卡面咯" + gens[event.message.id].element,
            referrer=gens[event.message.id].event.referrer,
        )

    gamers_store.add(event.channel.id)

    character_id, card_id, image_path = await card_manager.random_card_image()

    character_name = character_data[character_id][0]

    logger.info(
        f"character_name: {character_name}, character_id: {character_id}, card_id: {card_id}"
    )

    card_info = card_manager.__processed_data__.get(str(card_id), {})
    card_title = _localized(card_info.get("prefix"))
    card_rarity = card_info.get("rarity")
    card_type = card_info.get("type")
    difficulty_label = image_cut_setting["cut_name"].strip("[]")

    def _reveal_data(outcome: str, **kwargs) -> CckRevealData:
        return CckRevealData(
            outcome=outcome,
            character_name=character_name,
            card_id=str(card_id),
            card_image=image_path,
            card_title=card_title,
            rarity=card_rarity,
            card_type=card_type,
            difficulty=difficulty_label,
            **kwargs,
        )

    pil_full_image = Image.open(image_path)
    full_image = image_to_message(pil_full_image)
    image = random_crop_image(
        pil_full_image,
        image_cut_setting["cut_width"],
        image_cut_setting["cut_length"],
        image_cut_setting["is_black"],
        image_cut_setting["cut_counts"],
    )

    gens[event.message.id] = PG(event)
    latest_message_id = event.message.id

    await start_cck.send(
        image
        + f"{image_cut_setting['cut_name']}获取帮助: @Kasumi /help 猜卡面"
        + gens[event.message.id].element,
        referrer=gens[event.message.id].event.referrer,
    )

    @waiter(waits=["message"], matcher=start_cck, block=False)
    async def check(event_: MessageEvent) -> Union[MessageEvent, bool, bool]:
        if event_.channel.id != event.channel.id:
            return False
        return event_

    player_counts: Dict[str, int] = {}

    async for resp in check(timeout=180):
        if resp is False:
            continue

        if resp is True:
            raise Exception("Unexpected response")

        if resp is None:
            gamers_store.remove(event.channel.id)
            await _send_reveal_card(
                _reveal_data("timeout"),
                kit_for_user(event.get_user_id()),
                gens[latest_message_id],
                f"时间到！答案是———{character_name} card_id: {card_id}",
                full_image,
            )
            break

        msg, user_id, msg_id = (
            str(resp.get_message()),
            resp.get_user_id(),
            resp.message.id,
        )
        gens[msg_id] = PG(resp)
        latest_message_id = msg_id

        if msg == "bzd":
            gamers_store.remove(event.channel.id)
            await _send_reveal_card(
                _reveal_data("bzd"),
                kit_for_user(event.get_user_id()),
                gens[msg_id],
                f"答案是———{character_name} card_id: {card_id}",
                full_image,
            )
            break

        found_characters = [
            key for key, values in character_data.items() if msg.lower() in values
        ]

        if not found_characters:
            continue

        if user_id not in player_counts.keys():
            player_counts[user_id] = 0

        if player_counts[user_id] >= 3:
            await start_cck.send(
                "你已经回答三次啦，可以回复 bzd 查看答案～" + gens[msg_id].element,
                referrer=gens[msg_id].event.referrer,
            )
            continue

        if found_characters[0] != character_id:
            player_counts[user_id] += 1
            continue

        gamers_store.remove(event.channel.id)
        characters = get_today_birthday()
        base_amount = random.randint(
            *cut_name_to_amount[image_cut_setting["cut_name"]]
        )
        multiplier = 1
        birthday_names: tuple = ()
        if characters:
            if character_name not in characters:
                multiplier = 2
                birthday_names = tuple(characters)
            else:
                multiplier = 4
                birthday_names = (character_name,)
        amount = base_amount * multiplier
        monetary.add(user_id, amount, "cck")

        # Daily task callback (first-try win is checked via conditions)
        player_counts[user_id] += 1
        task_msg = await check_progress(
            user_id,
            "cck_first_try",
            {"attempt": player_counts[user_id]},
        )

        # Level-up
        old_level = monetary.get_level(user_id)
        await monetary.add_xp(user_id, amount)
        new_level = monetary.get_level(user_id)

        # One card replaces the old answer text + full image + task_msg +
        # level_msg sequence. It renders in the WINNER's theme with their
        # name on the signature — winning shows the theme off.
        winner = identity_for(user_id, avatar=await get_avatar(user_id))
        await _send_reveal_card(
            _reveal_data(
                "win",
                winner=winner,
                winner_attempt=player_counts[user_id],
                base_amount=base_amount,
                final_amount=amount,
                birthday_names=birthday_names,
                multiplier=multiplier,
                task=_completed_task(user_id) if task_msg else None,
                level=_level_gain(old_level, new_level),
                owner_name=winner.nickname,
            ),
            kit_for_user(user_id),
            gens[msg_id],
            f"正确！答案是———{character_name}，奖励你 {amount} 个Pt！card_id: {card_id}",
            full_image,
        )

        break
