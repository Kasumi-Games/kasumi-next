import json
from pathlib import Path
from typing import Dict, List
from nonebot.log import logger
from nonebot.params import CommandArg
from nonebot_plugin_waiter import waiter
from nonebot import on_command, get_driver, get_plugin_config
from nonebot.adapters.satori import MessageEvent, MessageSegment, Message

from utils import encode_with_ntsilk
from utils.passive_generator import PassiveGenerator as PG

from .. import monetary

from .config import Config
from .utils import call_speaker_api, call_synthesize_api, match_character, speaker_dict


plugin_config = get_plugin_config(Config)

speakers = None

with open(Path(__file__).parent / "characters.json", "r", encoding="utf-8") as f:
    characters: Dict[str, List[str]] = json.load(f)


vits = on_command("tts", priority=10, block=True)


@get_driver().on_startup
async def get_available_speakers():
    global speakers
    try:
        speakers = await call_speaker_api(
            url=plugin_config.bert_vits_api_url + "/speakers"
        )
        # key: speaker_id, value: speaker_name
    except Exception:
        logger.error(
            "Speaker list fetching failed, will try again when next called",
            exc_info=True,
        )


@vits.handle()
async def handle_vits(event: MessageEvent, arg: Message = CommandArg()):
    global speakers
    if speakers is None:
        try:
            speakers = await call_speaker_api(
                url=plugin_config.bert_vits_api_url + "/speakers"
            )
        except Exception as e:
            logger.error(f"Fetching speakers failed: {e}", exc_info=True)
            await vits.finish("TTS 服务出现故障，待会再来试试吧…")

    for seg in arg:
        if seg.type != "text":
            await vits.finish("Kasumi不太能理解怎么把这个转成语音呢...")

    args = arg.extract_plain_text().split(maxsplit=1)

    character = None
    text = None

    passive_generator = PG(event)

    if len(args) == 1:
        if args[0] in speakers.values():
            character = args[0]
        else:
            character = match_character(args[0], characters)

        if character is None:
            text = args[0]

    elif len(args) == 2:
        if args[0] in speakers.values():
            character = args[0]
            text = args[1]
        else:
            character = match_character(args[0], characters)
            text = args[1]

    # 使用 waiter 等待用户输入
    @waiter(waits=["message"], keep_session=True)
    async def check(event_: MessageEvent):
        return event_

    if character is None:
        await vits.send(
            "未获取到角色信息，把你要的角色名字告诉我吧~\n邦邦的角色支持使用别名哦，比如“香澄”可以写成“ksm”"
            + passive_generator.element
        )

        # 使用 speaker_list 作为角色列表
        await vits.send(
            "角色列表：\n"
            + "\n".join([f"{k}: {', '.join(v)}" for k, v in speaker_dict.items()])
            + passive_generator.element
        )

        resp = await check.wait(timeout=60)

        if resp is None:
            await vits.finish("时间到了哦，流程已结束" + passive_generator.element)

        passive_generator = PG(resp)

        input_text = resp.get_message().extract_plain_text()

        character = match_character(input_text, characters)

        if character is None and input_text in speakers.values():
            character = input_text

        if character is None:
            await vits.finish("Kasumi不太认识这个角色呢..." + passive_generator.element)

    if text is None:
        await vits.send("请告诉我你想让角色说的话吧~" + passive_generator.element)

        resp = await check.wait(timeout=60)

        if resp is None:
            await vits.finish("时间到了哦，流程已结束" + passive_generator.element)

        text = resp.get_message().extract_plain_text()

    required_amount = (len(text) / 10).__ceil__()
    has_amount = monetary.get(event.get_user_id())
    if has_amount < required_amount:
        await vits.finish(
            f"你现在共有 {has_amount} 个星之碎片，但语音生成需要 {required_amount} 个星之碎片，去玩游戏赚取碎片吧"
            + passive_generator.element
        )

    monetary.cost(event.get_user_id(), required_amount, "vits")
    speaker_id = [k for k, v in speakers.items() if v == character][0]

    try:
        response = await call_synthesize_api(
            text=text,
            speaker_id=speaker_id,
            url=plugin_config.bert_vits_api_url + "/synthesize",
        )
    except Exception as e:
        monetary.add(event.get_user_id(), required_amount, "vits_error")
        await vits.finish("请求失败：" + str(e) + passive_generator.element)

    await vits.send(
        MessageSegment.audio(
            raw=encode_with_ntsilk(response, "wav", "ntsilk"), mime="audio/silk"
        )
        + passive_generator.element
    )

    await vits.finish(
        f"本次语音合成消耗了 {required_amount} 个星之碎片，你还有 {monetary.get(event.get_user_id())} 个星之碎片"
        + passive_generator.element
    )
