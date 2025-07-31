from nonebot import on_command
from typing import Optional, Dict
from collections import defaultdict
from nonebot.params import CommandArg
from nonebot_plugin_waiter import waiter
from nonebot.adapters.satori import MessageEvent, Message

from .. import monetary
from utils.passive_generator import generators as gens
from utils.passive_generator import PassiveGenerator as PG

from .utils import get_action
from .models import Shoe, Hand


def init_shoe() -> Shoe:
    shoe = Shoe(6)
    shoe.shuffle()
    return shoe


channel_shoe_map: Dict[str, Shoe] = defaultdict(init_shoe)
reshuffle_threshold = 52 * 6 * 0.25


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


@game_start.handle()
async def handle_start(event: MessageEvent, arg: Optional[Message] = CommandArg()):
    gens[event.message.id] = PG(event)
    latest_message_id = event.message.id

    @waiter(waits=["message"], matcher=game_start, block=False, keep_session=True)
    async def check(event_: MessageEvent) -> MessageEvent:
        return event_

    arg_text = arg.extract_plain_text().strip()
    bet_amount = None

    try:
        bet_amount = int(arg_text)
    except ValueError:
        pass

    if bet_amount is None:
        await game_start.send("你要下注多少碎片呢？" + gens[latest_message_id].element)
        resp = await check.wait(timeout=60)
        if resp is None:
            await game_start.finish(
                "时间到了哦，黑香澄流程已结束" + gens[latest_message_id].element
            )

        else:
            gens[resp.message.id] = PG(resp)
            latest_message_id = resp.message.id
            try:
                bet_amount = int(str(resp.get_message()).strip())
            except ValueError:
                await game_start.finish(
                    "输入的金额不是数字，请重新输入" + gens[latest_message_id].element
                )

            if bet_amount <= 0:
                await game_start.finish(
                    "下注碎片不能少于 0 个哦，请重新输入"
                    + gens[latest_message_id].element
                )

    elif bet_amount <= 0:
        await game_start.finish(
            "下注碎片不能少于 1 个哦，请重新输入" + gens[latest_message_id].element
        )

    if len(channel_shoe_map[event.channel.id].deck) < reshuffle_threshold:
        await game_start.send(
            "牌靴中的牌数太少啦，Kasumi 重新洗下牌哦~" + gens[latest_message_id].element
        )
        channel_shoe_map[event.channel.id] = init_shoe()

    if (amount := monetary.get(event.get_user_id())) < bet_amount:
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

    init_msg = (
        f"Kasumi 的牌：{dealer_hand.cards[0]}，■■■■■\n"
        + f"你的牌：{player_hand.cards[0]}，{player_hand.cards[1]}\n"
        + f"你的点数：{player_hand.value}\n"
    )

    if player_hand.value == 21:
        if dealer_hand.value == 21:
            await game_start.finish(
                f"Kasumi 的牌：{dealer_hand.cards[0]}，{dealer_hand.cards[1]}\n"
                + f"你的牌：{player_hand.cards[0]}，{player_hand.cards[1]}\n"
                + f"你的点数：{player_hand.value}\n"
                + "平局！虽然是 BlackKasumi，但是没有奖励哦~\n"
                + f"你现在有 {monetary.get(event.get_user_id())} 个碎片"
                + gens[latest_message_id].element
            )
        else:
            monetary.add(event.get_user_id(), int(bet_amount * 1.5), "blackjack")
            await game_start.finish(
                f"Kasumi 的牌：{dealer_hand.cards[0]}，{dealer_hand.cards[1]}\n"
                + f"你的牌：{player_hand.cards[0]}，{player_hand.cards[1]}\n"
                + f"你的点数：{player_hand.value}\n"
                + f"BlackKasumi！你获得了 1.5 × {bet_amount} = {int(bet_amount * 1.5)} 个碎片！\n"
                + f"你现在有 {monetary.get(event.get_user_id())} 个碎片！"
                + gens[latest_message_id].element
            )

    if player_hand.cards[0].get_value() == player_hand.cards[1].get_value():
        sentence = (
            f"你有一对 {player_hand.cards[0].rank}，是否要分牌？\n"
            if player_hand.cards[0].rank == player_hand.cards[1].rank
            else f"你有一对相同点数的 {player_hand.cards[0].rank} 和 {player_hand.cards[1].rank}，是否要分牌？\n"
        )
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
                f"【第 {idx + 1} 幅牌】\n"
                + f"Kasumi 的牌：{dealer_hand.cards[0]}，■■■■■\n"
                + f"你的牌：{hand.cards[0]}，{hand.cards[1]}\n"
                + f"你的点数：{hand.value}\n"
                + "你要“补牌”(h)还是“停牌”(s)呢？"
                + gens[latest_message_id].element
            )
            playing = True
            while playing:
                async for resp in check(timeout=180):
                    if resp is None:
                        monetary.cost(event.get_user_id(), bet_amount * 2, "blackjack")
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
                                f"Kasumi 的牌：{dealer_hand.cards[0]}，■■■■■\n"
                                + f"你的牌：{' '.join(map(str, hand.cards))}\n"
                                + f"你的点数：{hand.value}\n"
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
        result_messages = []
        result_messages.append(
            f"到 Kasumi 的回合啦！Kasumi 的牌是 {' '.join(map(str, dealer_hand.cards))}"
        )

        count = 0
        while dealer_hand.value < 17:
            dealer_hand.add_card(channel_shoe_map[event.channel.id].deal())
            count += 1

        if count > 0:
            result_messages.append(
                f"Kasumi 一共补了 {count} 张牌，抽到了 {' '.join(map(str, dealer_hand.cards[-count:]))}\n总点数为 {dealer_hand.value}"
            )
        else:
            result_messages.append("Kasumi 的点数已经大于等于 17，不需要补牌")

        await game_start.send(
            "\n".join(result_messages) + gens[latest_message_id].element
        )
        result_messages = []

        for idx, hand in enumerate([player_hand, second_hand]):
            if hand.value > 21:
                result_messages.append(
                    f"【第 {idx + 1} 幅牌】你爆牌啦，Kasumi 获胜！刚才已经扣除了你 {bet_amount} 个碎片，你现在还有 {monetary.get(event.get_user_id())} 个碎片"
                )
            else:
                if dealer_hand.value > 21:
                    monetary.add(event.get_user_id(), bet_amount, "blackjack")
                    result_messages.append(
                        f"【第 {idx + 1} 幅牌】Kasumi 爆牌，你获胜啦！获得了 {bet_amount} 个碎片，你现在有 {monetary.get(event.get_user_id())} 个碎片"
                    )
                else:
                    if hand.value > dealer_hand.value:
                        monetary.add(event.get_user_id(), bet_amount, "blackjack")
                        result_messages.append(
                            f"【第 {idx + 1} 幅牌】{hand.value} > {dealer_hand.value}，你获胜啦！获得了 {bet_amount} 个碎片，你现在有 {monetary.get(event.get_user_id())} 个碎片"
                        )
                    elif hand.value < dealer_hand.value:
                        monetary.cost(event.get_user_id(), bet_amount, "blackjack")
                        result_messages.append(
                            f"【第 {idx + 1} 幅牌】{hand.value} < {dealer_hand.value}，Kasumi 获胜！扣除你 {bet_amount} 个碎片，你现在还有 {monetary.get(event.get_user_id())} 个碎片"
                        )
                    else:
                        result_messages.append(
                            f"【第 {idx + 1} 幅牌】{hand.value} = {dealer_hand.value}，平局！碎片不变"
                        )

        # 一次性发送所有结果
        await game_start.send(
            "\n".join(result_messages) + gens[latest_message_id].element
        )
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
                            f"Kasumi 的牌：{dealer_hand.cards[0]}，■■■■■\n"
                            + f"你的牌：{' '.join(map(str, player_hand.cards))}\n"
                            + f"你的点数：{player_hand.value}\n"
                            + (
                                "请从“补牌”(h)，“停牌”(s)中选择一项操作哦"
                                if player_hand.value <= 21
                                else ""
                            )
                            + gens[latest_message_id].element
                        )
                        if player_hand.value > 21:
                            monetary.cost(event.get_user_id(), bet_amount, "blackjack")
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
                                    f"Kasumi 的牌：{dealer_hand.cards[0]}，■■■■■\n"
                                    + f"你的牌：{' '.join(map(str, player_hand.cards))}\n"
                                    + f"你的点数：{player_hand.value}\n"
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
        result_messages = []
        result_messages.append(
            f"到 Kasumi 的回合啦！Kasumi 的牌是 {' '.join(map(str, dealer_hand.cards))}"
        )

        count = 0
        while dealer_hand.value < 17:
            dealer_hand.add_card(channel_shoe_map[event.channel.id].deal())
            count += 1

        if count > 0:
            result_messages.append(
                f"Kasumi 一共补了 {count} 张牌，抽到了 {' '.join(map(str, dealer_hand.cards[-count:]))}\n总点数为 {dealer_hand.value}"
            )
        else:
            result_messages.append("Kasumi 的点数已经大于等于 17，不需要补牌")

        await game_start.send(
            "\n".join(result_messages) + gens[latest_message_id].element
        )
        result_messages = []

        if dealer_hand.value > 21:
            monetary.add(event.get_user_id(), bet_amount, "blackjack")
            result_messages.append(
                f"Kasumi 爆牌，你获胜啦！获得了 {bet_amount} 个碎片，你现在有 {monetary.get(event.get_user_id())} 个碎片"
            )
        else:
            if player_hand.value > dealer_hand.value:
                monetary.add(event.get_user_id(), bet_amount, "blackjack")
                result_messages.append(
                    f"{player_hand.value} > {dealer_hand.value}，你获胜啦！获得了 {bet_amount} 个碎片，你现在有 {monetary.get(event.get_user_id())} 个碎片"
                )
            elif player_hand.value < dealer_hand.value:
                monetary.cost(event.get_user_id(), bet_amount, "blackjack")
                result_messages.append(
                    f"{player_hand.value} < {dealer_hand.value}，Kasumi 获胜！扣除你 {bet_amount} 个碎片，你现在还有 {monetary.get(event.get_user_id())} 个碎片"
                )
            else:
                result_messages.append(
                    f"{player_hand.value} = {dealer_hand.value}，平局！碎片不变"
                )

        # 一次性发送所有结果
        await game_start.send(
            "\n".join(result_messages) + gens[latest_message_id].element
        )
