import cv2
import json
from pathlib import Path
from nonebot.log import logger
from collections import defaultdict
from nonebot.params import CommandArg
from typing import Optional, Dict, Set
from nonebot.exception import MatcherException
from nonebot import on_command, require, get_driver
from nonebot.adapters.satori import MessageEvent, Message, MessageSegment

require("cck")  # for card images
require("nonebot_plugin_waiter")
require("nonebot_plugin_localstore")

from nonebot_plugin_waiter import waiter  # noqa: E402

from .. import monetary  # noqa: E402
from ..cck import card_manager  # noqa: E402
from utils import image_to_bytes  # noqa: E402
from utils.passive_generator import generators as gens  # noqa: E402
from utils.passive_generator import PassiveGenerator as PG  # noqa: E402

from .utils import get_action  # noqa: E402
from .database import init_database  # noqa: E402
from .render import BlackjackRenderer  # noqa: E402
from .game_service import BlackjackGameService  # noqa: E402
from .models import Shoe, Hand, Card, GameResult  # noqa: E402
from .stats_service import get_blackjack_stats, create_win_loss_chart  # noqa: E402


HELP_MESSAGE = MessageSegment.image(
    raw=Path("plugins/blackjack/recourses/instruction.png").read_bytes(),
    mime="image/png",
)


def init_shoe() -> Shoe:
    shoe = Shoe(6)
    shoe.shuffle()
    return shoe


def not_in_game(event: MessageEvent) -> bool:
    return event.get_user_id() not in active_players


def start_player_game(user_id: str, bet_amount: int) -> bool:
    """
    开始玩家游戏，扣除下注金额
    返回是否成功开始
    """
    if user_id in active_players:
        return False

    if monetary.get(user_id) < bet_amount:
        return False

    # 扣除下注金额
    monetary.cost(user_id, bet_amount, "blackjack")

    # 添加到活跃玩家列表
    active_players.add(user_id)
    player_bets[user_id] = bet_amount

    return True


def end_player_game(
    user_id: str, result: GameResult, winnings: int = 0, is_split: bool = False
) -> None:
    """
    结束玩家游戏，处理奖金，并记录到数据库

    Args:
        user_id: 玩家ID
        result: 游戏结果（GameResult枚举）
        winnings: 玩家净收益（不包括本金，可为负）
        is_split: 是否为分牌游戏
    """
    if user_id not in active_players:
        return

    bet_amount = player_bets.get(user_id, 0)
    total_return = bet_amount + winnings

    # 如果有返还金额，添加到玩家账户
    if total_return > 0:
        monetary.add(user_id, total_return, "blackjack")

    # 记录游戏到数据库
    BlackjackGameService.record_game(
        user_id=user_id,
        bet_amount=bet_amount,
        result=result,
        winnings=winnings,
        is_split=is_split,
    )

    # 清理玩家状态
    active_players.discard(user_id)
    player_bets.pop(user_id, None)


def refund_player_bet(user_id: str) -> None:
    """
    退还玩家下注金额（用于错误处理）
    """
    if user_id not in active_players:
        return

    bet_amount = player_bets.get(user_id, 0)
    if bet_amount > 0:
        monetary.add(user_id, bet_amount, "blackjack")

    # 清理玩家状态
    active_players.discard(user_id)
    player_bets.pop(user_id, None)


channel_shoe_map: Dict[str, Shoe] = defaultdict(init_shoe)
active_players: Set[str] = set()  # 全局跟踪正在游戏中的玩家
player_bets: Dict[str, int] = {}  # 跟踪每个玩家的下注金额
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
    rule=not_in_game,
)
game_stats = on_command(
    "黑香澄统计",
    aliases={
        "bkstats",
        "bjstats",
        "bk统计",
        "bj统计",
        "bks",
        "bjs",
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
            mime="image/jpeg",
        )

    image, _get_image = renderer.generate_card(
        card.rank, card.suit, ace_value=ace_value
    )
    card._get_image = _get_image
    return MessageSegment.image(
        raw=image_to_bytes(image),
        mime="image/jpeg",
    )


def play_dealer_turn(
    dealer_hand: Hand, channel_id: str, latest_message_id: str
) -> Message:
    """执行庄家回合，返回结果消息"""
    result_messages = Message()
    result_messages += "到 Kasumi 的回合啦！"

    count = 0
    while dealer_hand.value < 17:
        dealer_hand.add_card(channel_shoe_map[channel_id].deal())
        count += 1

    if count > 0:
        result_messages += f"Kasumi 一共补了 {count} 张牌" + MessageSegment.image(
            raw=image_to_bytes(renderer.generate_hand(dealer_hand, False)),
            mime="image/jpeg",
        )
    else:
        result_messages += (
            "Kasumi 的点数已经大于等于 17，不需要补牌"
            + MessageSegment.image(
                raw=image_to_bytes(renderer.generate_hand(dealer_hand, False)),
                mime="image/jpeg",
            )
        )

    return result_messages + gens[latest_message_id].element


def evaluate_hand_result(
    player_hand: Hand,
    dealer_hand: Hand,
    bet_amount: int,
    hand_name: str = "",
) -> tuple[int, str]:
    """
    评估单手牌的结果
    返回: (奖金金额, 结果文本)
    奖金金额是相对于下注金额的额外收益，不包括本金
    """
    prefix = f"【{hand_name}】" if hand_name else ""

    if player_hand.value > 21:
        # 玩家爆牌，输掉下注金额
        return -bet_amount, f"{prefix}你爆牌啦，Kasumi 获胜！输掉了 {bet_amount} 个碎片"

    if dealer_hand.value > 21:
        # 庄家爆牌，玩家赢得下注金额
        return bet_amount, f"{prefix}Kasumi 爆牌，你获胜啦！赢得了 {bet_amount} 个碎片"

    if player_hand.value > dealer_hand.value:
        # 玩家获胜，赢得下注金额
        return (
            bet_amount,
            f"{prefix}{player_hand.value} > {dealer_hand.value}，你获胜啦！赢得了 {bet_amount} 个碎片",
        )
    elif player_hand.value < dealer_hand.value:
        # 玩家失败，输掉下注金额
        return (
            -bet_amount,
            f"{prefix}{player_hand.value} < {dealer_hand.value}，Kasumi 获胜！输掉了 {bet_amount} 个碎片",
        )
    else:
        # 平局，返还下注金额
        return (
            0,
            f"{prefix}{player_hand.value} = {dealer_hand.value}，平局！下注金额返还",
        )


async def handle_player_bust(
    user_id: str, bet_amount: int, latest_message_id: str, matcher
) -> None:
    """处理玩家爆牌的情况"""
    # 玩家爆牌，输掉下注金额
    end_player_game(user_id, GameResult.BUST, winnings=0)
    await matcher.finish(
        f"你爆牌啦，Kasumi 获胜！输掉了 {bet_amount} 个碎片，你现在还有 {monetary.get(user_id)} 个碎片"
        + gens[latest_message_id].element
    )


async def handle_surrender(
    user_id: str,
    bet_amount: int,
    latest_message_id: str,
    dealer_hand: Hand,
    player_hand: Hand,
    matcher,
) -> None:
    """处理玩家投降的情况"""
    # 投降损失一半下注金额
    loss_amount = (bet_amount / 2).__ceil__()
    end_player_game(user_id, GameResult.SURRENDER, winnings=-loss_amount)
    await matcher.finish(
        MessageSegment.image(
            raw=image_to_bytes(
                renderer.generate_table(dealer_hand, player_hand, False)
            ),
            mime="image/jpeg",
        )
        + f"你投降啦，Kasumi 获胜！损失了 {loss_amount} 个碎片，你现在还有 {monetary.get(user_id)} 个碎片"
        + gens[latest_message_id].element
    )


async def play_player_turn(
    player_hand: Hand,
    dealer_hand: Hand,
    bet_amount: int,
    event: MessageEvent,
    latest_message_id: str,
    check,
    matcher,
    is_split: bool = False,
    hand_name: str = "",
    show_initial_message: bool = True,
) -> tuple[str, bool, int]:
    """
    处理玩家回合逻辑
    返回: (最新消息ID, 是否完成游戏(投降/爆牌), 更新后的下注金额)
    """
    play_round = 1
    playing = True

    # 初始提示消息
    if show_initial_message:
        if is_split:
            prompt = f'{hand_name}\n你要"补牌"(h)，"停牌"(s)还是"投降"(q)呢？'
        else:
            prompt = '请从"补牌"(h)，"停牌"(s)，"双倍"(d)或者"投降"(q)中选择一项操作哦'

        await matcher.send(
            MessageSegment.image(
                raw=image_to_bytes(
                    renderer.generate_table(dealer_hand, player_hand, True)
                ),
                mime="image/jpeg",
            )
            + prompt
            + gens[latest_message_id].element
        )

    while playing:
        async for resp in check(timeout=180):
            if resp is None:
                # 超时处理 - 玩家失败，输掉下注金额
                bet_amount = player_bets.get(event.get_user_id(), 0)
                end_player_game(
                    event.get_user_id(), GameResult.TIMEOUT, winnings=-bet_amount
                )
                await matcher.finish(
                    "时间到了哦，游戏自动结束。下注的碎片已没收哦~\n"
                    + gens[latest_message_id].element
                )
            else:
                msg = str(resp.get_message()).strip()
                latest_message_id = resp.message.id
                gens[latest_message_id] = PG(resp)

                action = get_action(msg)
                if action is None:
                    # 无效输入
                    if is_split:
                        error_msg = '请从"补牌"(h)，"停牌"(s)或"投降"(q)中选择一项哦'
                    else:
                        error_msg = (
                            '请从"补牌"(h)，"停牌"(s)'
                            + ('"双倍"(d)' if play_round == 1 else "")
                            + '或者"投降"(q)中选择一项操作哦'
                        )
                    await matcher.send(error_msg + gens[latest_message_id].element)
                    continue

                elif action == "h":
                    # 补牌
                    player_hand.add_card(channel_shoe_map[event.channel.id].deal())

                    next_prompt = ""
                    if player_hand.value < 21:
                        if is_split:
                            next_prompt = (
                                '请从"补牌"(h)，"停牌"(s)或"投降"(q)中选择一项哦'
                            )
                        else:
                            next_prompt = (
                                '请从"补牌"(h)，"停牌"(s)或"投降"(q)中选择一项操作哦'
                            )
                    elif player_hand.value == 21:
                        next_prompt = ""  # 不显示提示，因为会自动停牌

                    await matcher.send(
                        MessageSegment.image(
                            raw=image_to_bytes(
                                renderer.generate_table(
                                    dealer_hand, player_hand, player_hand.value <= 21
                                )
                            ),
                            mime="image/jpeg",
                        )
                        + next_prompt
                        + gens[latest_message_id].element
                    )

                    play_round += 1
                    if player_hand.value > 21:
                        await handle_player_bust(
                            event.get_user_id(),
                            bet_amount,
                            latest_message_id,
                            matcher,
                        )
                        return latest_message_id, True, bet_amount  # 游戏结束
                    elif player_hand.value == 21:
                        playing = False
                        break

                elif action == "s":
                    # 停牌
                    playing = False
                    break

                elif action == "d":
                    # 双倍下注
                    if is_split:
                        await matcher.send(
                            "分牌之后不能双倍下注哦~请重新选择"
                            + gens[latest_message_id].element
                        )
                        continue
                    elif play_round != 1:
                        await matcher.send(
                            "不能在非第一轮使用双倍下注哦~请重新选择"
                            + gens[latest_message_id].element
                        )
                        continue
                    else:
                        if monetary.get(event.get_user_id()) < bet_amount * 2:
                            await matcher.send(
                                f"你只有 {monetary.get(event.get_user_id())} 个碎片，不够双倍下注哦~请重新选择"
                                + gens[latest_message_id].element
                            )
                            continue
                        else:
                            # 执行双倍下注
                            bet_amount *= 2
                            player_hand.add_card(
                                channel_shoe_map[event.channel.id].deal()
                            )
                            await matcher.send(
                                MessageSegment.image(
                                    raw=image_to_bytes(
                                        renderer.generate_table(
                                            dealer_hand,
                                            player_hand,
                                            player_hand.value <= 21,
                                        )
                                    ),
                                    mime="image/jpeg",
                                )
                                + gens[latest_message_id].element
                            )

                            if player_hand.value > 21:
                                await handle_player_bust(
                                    event.get_user_id(),
                                    bet_amount,
                                    latest_message_id,
                                    matcher,
                                )
                                return latest_message_id, True, bet_amount  # 游戏结束
                            else:
                                playing = False
                                break

                elif action == "q":
                    # 投降
                    await handle_surrender(
                        event.get_user_id(),
                        bet_amount,
                        latest_message_id,
                        dealer_hand,
                        player_hand,
                        matcher,
                    )
                    return latest_message_id, True, bet_amount  # 游戏结束

    return latest_message_id, False, bet_amount  # 继续游戏


@get_driver().on_startup
async def init_blackjack():
    global renderer

    # Initialize database
    init_database()

    # Initialize renderer
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


@get_driver().on_shutdown
async def shutdown_blackjack():
    # 返还正在进行游戏中的玩家碎片
    logger.info("返还正在进行游戏中的玩家碎片")
    for user_id in active_players.copy():
        refund_player_bet(user_id)


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

    try:
        bet_amount = None

        try:
            bet_amount = int(arg_text)
        except ValueError:
            pass

        if bet_amount is None:
            await game_start.send(
                "你要下注多少碎片呢？" + gens[latest_message_id].element
            )
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
                        "输入的金额不是数字，请重新输入"
                        + gens[latest_message_id].element
                    )

                if bet_amount <= 0:
                    await game_start.finish(
                        "下注碎片不能少于 1 个哦，请重新输入"
                        + gens[latest_message_id].element
                    )

        elif bet_amount <= 0:
            await game_start.finish(
                "下注碎片不能少于 1 个哦，请重新输入" + gens[latest_message_id].element
            )

        # 尝试开始游戏（包含下注金额检查和扣除）
        if not start_player_game(event.get_user_id(), bet_amount):
            await game_start.finish(
                f"你只有 {monetary.get(event.get_user_id())} 个碎片，不够下注哦~"
                + gens[latest_message_id].element
            )

        if len(channel_shoe_map[event.channel.id].deck) < reshuffle_threshold:
            await game_start.send(
                "牌靴中的牌数太少啦，Kasumi 重新洗下牌哦~"
                + gens[latest_message_id].element
            )
            channel_shoe_map[event.channel.id] = init_shoe()

        player_hand = Hand()
        dealer_hand = Hand()
        split_card = False

        player_hand.add_card(channel_shoe_map[event.channel.id].deal())
        dealer_hand.add_card(channel_shoe_map[event.channel.id].deal())
        player_hand.add_card(channel_shoe_map[event.channel.id].deal())
        dealer_hand.add_card(channel_shoe_map[event.channel.id].deal())

        init_msg = MessageSegment.image(
            raw=image_to_bytes(renderer.generate_table(dealer_hand, player_hand, True)),
            mime="image/jpeg",
        )

        if player_hand.value == 21:
            if dealer_hand.value == 21:
                # 平局，返还下注金额
                end_player_game(event.get_user_id(), GameResult.PUSH, winnings=0)
                await game_start.finish(
                    MessageSegment.image(
                        raw=image_to_bytes(
                            renderer.generate_table(dealer_hand, player_hand, False)
                        ),
                        mime="image/jpeg",
                    )
                    + "平局！虽然是 BlackKasumi，但是没有奖励哦~\n"
                    + f"你现在有 {monetary.get(event.get_user_id())} 个碎片"
                    + gens[latest_message_id].element
                )
            else:
                # BlackJack，赢得1.5倍下注金额
                blackjack_winnings = int(bet_amount * 1.5)
                end_player_game(
                    event.get_user_id(),
                    GameResult.BLACKJACK,
                    winnings=blackjack_winnings,
                )
                await game_start.finish(
                    MessageSegment.image(
                        raw=image_to_bytes(
                            renderer.generate_table(dealer_hand, player_hand, False)
                        ),
                        mime="image/jpeg",
                    )
                    + f"BlackKasumi！你赢得了 1.5 × {bet_amount} = {blackjack_winnings} 个碎片！\n"
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
                        "听不懂喵，就当你不想分牌了吧~"
                        + gens[latest_message_id].element
                    )
                    split_card = False
                else:
                    split_card = "是" in msg

            if (amount := monetary.get(event.get_user_id())) < bet_amount:
                # 分牌需要额外的下注金额
                await game_start.send(
                    f"你只有 {amount} 个碎片，不够分牌的额外下注哦~接下来将按照不分牌处理"
                    + gens[latest_message_id].element
                )
                split_card = False
            elif split_card:
                # 扣除分牌的额外下注金额
                monetary.cost(event.get_user_id(), bet_amount, "blackjack")
                # 更新玩家下注记录（现在是双倍下注）
                player_bets[event.get_user_id()] = bet_amount * 2

        if split_card:
            second_hand = Hand()
            second_hand.add_card(player_hand.cards.pop())
            player_hand.add_card(channel_shoe_map[event.channel.id].deal())
            second_hand.add_card(channel_shoe_map[event.channel.id].deal())

            for idx, hand in enumerate([player_hand, second_hand]):
                latest_message_id, game_ended, _ = await play_player_turn(
                    hand,
                    dealer_hand,
                    bet_amount,
                    event,
                    latest_message_id,
                    check,
                    game_start,
                    is_split=True,
                    hand_name=f"【第 {idx + 1} 幅牌】",
                )
                if game_ended:
                    return  # 游戏已结束（投降或爆牌）

            # Kasumi的回合
            dealer_result = play_dealer_turn(
                dealer_hand, event.channel.id, latest_message_id
            )
            await game_start.send(dealer_result)
            result_messages = Message()

            total_winnings = 0
            for idx, hand in enumerate([player_hand, second_hand]):
                winnings, hand_result = evaluate_hand_result(
                    hand,
                    dealer_hand,
                    bet_amount,
                    f"第 {idx + 1} 幅牌",
                )
                total_winnings += winnings
                result_messages += hand_result + "\n"

            # 处理总的输赢，根据总收益确定结果
            if total_winnings > 0:
                split_result = GameResult.WIN
            elif total_winnings == 0:
                split_result = GameResult.PUSH
            else:
                split_result = GameResult.BUST  # 或其他失败结果

            end_player_game(
                event.get_user_id(),
                split_result,
                winnings=total_winnings,
                is_split=True,
            )
            result_messages += f"你现在有 {monetary.get(event.get_user_id())} 个碎片"

            # 一次性发送所有结果
            await game_start.send(result_messages + gens[latest_message_id].element)
        else:
            latest_message_id, game_ended, bet_amount = await play_player_turn(
                player_hand,
                dealer_hand,
                bet_amount,
                event,
                latest_message_id,
                check,
                game_start,
                is_split=False,
            )
            if game_ended:
                return  # 游戏已结束（投降或爆牌）
            # Kasumi的回合
            dealer_result = play_dealer_turn(
                dealer_hand, event.channel.id, latest_message_id
            )
            await game_start.send(dealer_result)
            result_messages = Message()

            winnings, hand_result = evaluate_hand_result(
                player_hand, dealer_hand, bet_amount
            )

            # 处理输赢，根据结果确定游戏结果
            if winnings > 0:
                game_result = GameResult.WIN
            elif winnings == 0:
                game_result = GameResult.PUSH
            else:
                game_result = GameResult.BUST  # 或其他失败结果

            end_player_game(event.get_user_id(), game_result, winnings=winnings)
            result_messages += (
                hand_result + f"，你现在有 {monetary.get(event.get_user_id())} 个碎片"
            )

            # 一次性发送所有结果
            await game_start.send(result_messages + gens[latest_message_id].element)
    except MatcherException:
        raise
    except Exception as e:
        # 发生错误时退还下注金额
        refund_player_bet(event.get_user_id())
        logger.error("Blackjack error: " + str(e), exc_info=True)
        await game_start.finish(
            "发生意外错误！下注已退回给你，再试一次吧？"
            + gens[latest_message_id].element
        )


@game_stats.handle()
async def handle_stats(event: MessageEvent):
    """处理黑香澄统计信息查询"""
    user_id = event.get_user_id()
    gens[event.message.id] = PG(event)

    try:
        # 获取玩家的blackjack统计数据
        stats = get_blackjack_stats(user_id)

        if stats.total_games == 0:
            await game_stats.finish(
                "你还没有玩过黑香澄游戏哦，快来试试吧！"
                + gens[event.message.id].element
            )

        # 构建统计信息文本
        stats_text = f"""🎴 黑香澄游戏统计
📊 {stats.total_games}局 | 胜{stats.wins} 负{stats.losses} | 胜率{stats.win_rate:.1%}
💰 投入{stats.total_wagered} | 得{stats.total_won} 失{stats.total_lost} | 净收益{stats.net_profit:+d}
🎰 平均赌注{stats.avg_bet:.1f} | 平均赢{stats.avg_win:.1f} | 平均输{stats.avg_loss:.1f}
🏆 最高赢{stats.biggest_win} | 最高输{stats.biggest_loss}"""

        # 尝试生成图表
        chart_bytes = create_win_loss_chart(stats)

        # 发送统计信息
        response_message = MessageSegment.text(stats_text)

        if chart_bytes:
            # 如果成功生成图表，添加图表
            response_message += MessageSegment.image(raw=chart_bytes, mime="image/png")
        else:
            response_message += MessageSegment.text("\n📊 图表生成失败")

        response_message += gens[event.message.id].element
        await game_stats.finish(response_message)

    except MatcherException:
        raise
    except Exception as e:
        logger.error(f"获取blackjack统计信息时出错: {e}", exc_info=True)
        await game_stats.finish(
            "获取统计信息时出现错误，请稍后再试" + gens[event.message.id].element
        )
