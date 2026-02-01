from __future__ import annotations

from typing import Optional, Tuple

from nonebot.matcher import Matcher
from nonebot_plugin_waiter import Waiter
from nonebot.adapters.satori import Message, MessageEvent, MessageSegment

from utils import image_to_bytes
from utils.passive_generator import generators as gens
from utils.passive_generator import PassiveGenerator as PG

from .. import monetary
from .messages import Messages
from .models import Hand, Card, GameResult
from .session import GameManager, GameSession
from .utils import get_action


def get_card_image(card: Card, renderer) -> MessageSegment:
    """获取牌的图片"""
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
    dealer_hand: Hand,
    channel_id: str,
    latest_message_id: str,
    game_manager: GameManager,
) -> Message:
    """执行庄家回合，返回结果消息"""
    result_messages = Message()
    result_messages += Messages.DEALER_TURN

    count = 0
    while dealer_hand.value < 17:
        dealer_hand.add_card(game_manager.get_shoe(channel_id).deal())
        count += 1

    if count > 0:
        result_messages += Messages.DEALER_DRAWN.format(
            count=count
        ) + MessageSegment.image(
            raw=image_to_bytes(game_manager.renderer.generate_hand(dealer_hand, False)),
            mime="image/jpeg",
        )
    else:
        result_messages += Messages.DEALER_STAND + MessageSegment.image(
            raw=image_to_bytes(game_manager.renderer.generate_hand(dealer_hand, False)),
            mime="image/jpeg",
        )

    return result_messages + gens[latest_message_id].element


def evaluate_hand_result(
    player_hand: Hand,
    dealer_hand: Hand,
    bet_amount: int,
    hand_name: str = "",
    bonus_applied: bool = False,
    actual_winnings: int = 0,
) -> tuple[int, str]:
    """
    评估单手牌的结果
    返回: (奖金金额, 结果文本)
    奖金金额是相对于下注金额的额外收益，不包括本金

    Args:
        bonus_applied: 是否应用了今日首局双倍加成
        actual_winnings: 实际奖金（如果bonus_applied为True，这是双倍后的奖金）
    """
    prefix = f"【{hand_name}】" if hand_name else ""

    if player_hand.value > 21:
        return -bet_amount, prefix + Messages.BUST_LOSE.format(amount=bet_amount)

    if dealer_hand.value > 21:
        if bonus_applied:
            return (
                bet_amount,
                prefix
                + Messages.DEALER_BUST_WIN_BONUS.format(
                    original=bet_amount, amount=actual_winnings
                ),
            )
        return bet_amount, prefix + Messages.DEALER_BUST_WIN.format(amount=bet_amount)

    if player_hand.value > dealer_hand.value:
        if bonus_applied:
            return (
                bet_amount,
                prefix
                + Messages.RESULT_WIN_BONUS.format(
                    player=player_hand.value,
                    dealer=dealer_hand.value,
                    original=bet_amount,
                    amount=actual_winnings,
                ),
            )
        return (
            bet_amount,
            prefix
            + Messages.RESULT_WIN.format(
                player=player_hand.value, dealer=dealer_hand.value, amount=bet_amount
            ),
        )
    if player_hand.value < dealer_hand.value:
        return (
            -bet_amount,
            prefix
            + Messages.RESULT_LOSE.format(
                player=player_hand.value, dealer=dealer_hand.value, amount=bet_amount
            ),
        )
    return (
        0,
        prefix
        + Messages.RESULT_PUSH.format(
            player=player_hand.value, dealer=dealer_hand.value
        ),
    )


async def handle_player_bust(
    user_id: str,
    bet_amount: int,
    latest_message_id: str,
    matcher: Matcher,
    game_manager: GameManager,
) -> None:
    """处理玩家爆牌的情况"""
    game_manager.end_game(user_id, GameResult.BUST, winnings=-bet_amount)
    await matcher.send(
        Messages.BUST_LOSE.format(amount=bet_amount)
        + (
            f"，你现在还有 {monetary.get(user_id)} 个碎片"
            if game_manager.get_split_state(user_id) == 0
            else ""
        )
        + gens[latest_message_id].element
    )


async def handle_surrender(
    user_id: str,
    bet_amount: int,
    latest_message_id: str,
    dealer_hand: Hand,
    player_hand: Hand,
    matcher: Matcher,
    game_manager: GameManager,
) -> None:
    """处理玩家投降的情况"""
    loss_amount = (bet_amount / 2).__ceil__()
    game_manager.end_game(user_id, GameResult.SURRENDER, winnings=-loss_amount)
    await matcher.send(
        MessageSegment.image(
            raw=image_to_bytes(
                game_manager.renderer.generate_table(dealer_hand, player_hand, False)
            ),
            mime="image/jpeg",
        )
        + Messages.SURRENDER_LOSE.format(amount=loss_amount)
        + (
            f"，你现在还有 {monetary.get(user_id)} 个碎片"
            if game_manager.get_split_state(user_id) == 0
            else ""
        )
        + gens[latest_message_id].element
    )


async def play_player_turn(
    player_hand: Hand,
    dealer_hand: Hand,
    bet_amount: int,
    event: MessageEvent,
    latest_message_id: str,
    check: Waiter[MessageEvent],
    matcher: Matcher,
    game_manager: GameManager,
    hand_name: str = "",
    show_initial_message: bool = True,
) -> tuple[str, bool, int]:
    """
    处理玩家回合逻辑
    返回: (最新消息ID, 是否完成游戏(投降/爆牌), 更新后的下注金额)
    """
    play_round = 1
    playing = True

    if show_initial_message:
        if game_manager.get_split_state(event.get_user_id()) > 0:
            prompt = Messages.ACTION_PROMPT_SPLIT.format(hand_name=hand_name)
        else:
            prompt = Messages.ACTION_PROMPT

        await matcher.send(
            MessageSegment.image(
                raw=image_to_bytes(
                    game_manager.renderer.generate_table(dealer_hand, player_hand, True)
                ),
                mime="image/jpeg",
            )
            + prompt
            + gens[latest_message_id].element
        )

    while playing:
        async for resp in check(timeout=180):
            if resp is None:
                bet_amount = game_manager.get_player_bet(event.get_user_id())
                game_manager.end_game(
                    event.get_user_id(), GameResult.TIMEOUT, winnings=-bet_amount
                )
                await matcher.finish(
                    Messages.TIMEOUT_LOSE + gens[latest_message_id].element
                )
            else:
                msg = str(resp.get_message()).strip()
                latest_message_id = resp.message.id
                gens[latest_message_id] = PG(resp)

                action = get_action(msg)
                if action is None:
                    if game_manager.get_split_state(event.get_user_id()) > 0:
                        error_msg = Messages.ACTION_INVALID_SPLIT
                    else:
                        double_part = '"双倍"(d)' if play_round == 1 else ""
                        error_msg = Messages.ACTION_INVALID.format(
                            double_part=double_part
                        )
                    await matcher.send(error_msg + gens[latest_message_id].element)
                    continue

                if action == "h":
                    player_hand.add_card(game_manager.get_shoe(event.channel.id).deal())

                    next_prompt = ""
                    if player_hand.value < 21:
                        next_prompt = Messages.ACTION_HIT_PROMPT
                    elif player_hand.value == 21:
                        next_prompt = ""

                    await matcher.send(
                        MessageSegment.image(
                            raw=image_to_bytes(
                                game_manager.renderer.generate_table(
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
                            game_manager,
                        )
                        return latest_message_id, True, bet_amount
                    if player_hand.value == 21:
                        playing = False
                        break

                elif action == "s":
                    playing = False
                    break

                elif action == "d":
                    if game_manager.get_split_state(event.get_user_id()) > 0:
                        await matcher.send(
                            Messages.DOUBLE_AFTER_SPLIT
                            + gens[latest_message_id].element
                        )
                        continue
                    if play_round != 1:
                        await matcher.send(
                            Messages.DOUBLE_NOT_FIRST + gens[latest_message_id].element
                        )
                        continue

                    if monetary.get(event.get_user_id()) < bet_amount:
                        await matcher.send(
                            Messages.DOUBLE_NOT_ENOUGH.format(
                                amount=monetary.get(event.get_user_id())
                            )
                            + gens[latest_message_id].element
                        )
                        continue

                    monetary.cost(event.get_user_id(), bet_amount, "blackjack")
                    bet_amount *= 2
                    game_manager.set_player_bet(event.get_user_id(), bet_amount)
                    player_hand.add_card(game_manager.get_shoe(event.channel.id).deal())
                    await matcher.send(
                        MessageSegment.image(
                            raw=image_to_bytes(
                                game_manager.renderer.generate_table(
                                    dealer_hand, player_hand, player_hand.value <= 21
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
                            game_manager,
                        )
                        return latest_message_id, True, bet_amount
                    playing = False
                    break

                elif action == "q":
                    await handle_surrender(
                        event.get_user_id(),
                        bet_amount,
                        latest_message_id,
                        dealer_hand,
                        player_hand,
                        matcher,
                        game_manager,
                    )
                    return latest_message_id, True, bet_amount

    return latest_message_id, False, bet_amount


async def get_bet_amount(
    arg_text: str,
    latest_message_id: str,
    check: Waiter[MessageEvent],
    matcher: Matcher,
) -> Tuple[int, str]:
    bet_amount: Optional[int] = None

    try:
        bet_amount = int(arg_text)
    except ValueError:
        bet_amount = None

    if bet_amount is None:
        await matcher.send(Messages.BET_PROMPT + gens[latest_message_id].element)
        resp = await check.wait(timeout=60)
        if resp is None:
            await matcher.finish(Messages.BET_TIMEOUT + gens[latest_message_id].element)
        else:
            gens[resp.message.id] = PG(resp)
            latest_message_id = resp.message.id
            try:
                bet_amount = int(str(resp.get_message()).strip())
            except ValueError:
                await matcher.finish(
                    Messages.BET_INVALID + gens[latest_message_id].element
                )

            if bet_amount <= 0:
                await matcher.finish(
                    Messages.BET_TOO_SMALL + gens[latest_message_id].element
                )

    elif bet_amount <= 0:
        await matcher.finish(Messages.BET_TOO_SMALL + gens[latest_message_id].element)

    return bet_amount, latest_message_id


async def handle_initial_blackjack(
    session: GameSession,
    bet_amount: int,
    latest_message_id: str,
    matcher: Matcher,
    game_manager: GameManager,
) -> bool:
    if session.player_hand.value == 21:
        if session.dealer_hand.value == 21:
            game_manager.end_game(session.user_id, GameResult.PUSH, winnings=0)
            await matcher.finish(
                MessageSegment.image(
                    raw=image_to_bytes(
                        game_manager.renderer.generate_table(
                            session.dealer_hand, session.player_hand, False
                        )
                    ),
                    mime="image/jpeg",
                )
                + Messages.BLACKJACK_PUSH
                + f"你现在有 {monetary.get(session.user_id)} 个碎片"
                + gens[latest_message_id].element
            )
        else:
            blackjack_winnings = int(bet_amount * 1.5)
            actual_winnings, bonus_applied = game_manager.end_game(
                session.user_id,
                GameResult.BLACKJACK,
                winnings=blackjack_winnings,
            )
            if bonus_applied:
                win_msg = Messages.BLACKJACK_WIN_BONUS.format(
                    bet=bet_amount, amount=actual_winnings
                )
            else:
                win_msg = Messages.BLACKJACK_WIN.format(
                    bet=bet_amount, amount=actual_winnings
                )
            await matcher.finish(
                MessageSegment.image(
                    raw=image_to_bytes(
                        game_manager.renderer.generate_table(
                            session.dealer_hand, session.player_hand, False
                        )
                    ),
                    mime="image/jpeg",
                )
                + win_msg
                + f"你现在有 {monetary.get(session.user_id)} 个碎片！"
                + gens[latest_message_id].element
            )
        return True
    return False


async def handle_split_decision(
    session: GameSession,
    bet_amount: int,
    event: MessageEvent,
    latest_message_id: str,
    check: Waiter[MessageEvent],
    matcher: Matcher,
    game_manager: GameManager,
) -> Tuple[bool, int, str]:
    split_card = False

    if (
        session.player_hand.cards[0].get_value()
        == session.player_hand.cards[1].get_value()
    ):
        sentence = Messages.SPLIT_PROMPT
        await matcher.send(
            MessageSegment.image(
                raw=image_to_bytes(
                    game_manager.renderer.generate_table(
                        session.dealer_hand, session.player_hand, True
                    )
                ),
                mime="image/jpeg",
            )
            + sentence
            + Messages.SPLIT_CHOICE
            + gens[latest_message_id].element
        )
        resp = await check.wait(timeout=60)

        if resp is None:
            await matcher.send(Messages.SPLIT_TIMEOUT + gens[latest_message_id].element)
            split_card = False
        else:
            msg = str(resp.get_message()).strip()
            latest_message_id = resp.message.id
            gens[latest_message_id] = PG(resp)

            if msg not in ["是", "否"]:
                await matcher.send(
                    Messages.SPLIT_INVALID + gens[latest_message_id].element
                )
                split_card = False
            else:
                split_card = "是" in msg

        if (amount := monetary.get(event.get_user_id())) < bet_amount:
            await matcher.send(
                Messages.SPLIT_NOT_ENOUGH.format(amount=amount)
                + gens[latest_message_id].element
            )
            split_card = False
        elif split_card:
            monetary.cost(event.get_user_id(), bet_amount, "blackjack")
            game_manager.set_player_bet(event.get_user_id(), bet_amount * 2)
            bet_amount *= 2
            game_manager.set_split_state(event.get_user_id(), 1)

    return split_card, bet_amount, latest_message_id


async def handle_split_game(
    session: GameSession,
    bet_amount: int,
    event: MessageEvent,
    latest_message_id: str,
    check: Waiter[MessageEvent],
    matcher: Matcher,
    game_manager: GameManager,
) -> None:
    second_hand = Hand()
    second_hand.add_card(session.player_hand.cards.pop())
    session.player_hand.add_card(game_manager.get_shoe(event.channel.id).deal())
    second_hand.add_card(game_manager.get_shoe(event.channel.id).deal())
    session.split_hand = second_hand

    game_ended_map = {1: False, 2: False}

    for idx, hand in enumerate([session.player_hand, session.split_hand]):
        if hand.value == 21:
            await matcher.send(
                MessageSegment.image(
                    raw=image_to_bytes(
                        game_manager.renderer.generate_table(
                            session.dealer_hand, hand, True
                        )
                    ),
                    mime="image/jpeg",
                )
                + f"【第 {idx + 1} 幅牌】"
                + gens[latest_message_id].element
            )
        else:
            latest_message_id, game_ended, _ = await play_player_turn(
                hand,
                session.dealer_hand,
                bet_amount // 2,
                event,
                latest_message_id,
                check,
                matcher,
                game_manager,
                hand_name=f"【第 {idx + 1} 幅牌】",
            )
            game_ended_map[idx + 1] = game_ended

    dealer_result = play_dealer_turn(
        session.dealer_hand, event.channel.id, latest_message_id, game_manager
    )
    await matcher.send(dealer_result)
    result_messages = Message()

    total_winnings = 0
    for idx, hand in enumerate([session.player_hand, session.split_hand]):
        winnings, hand_result = evaluate_hand_result(
            hand,
            session.dealer_hand,
            bet_amount // 2,
            f"第 {idx + 1} 幅牌",
        )
        total_winnings += winnings if not game_ended_map[idx + 1] else 0
        result_messages += hand_result + "\n"

    if total_winnings > 0:
        split_result = GameResult.WIN
    elif total_winnings == 0:
        split_result = GameResult.PUSH
    else:
        split_result = GameResult.BUST

    game_manager.set_split_state(event.get_user_id(), 0)

    actual_winnings, bonus_applied = game_manager.end_game(
        event.get_user_id(),
        split_result,
        winnings=total_winnings,
    )
    if bonus_applied:
        result_messages += Messages.SPLIT_TOTAL_BONUS.format(
            original=total_winnings, amount=actual_winnings
        )
    result_messages += f"你现在有 {monetary.get(event.get_user_id())} 个碎片"
    await matcher.send(result_messages + gens[latest_message_id].element)


async def handle_normal_game(
    session: GameSession,
    bet_amount: int,
    event: MessageEvent,
    latest_message_id: str,
    check: Waiter[MessageEvent],
    matcher: Matcher,
    game_manager: GameManager,
) -> None:
    latest_message_id, game_ended, bet_amount = await play_player_turn(
        session.player_hand,
        session.dealer_hand,
        bet_amount,
        event,
        latest_message_id,
        check,
        matcher,
        game_manager,
    )
    if game_ended:
        return

    dealer_result = play_dealer_turn(
        session.dealer_hand, event.channel.id, latest_message_id, game_manager
    )
    await matcher.send(dealer_result)
    result_messages = Message()

    # 先计算原始奖金确定游戏结果类型
    if session.player_hand.value > 21:
        winnings = -bet_amount
        game_result = GameResult.BUST
    elif session.dealer_hand.value > 21:
        winnings = bet_amount
        game_result = GameResult.WIN
    elif session.player_hand.value > session.dealer_hand.value:
        winnings = bet_amount
        game_result = GameResult.WIN
    elif session.player_hand.value < session.dealer_hand.value:
        winnings = -bet_amount
        game_result = GameResult.BUST
    else:
        winnings = 0
        game_result = GameResult.PUSH

    # 结束游戏并获取实际奖金和加成状态
    actual_winnings, bonus_applied = game_manager.end_game(
        event.get_user_id(), game_result, winnings=winnings
    )

    # 使用加成信息生成正确的结果消息
    _, hand_result = evaluate_hand_result(
        session.player_hand,
        session.dealer_hand,
        bet_amount,
        bonus_applied=bonus_applied,
        actual_winnings=actual_winnings,
    )

    result_messages += (
        hand_result + f"，你现在有 {monetary.get(event.get_user_id())} 个碎片"
    )

    await matcher.send(result_messages + gens[latest_message_id].element)
