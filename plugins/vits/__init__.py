import json
import uuid
from typing import Dict
from typing import List
from pathlib import Path

from nonebot import require
from nonebot import get_driver
from nonebot import on_command
from nonebot import get_plugin_config
from nonebot.log import logger
from nonebot.params import CommandArg
from nonebot.adapters.satori import Message
from nonebot.adapters.satori import MessageEvent
from nonebot.adapters.satori import MessageSegment

from utils.error_handler import log_error
from utils.error_handler import handle_error
from utils.error_handler import generate_error_code

require("nonebot_plugin_waiter")

from nonebot_plugin_waiter import waiter  # noqa: E402

from utils import encode_with_ntsilk  # noqa: E402
from utils.content_safety import ContentSafetyError  # noqa: E402
from utils.content_safety import ensure_safe_text  # noqa: E402
from utils.passive_generator import PassiveGenerator as PG  # noqa: E402

from .. import monetary  # noqa: E402
from ..inventory import point_hold_service as point_holds  # noqa: E402
from .utils import speaker_dict  # noqa: E402
from .utils import match_character  # noqa: E402
from .utils import call_speaker_api  # noqa: E402
from .utils import call_synthesize_api  # noqa: E402
from .config import Config  # noqa: E402

plugin_config = get_plugin_config(Config)

speakers = None

with open(Path(__file__).parent / "characters.json", "r", encoding="utf-8") as f:
    characters: Dict[str, List[str]] = json.load(f)


vits = on_command("tts", priority=10, block=True)


def _reserve_vits_charge(user_id: str, amount: int) -> str:
    hold_key = f"vits:{uuid.uuid4().hex}"
    point_holds.reserve_points(
        user_id,
        amount,
        hold_key,
        "vits",
        operation_key=f"{hold_key}:reserve",
    )
    return hold_key


def _settle_vits_charge(hold_key: str) -> bool:
    """Consume a delivered request, or refund it if its Pt scope closed."""

    try:
        point_holds.settle_point_hold(
            hold_key,
            0,
            operation_key=f"{hold_key}:settle",
        )
        return True
    except point_holds.PointHoldScopeClosed:
        point_holds.refund_point_hold(
            hold_key,
            operation_key=f"{hold_key}:scope_cancel",
        )
        return False
    except point_holds.PointHoldClosed:
        hold = point_holds.get_point_hold(hold_key)
        if hold is not None and hold.status == point_holds.HOLD_REFUNDED:
            return False
        raise


def _refund_vits_charge(hold_key: str) -> None:
    point_holds.refund_point_hold(
        hold_key,
        operation_key=f"{hold_key}:error_refund",
    )


@get_driver().on_startup
async def get_available_speakers():
    global speakers
    refunded = point_holds.refund_abandoned_game_holds(("vits",))
    if refunded:
        logger.info(f"已退还 {refunded} 笔上次进程遗留的语音合成费用")
    try:
        speakers = await call_speaker_api(
            url=plugin_config.bert_vits_api_url + "/speakers"
        )
        # key: speaker_id, value: speaker_name
    except Exception as e:
        log_error(generate_error_code(), e, context="vits_speaker_startup")


@vits.handle()
async def handle_vits(event: MessageEvent, arg: Message = CommandArg()):
    global speakers
    if speakers is None:
        try:
            speakers = await call_speaker_api(
                url=plugin_config.bert_vits_api_url + "/speakers"
            )
        except Exception as e:
            code = handle_error(
                e, context="vits_speaker_fetch", user_id=event.get_user_id()
            )
            await vits.finish(
                "TTS 服务出现故障，待会再来试试吧…\n错误码：{}".format(code),
                referrer=event.referrer,
            )

    for seg in arg:
        if seg.type != "text":
            await vits.finish(
                "Kasumi不太能理解怎么把这个转成语音呢...", referrer=event.referrer
            )

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
            + passive_generator.element,
            referrer=passive_generator.event.referrer,
        )

        # 使用 speaker_list 作为角色列表
        await vits.send(
            "角色列表：\n"
            + "\n".join([f"{k}: {', '.join(v)}" for k, v in speaker_dict.items()])
            + passive_generator.element,
            referrer=passive_generator.event.referrer,
        )

        resp = await check.wait(timeout=60)

        if resp is None:
            await vits.finish(
                "时间到了哦，流程已结束" + passive_generator.element,
                referrer=passive_generator.event.referrer,
            )

        passive_generator = PG(resp)

        input_text = resp.get_message().extract_plain_text()

        character = match_character(input_text, characters)

        if character is None and input_text in speakers.values():
            character = input_text

        if character is None:
            await vits.finish(
                "Kasumi不太认识这个角色呢..." + passive_generator.element,
                referrer=passive_generator.event.referrer,
            )

    if text is None:
        await vits.send(
            "请告诉我你想让角色说的话吧~" + passive_generator.element,
            referrer=passive_generator.event.referrer,
        )

        resp = await check.wait(timeout=60)

        if resp is None:
            await vits.finish(
                "时间到了哦，流程已结束" + passive_generator.element,
                referrer=passive_generator.event.referrer,
            )

        text = resp.get_message().extract_plain_text()

    try:
        ensure_safe_text(text)
    except ContentSafetyError as error:
        await vits.finish(
            str(error) + passive_generator.element,
            referrer=passive_generator.event.referrer,
        )

    required_amount = (len(text) / 10).__ceil__()
    has_amount = monetary.get(event.get_user_id())
    if has_amount < required_amount:
        await vits.finish(
            f"你现在共有 {has_amount} Pt，但语音生成需要 {required_amount} Pt，去玩游戏赚取 Pt 吧"
            + passive_generator.element,
            referrer=passive_generator.event.referrer,
        )

    speaker_id = next((key for key, value in speakers.items() if value == character), None)
    if speaker_id is None:
        await vits.finish(
            "这个角色当前没有可用的语音模型，请换一个角色再试试吧~"
            + passive_generator.element,
            referrer=passive_generator.event.referrer,
        )

    user_id = event.get_user_id()
    hold_key = _reserve_vits_charge(user_id, required_amount)
    try:
        response = await call_synthesize_api(
            text=text,
            speaker_id=speaker_id,
            url=plugin_config.bert_vits_api_url + "/synthesize",
        )
        encoded = await encode_with_ntsilk(response, "wav", "ntsilk")
        await vits.send(
            MessageSegment.audio(raw=encoded, mime="audio/silk")
            + passive_generator.element,
            referrer=passive_generator.event.referrer,
        )
        charged = _settle_vits_charge(hold_key)
    except Exception as e:
        _refund_vits_charge(hold_key)
        code = handle_error(e, context="vits_delivery", user_id=user_id)
        await vits.finish(
            "请求失败\n错误码：{}".format(code) + passive_generator.element,
            referrer=passive_generator.event.referrer,
        )

    if charged:
        result_text = (
            f"本次语音合成消耗了 {required_amount} Pt，"
            f"你还有 {monetary.get(user_id)} Pt"
        )
    else:
        result_text = "赛季已切换，本次语音合成未扣除 Pt"
    await vits.finish(
        result_text + passive_generator.element,
        referrer=passive_generator.event.referrer,
    )
