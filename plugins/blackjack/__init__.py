import cv2
import json
from pathlib import Path
from collections import defaultdict
from nonebot.params import CommandArg
from typing import Optional, Dict, Set
from nonebot_plugin_waiter import waiter
from nonebot import on_command, require, get_driver
from nonebot.adapters.satori import MessageEvent, Message, MessageSegment

require("cck")  # for card images
require("nonebot_plugin_localstore")

from .. import monetary  # noqa: E402
from ..cck import card_manager  # noqa: E402
from utils import image_to_bytes  # noqa: E402
from utils.birthday import get_today_birthday  # noqa: E402
from utils.passive_generator import generators as gens  # noqa: E402
from utils.passive_generator import PassiveGenerator as PG  # noqa: E402

from .utils import get_action  # noqa: E402
from .models import Shoe, Hand, Card  # noqa: E402
from .render import BlackjackRenderer  # noqa: E402


HELP_MESSAGE = MessageSegment.image(
    raw=Path("plugins/blackjack/recourses/instruction.png").read_bytes(),
    mime="image/png",
)


def init_shoe() -> Shoe:
    shoe = Shoe(6)
    shoe.shuffle()
    return shoe


channel_shoe_map: Dict[str, Shoe] = defaultdict(init_shoe)
channel_players: Dict[str, Set[str]] = defaultdict(set)
reshuffle_threshold = 52 * 6 * 0.25
renderer: BlackjackRenderer = None


game_start = on_command(
    "黑香澄",
    aliases={
        "blackjack",
        "blackkasumi",
        "blackasumi",
        "bk",
        "bj",
        "黑杰克",
        "二十一点",
    },
    priority=10,
    block=True,
)


def get_character_id(character_name: str) -> Optional[int]:
    """获取角色ID"""
    for id, data in renderer.character_data.items():
        if character_name in data["characterName"]:
            return int(id)
    return None


def get_card_image(card: Card) -> MessageSegment:
    """获取牌的图片"""
    # 对于A牌使用其ace_value，其他牌传None
    ace_value = card.ace_value if card.rank == "A" else None

    if card._get_image is not None:
        return MessageSegment.image(
            raw=image_to_bytes(card._get_image(ace_value)),
            mime="image/png",
        )

    image, _get_image = renderer.generate_card(
        card.rank, card.suit, ace_value=ace_value
    )
    card._get_image = _get_image
    return MessageSegment.image(
        raw=image_to_bytes(image),
        mime="image/png",
    )


@get_driver().on_startup
async def init_blackjack():
    global renderer
    renderer = BlackjackRenderer(
        resource_dir="plugins/blackjack/recourses",
        card_data=card_manager.__summary_data__,
        character_data=json.loads(
            Path("plugins/blackjack/recourses/character_data.json").read_text(
                encoding="utf-8"
            )
        ),
        face_positions=json.loads(
            Path("plugins/blackjack/recourses/face_positions.json").read_text(
                encoding="utf-8"
            )
        ),
        cascade=cv2.CascadeClassifier(
            "plugins/blackjack/recourses/lbpcascade_animeface.xml"
        ),
    )


@game_start.handle()
async def handle_start(event: MessageEvent, arg: Optional[Message] = CommandArg()):
    gens[event.message.id] = PG(event)
    latest_message_id = event.message.id

    @waiter(waits=["message"], matcher=game_start, block=False, keep_session=True)
    async def check(event_: MessageEvent) -> MessageEvent:
        return event_

    arg_text = arg.extract_plain_text().strip()

    if arg_text in ["h", "-h", "--help", "help"]:
        await game_start.finish(HELP_MESSAGE + gens[latest_message_id].element)

    if event.get_user_id() in channel_players[event.channel.id]:
        await game_start.finish(
            "你已经在游戏中了，请先结束当前游戏哦~" + gens[latest_message_id].element
        )
    else:
        channel_players[event.channel.id].add(event.get_user_id())

    bet_amount = None
    character_ids = [get_character_id(name) for name in get_today_birthday()]
    character_ids = [id for id in character_ids if id is not None]

    try:
        bet_amount = int(arg_text)
    except ValueError:
        pass

    if bet_amount is None:
        await game_start.send("你要下注多少碎片呢？" + gens[latest_message_id].element)
        resp = await check.wait(timeout=60)
        if resp is None:
            channel_players[event.channel.id].remove(event.get_user_id())
            await game_start.finish(
                "时间到了哦，黑香澄流程已结束" + gens[latest_message_id].element
            )

        else:
            gens[resp.message.id] = PG(resp)
            latest_message_id = resp.message.id
            try:
                bet_amount = int(str(resp.get_message()).strip())
            except ValueError:
                channel_players[event.channel.id].remove(event.get_user_id())
                await game_start.finish(
                    "输入的金额不是数字，请重新输入" + gens[latest_message_id].element
                )

            if bet_amount <= 0:
                channel_players[event.channel.id].remove(event.get_user_id())
                await game_start.finish(
                    "下注碎片不能少于 1 个哦，请重新输入"
                    + gens[latest_message_id].element
                )

    elif bet_amount <= 0:
        channel_players[event.channel.id].remove(event.get_user_id())
        await game_start.finish(
            "下注碎片不能少于 1 个哦，请重新输入" + gens[latest_message_id].element
        )

    if len(channel_shoe_map[event.channel.id].deck) < reshuffle_threshold:
        await game_start.send(
            "牌靴中的牌数太少啦，Kasumi 重新洗下牌哦~" + gens[latest_message_id].element
        )
        channel_shoe_map[event.channel.id] = init_shoe()

    if (amount := monetary.get(event.get_user_id())) < bet_amount:
        channel_players[event.channel.id].remove(event.get_user_id())
        await game_start.finish(
            f"你只有 {amount} 个碎片，不够下注哦~" + gens[latest_message_id].element
        )

    player_hand = Hand()
    dealer_hand = Hand()
    split_card = False

    player_hand.add_card(channel_shoe_map[event.channel.id].deal())
    dealer_hand.add_card(channel_shoe_map[event.channel.id].deal())
    player_hand.add_card(channel_shoe_map[event.channel.id].deal())
    dealer_hand.add_card(channel_shoe_map[event.channel.id].deal())

    init_msg = MessageSegment.image(
        raw=image_to_bytes(renderer.generate_table(dealer_hand, player_hand, True)),
        mime="image/png",
    )

    if player_hand.value == 21:
        if dealer_hand.value == 21:
            channel_players[event.channel.id].remove(event.get_user_id())
            await game_start.finish(
                MessageSegment.image(
                    raw=image_to_bytes(
                        renderer.generate_table(dealer_hand, player_hand, False)
                    ),
                    mime="image/png",
                )
                + "平局！虽然是 BlackKasumi，但是没有奖励哦~\n"
                + f"你现在有 {monetary.get(event.get_user_id())} 个碎片"
                + gens[latest_message_id].element
            )
        else:
            if len(character_ids) > 0:
                monetary.add(
                    event.get_user_id(), int(bet_amount * 1.5 * 1.5), "blackjack"
                )
            else:
                monetary.add(event.get_user_id(), int(bet_amount * 1.5), "blackjack")

            channel_players[event.channel.id].remove(event.get_user_id())
            await game_start.finish(
                MessageSegment.image(
                    raw=image_to_bytes(
                        renderer.generate_table(dealer_hand, player_hand, False)
                    ),
                    mime="image/png",
                )
                + (
                    f"BlackKasumi！你获得了 1.5 × {bet_amount} = {int(bet_amount * 1.5)} 个碎片！\n"
                    if len(character_ids) == 0
                    else f"BlackKasumi！今天是{'和'.join(get_today_birthday())}的生日，奖励多多！你获得了 1.5 × {bet_amount} × 1.5 = {int(bet_amount * 1.5 * 1.5)} 个碎片！\n"
                )
                + f"你现在有 {monetary.get(event.get_user_id())} 个碎片！"
                + gens[latest_message_id].element
            )

    if player_hand.cards[0].get_value() == player_hand.cards[1].get_value():
        sentence = "你有一对相同点数的牌，是否要分牌？\n"
        await game_start.send(
            init_msg
            + sentence
            + "请从“是”或“否”中选择一项哦"
            + gens[latest_message_id].element
        )
        resp = await check.wait(timeout=60)

        if resp is None:
            await game_start.send(
                "让 Kasumi 等这么久，不许分牌了！" + gens[latest_message_id].element
            )
            split_card = False
        else:
            msg = str(resp.get_message()).strip()
            latest_message_id = resp.message.id
            gens[latest_message_id] = PG(resp)

            if msg not in ["是", "否"]:
                await game_start.send(
                    "听不懂喵，就当你不想分牌了吧~" + gens[latest_message_id].element
                )
                split_card = False
            else:
                split_card = "是" in msg

        if (amount := monetary.get(event.get_user_id())) < bet_amount * 2:
            # check if money is enough
            await game_start.send(
                f"你只有 {amount} 个碎片，不够分牌下注哦~接下来将按照不分牌处理"
                + gens[latest_message_id].element
            )
            split_card = False

    if split_card:
        second_hand = Hand()
        second_hand.add_card(player_hand.cards.pop())
        player_hand.add_card(channel_shoe_map[event.channel.id].deal())
        second_hand.add_card(channel_shoe_map[event.channel.id].deal())

        for idx, hand in enumerate([player_hand, second_hand]):
            await game_start.send(
                MessageSegment.image(
                    raw=image_to_bytes(
                        renderer.generate_table(dealer_hand, hand, True)
                    ),
                    mime="image/png",
                )
                + f"【第 {idx + 1} 幅牌】\n"
                + "你要“补牌”(h)还是“停牌”(s)呢？"
                + gens[latest_message_id].element
            )
            playing = True
            while playing:
                async for resp in check(timeout=180):
                    if resp is None:
                        monetary.cost(event.get_user_id(), bet_amount * 2, "blackjack")
                        channel_players[event.channel.id].remove(event.get_user_id())
                        await game_start.finish(
                            "时间到了哦，游戏自动结束。但是下注的碎片不会退回给你哦~\n"
                            + gens[latest_message_id].element
                        )
                    else:
                        msg = str(resp.get_message()).strip()
                        latest_message_id = resp.message.id
                        gens[latest_message_id] = PG(resp)

                        action = get_action(msg)
                        if action is None:
                            await game_start.send(
                                "请从“补牌”(h)或“停牌”(s)中选择一项哦"
                                + gens[latest_message_id].element
                            )
                            continue
                        elif action == "h":
                            hand.add_card(channel_shoe_map[event.channel.id].deal())
                            await game_start.send(
                                MessageSegment.image(
                                    raw=image_to_bytes(
                                        renderer.generate_table(dealer_hand, hand, True)
                                    ),
                                    mime="image/png",
                                )
                                + (
                                    "请从“补牌”(h)或“停牌”(s)中选择一项哦"
                                    if hand.value <= 21
                                    else ""
                                )
                                + gens[latest_message_id].element
                            )
                            if hand.value > 21:
                                monetary.cost(
                                    event.get_user_id(), bet_amount, "blackjack"
                                )
                                await game_start.send(
                                    f"你爆牌啦，Kasumi 获胜！扣除你 {bet_amount} 个碎片，你现在还有 {monetary.get(event.get_user_id())} 个碎片"
                                    + gens[latest_message_id].element
                                )
                                playing = False
                                break
                        elif action == "d":
                            await game_start.send(
                                "分牌之后不能双倍下注哦~请重新选择"
                                + gens[latest_message_id].element
                            )
                            continue
                        else:
                            # action == "s"
                            playing = False
                            break

        # Kasumi的回合
        result_messages = Message()
        result_messages += "到 Kasumi 的回合啦！"

        count = 0
        while dealer_hand.value < 17:
            dealer_hand.add_card(channel_shoe_map[event.channel.id].deal())
            count += 1

        if count > 0:
            result_messages += f"Kasumi 一共补了 {count} 张牌" + MessageSegment.image(
                raw=image_to_bytes(renderer.generate_hand(dealer_hand, False)),
                mime="image/png",
            )
        else:
            result_messages += (
                "Kasumi 的点数已经大于等于 17，不需要补牌"
                + MessageSegment.image(
                    raw=image_to_bytes(renderer.generate_hand(dealer_hand, False)),
                    mime="image/png",
                )
            )

        await game_start.send(result_messages + gens[latest_message_id].element)
        result_messages = Message()

        for idx, hand in enumerate([player_hand, second_hand]):
            if hand.value > 21:
                result_messages += f"【第 {idx + 1} 幅牌】你爆牌啦，Kasumi 获胜！刚才已经扣除了你 {bet_amount} 个碎片"
            else:
                if dealer_hand.value > 21:
                    if len(character_ids) > 0:
                        monetary.add(event.get_user_id(), bet_amount * 1.5, "blackjack")
                        result_messages += f"【第 {idx + 1} 幅牌】Kasumi 爆牌，你获胜啦！今天是{'和'.join(get_today_birthday())}的生日，奖励多多！你获得了 {bet_amount} × 1.5 = {bet_amount * 1.5} 个碎片"
                    else:
                        monetary.add(event.get_user_id(), bet_amount, "blackjack")
                        result_messages += f"【第 {idx + 1} 幅牌】Kasumi 爆牌，你获胜啦！获得了 {bet_amount} 个碎片"
                else:
                    if hand.value > dealer_hand.value:
                        if len(character_ids) > 0:
                            monetary.add(
                                event.get_user_id(), bet_amount * 1.5, "blackjack"
                            )
                            result_messages += f"【第 {idx + 1} 幅牌】{hand.value} > {dealer_hand.value}，你获胜啦！今天是{'和'.join(get_today_birthday())}的生日，奖励多多！你获得了 {bet_amount} × 1.5 = {bet_amount * 1.5} 个碎片"
                        else:
                            monetary.add(event.get_user_id(), bet_amount, "blackjack")
                            result_messages += f"【第 {idx + 1} 幅牌】{hand.value} > {dealer_hand.value}，你获胜啦！获得了 {bet_amount} 个碎片"
                    elif hand.value < dealer_hand.value:
                        monetary.cost(event.get_user_id(), bet_amount, "blackjack")
                        result_messages += f"【第 {idx + 1} 幅牌】{hand.value} < {dealer_hand.value}，Kasumi 获胜！扣除你 {bet_amount} 个碎片"
                    else:
                        result_messages += f"【第 {idx + 1} 幅牌】{hand.value} = {dealer_hand.value}，平局！碎片不变"
            result_messages += "\n"
        result_messages += f"你现在有 {monetary.get(event.get_user_id())} 个碎片"

        # 一次性发送所有结果
        channel_players[event.channel.id].remove(event.get_user_id())
        await game_start.send(result_messages + gens[latest_message_id].element)
    else:
        playing = True
        play_round = 0
        await game_start.send(
            init_msg
            + "请从“补牌”(h)，“停牌”(s)或者“双倍”(d)中选择一项操作哦"
            + gens[latest_message_id].element
        )
        while playing:
            play_round += 1
            async for resp in check(timeout=180):
                if resp is None:
                    monetary.cost(event.get_user_id(), bet_amount, "blackjack")
                    channel_players[event.channel.id].remove(event.get_user_id())
                    await game_start.finish(
                        "时间到了哦，游戏自动结束。但是下注的碎片不会退回给你哦~\n"
                        + gens[latest_message_id].element
                    )
                else:
                    msg = str(resp.get_message()).strip()
                    latest_message_id = resp.message.id
                    gens[latest_message_id] = PG(resp)

                    action = get_action(msg)
                    if action is None:
                        await game_start.send(
                            "请从“补牌”(h)，“停牌”(s)"
                            + ("或者“双倍”(d)" if play_round == 1 else "")
                            + "中选择一项操作哦"
                            + gens[latest_message_id].element
                        )
                        continue
                    elif action == "h":
                        player_hand.add_card(channel_shoe_map[event.channel.id].deal())
                        await game_start.send(
                            MessageSegment.image(
                                raw=image_to_bytes(
                                    renderer.generate_table(
                                        dealer_hand,
                                        player_hand,
                                        player_hand.value <= 21,
                                    )
                                ),
                                mime="image/png",
                            )
                            + (
                                "请从“补牌”(h)，“停牌”(s)中选择一项操作哦"
                                if player_hand.value <= 21
                                else ""
                            )
                            + gens[latest_message_id].element
                        )
                        if player_hand.value > 21:
                            monetary.cost(event.get_user_id(), bet_amount, "blackjack")
                            channel_players[event.channel.id].remove(
                                event.get_user_id()
                            )
                            await game_start.finish(
                                f"你爆牌啦，Kasumi 获胜！扣除你 {bet_amount} 个碎片，你现在还有 {monetary.get(event.get_user_id())} 个碎片"
                                + gens[latest_message_id].element
                            )
                    elif action == "s":
                        playing = False
                        break
                    elif action == "d":
                        if play_round == 1:
                            if monetary.get(event.get_user_id()) < bet_amount * 2:
                                await game_start.send(
                                    f"你只有 {monetary.get(event.get_user_id())} 个碎片，不够双倍下注哦~请重新选择"
                                    + gens[latest_message_id].element
                                )
                                continue
                            else:
                                bet_amount *= 2
                                player_hand.add_card(
                                    channel_shoe_map[event.channel.id].deal()
                                )
                                await game_start.send(
                                    MessageSegment.image(
                                        raw=image_to_bytes(
                                            renderer.generate_table(
                                                dealer_hand,
                                                player_hand,
                                                player_hand.value <= 21,
                                            )
                                        ),
                                        mime="image/png",
                                    )
                                    + (
                                        "请从“补牌”(h)，“停牌”(s)中选择一项操作哦"
                                        if player_hand.value <= 21
                                        else ""
                                    )
                                    + gens[latest_message_id].element
                                )
                                if player_hand.value > 21:
                                    monetary.cost(
                                        event.get_user_id(), bet_amount, "blackjack"
                                    )
                                    channel_players[event.channel.id].remove(
                                        event.get_user_id()
                                    )
                                    await game_start.finish(
                                        f"你爆牌啦，Kasumi 获胜！扣除你 {bet_amount} 个碎片，你现在还有 {monetary.get(event.get_user_id())} 个碎片"
                                        + gens[latest_message_id].element
                                    )
                        else:
                            await game_start.send(
                                "不能在非第一轮使用双倍下注哦~请重新选择"
                                + gens[latest_message_id].element
                            )
                            continue

        # Kasumi的回合
        result_messages = Message()
        result_messages += "到 Kasumi 的回合啦！"

        count = 0
        while dealer_hand.value < 17:
            dealer_hand.add_card(channel_shoe_map[event.channel.id].deal())
            count += 1

        if count > 0:
            result_messages += f"Kasumi 一共补了 {count} 张牌" + MessageSegment.image(
                raw=image_to_bytes(renderer.generate_hand(dealer_hand, False)),
                mime="image/png",
            )
        else:
            result_messages += (
                "Kasumi 的点数已经大于等于 17，不需要补牌"
                + MessageSegment.image(
                    raw=image_to_bytes(renderer.generate_hand(dealer_hand, False)),
                    mime="image/png",
                )
            )

        await game_start.send(result_messages + gens[latest_message_id].element)
        result_messages = Message()

        if dealer_hand.value > 21:
            if len(character_ids) > 0:
                monetary.add(event.get_user_id(), bet_amount * 1.5, "blackjack")
                result_messages += f"Kasumi 爆牌，你获胜啦！今天是{'和'.join(get_today_birthday())}的生日，奖励多多！你获得了 {bet_amount} × 1.5 = {bet_amount * 1.5} 个碎片，你现在有 {monetary.get(event.get_user_id())} 个碎片"
            else:
                monetary.add(event.get_user_id(), bet_amount, "blackjack")
                result_messages += f"Kasumi 爆牌，你获胜啦！获得了 {bet_amount} 个碎片，你现在有 {monetary.get(event.get_user_id())} 个碎片"
        else:
            if player_hand.value > dealer_hand.value:
                if len(character_ids) > 0:
                    monetary.add(event.get_user_id(), bet_amount * 1.5, "blackjack")
                    result_messages += f"{player_hand.value} > {dealer_hand.value}，你获胜啦！今天是{'和'.join(get_today_birthday())}的生日，奖励多多！你获得了 {bet_amount} × 1.5 = {bet_amount * 1.5} 个碎片，你现在有 {monetary.get(event.get_user_id())} 个碎片"
                else:
                    monetary.add(event.get_user_id(), bet_amount, "blackjack")
                    result_messages += f"{player_hand.value} > {dealer_hand.value}，你获胜啦！获得了 {bet_amount} 个碎片，你现在有 {monetary.get(event.get_user_id())} 个碎片"
            elif player_hand.value < dealer_hand.value:
                monetary.cost(event.get_user_id(), bet_amount, "blackjack")
                result_messages += f"{player_hand.value} < {dealer_hand.value}，Kasumi 获胜！扣除你 {bet_amount} 个碎片，你现在还有 {monetary.get(event.get_user_id())} 个碎片"
            else:
                result_messages += (
                    f"{player_hand.value} = {dealer_hand.value}，平局！碎片不变"
                )

        # 一次性发送所有结果
        channel_players[event.channel.id].remove(event.get_user_id())
        await game_start.send(result_messages + gens[latest_message_id].element)
