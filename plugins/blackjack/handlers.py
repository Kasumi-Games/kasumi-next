from typing import Tuple
from typing import Optional

from nonebot import require
from nonebot.matcher import Matcher
from nonebot_plugin_waiter import Waiter
from nonebot.adapters.satori import Message
from nonebot.adapters.satori import MessageEvent
from nonebot.adapters.satori import MessageSegment

from utils import image_to_bytes
from utils.images import render_image_value
from plugins.render import PlayerIdentity
from utils.passive_generator import PassiveGenerator as PG
from utils.passive_generator import generators as gens

from .. import monetary
from .utils import get_action
from .models import Hand
from .models import GameResult
from .session import GameManager
from .session import GameSession
from .messages import Messages
from .rules import can_surrender

require("daily_task")

from ..daily_task import check_progress  # noqa: E402


async def _render_jpeg_segment(renderer, /, *args, **kwargs) -> MessageSegment:
    raw = await render_image_value(renderer, image_to_bytes, *args, **kwargs)
    return MessageSegment.image(raw=raw, mime="image/jpeg")


def _bet_detail(bet_amount: int) -> str:
    """The identity-strip detail text for a bet."""
    return f"押注 {bet_amount} Pt"


async def play_dealer_turn(
    dealer_hand: Hand,
    channel_id: str,
    user_id: str,
    latest_message_id: str,
    game_manager: GameManager,
    identity: Optional[PlayerIdentity] = None,
    detail: Optional[str] = None,
) -> Message:
    """执行庄家回合，返回结果消息"""
    result_messages = Message()
    result_messages += Messages.DEALER_TURN

    count = 0
    while dealer_hand.value < 17:
        dealer_hand.add_card(game_manager.get_shoe(channel_id).deal())
        count += 1

    hand_image = await _render_jpeg_segment(
        game_manager.renderer_for(user_id).generate_hand,
        dealer_hand,
        False,
        identity=identity,
        detail=detail,
    )
    if count > 0:
        result_messages += Messages.DEALER_DRAWN.format(count=count) + hand_image
    else:
        result_messages += Messages.DEALER_STAND + hand_image

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
        return -bet_amount, prefix + Messages.BUST_LOSE.format(amount=bet_amount)

    if dealer_hand.value > 21:
        return bet_amount, prefix + Messages.DEALER_BUST_WIN.format(amount=bet_amount)

    if player_hand.value > dealer_hand.value:
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
            f"，你现在还有 {monetary.get(user_id)} 个Pt"
            if game_manager.get_split_state(user_id) == 0
            else ""
        )
        + gens[latest_message_id].element,
        referrer=gens[latest_message_id].event.referrer,
    )


async def handle_surrender(
    user_id: str,
    bet_amount: int,
    latest_message_id: str,
    dealer_hand: Hand,
    player_hand: Hand,
    matcher: Matcher,
    game_manager: GameManager,
    identity: Optional[PlayerIdentity] = None,
) -> None:
    """处理玩家投降的情况"""
    renderer = game_manager.renderer_for(user_id)
    loss_amount = (bet_amount / 2).__ceil__()
    game_manager.end_game(user_id, GameResult.SURRENDER, winnings=-loss_amount)
    await matcher.send(
        await _render_jpeg_segment(
            renderer.generate_table,
            dealer_hand,
            player_hand,
            False,
            identity=identity,
            detail=_bet_detail(bet_amount),
        )
        + Messages.SURRENDER_LOSE.format(amount=loss_amount)
        + (
            f"，你现在还有 {monetary.get(user_id)} 个Pt"
            if game_manager.get_split_state(user_id) == 0
            else ""
        )
        + gens[latest_message_id].element,
        referrer=gens[latest_message_id].event.referrer,
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
    identity: Optional[PlayerIdentity] = None,
) -> tuple[str, bool, int]:
    """
    处理玩家回合逻辑
    返回: (最新消息ID, 是否完成游戏(投降/爆牌), 更新后的下注金额)
    """
    play_round = 1
    playing = True
    renderer = game_manager.renderer_for(event.get_user_id())

    if show_initial_message:
        if game_manager.get_split_state(event.get_user_id()) > 0:
            prompt = Messages.ACTION_PROMPT_SPLIT.format(hand_name=hand_name)
        else:
            prompt = Messages.ACTION_PROMPT

        await matcher.send(
            await _render_jpeg_segment(
                renderer.generate_table,
                dealer_hand,
                player_hand,
                True,
                identity=identity,
                detail=_bet_detail(bet_amount),
            )
            + prompt
            + gens[latest_message_id].element,
            referrer=gens[latest_message_id].event.referrer,
        )

    while playing:
        async for resp in check(timeout=180):
            if resp is None:
                bet_amount = game_manager.get_player_bet(event.get_user_id())
                game_manager.end_game(
                    event.get_user_id(), GameResult.TIMEOUT, winnings=-bet_amount
                )
                await matcher.finish(
                    Messages.TIMEOUT_LOSE + gens[latest_message_id].element,
                    referrer=gens[latest_message_id].event.referrer,
                )
            else:
                msg = str(resp.get_message()).strip()
                latest_message_id = resp.message.id
                gens[latest_message_id] = PG(resp)

                action = get_action(msg)
                if action is None:
                    if play_round > 1:
                        error_msg = Messages.ACTION_INVALID_AFTER_HIT
                    elif game_manager.get_split_state(event.get_user_id()) > 0:
                        error_msg = Messages.ACTION_INVALID_SPLIT
                    else:
                        double_part = '"双倍"(d)' if play_round == 1 else ""
                        error_msg = Messages.ACTION_INVALID.format(
                            double_part=double_part
                        )
                    await matcher.send(
                        error_msg + gens[latest_message_id].element,
                        referrer=gens[latest_message_id].event.referrer,
                    )
                    continue

                if action == "h":
                    player_hand.add_card(game_manager.get_shoe(event.channel.id).deal())

                    next_prompt = ""
                    if player_hand.value < 21:
                        next_prompt = Messages.ACTION_HIT_PROMPT
                    elif player_hand.value == 21:
                        next_prompt = ""

                    await matcher.send(
                        await _render_jpeg_segment(
                            renderer.generate_table,
                            dealer_hand,
                            player_hand,
                            player_hand.value <= 21,
                            identity=identity,
                            detail=_bet_detail(bet_amount),
                        )
                        + next_prompt
                        + gens[latest_message_id].element,
                        referrer=gens[latest_message_id].event.referrer,
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
                            + gens[latest_message_id].element,
                            referrer=gens[latest_message_id].event.referrer,
                        )
                        continue
                    if play_round != 1:
                        await matcher.send(
                            Messages.DOUBLE_NOT_FIRST + gens[latest_message_id].element,
                            referrer=gens[latest_message_id].event.referrer,
                        )
                        continue

                    if monetary.get(event.get_user_id()) < bet_amount:
                        await matcher.send(
                            Messages.DOUBLE_NOT_ENOUGH.format(
                                amount=monetary.get(event.get_user_id())
                            )
                            + gens[latest_message_id].element,
                            referrer=gens[latest_message_id].event.referrer,
                        )
                        continue

                    monetary.cost(event.get_user_id(), bet_amount, "blackjack")
                    bet_amount *= 2
                    game_manager.set_player_bet(event.get_user_id(), bet_amount)
                    player_hand.add_card(game_manager.get_shoe(event.channel.id).deal())
                    await matcher.send(
                        await _render_jpeg_segment(
                            renderer.generate_table,
                            dealer_hand,
                            player_hand,
                            player_hand.value <= 21,
                            identity=identity,
                            detail=_bet_detail(bet_amount),
                        )
                        + gens[latest_message_id].element,
                        referrer=gens[latest_message_id].event.referrer,
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
                    if not can_surrender(play_round):
                        await matcher.send(
                            Messages.SURRENDER_NOT_FIRST
                            + gens[latest_message_id].element,
                            referrer=gens[latest_message_id].event.referrer,
                        )
                        continue
                    await handle_surrender(
                        event.get_user_id(),
                        bet_amount,
                        latest_message_id,
                        dealer_hand,
                        player_hand,
                        matcher,
                        game_manager,
                        identity=identity,
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
        await matcher.send(
            Messages.BET_PROMPT + gens[latest_message_id].element,
            referrer=gens[latest_message_id].event.referrer,
        )
        resp = await check.wait(timeout=60)
        if resp is None:
            await matcher.finish(
                Messages.BET_TIMEOUT + gens[latest_message_id].element,
                referrer=gens[latest_message_id].event.referrer,
            )
        else:
            gens[resp.message.id] = PG(resp)
            latest_message_id = resp.message.id
            try:
                bet_amount = int(str(resp.get_message()).strip())
            except ValueError:
                await matcher.finish(
                    Messages.BET_INVALID + gens[latest_message_id].element,
                    referrer=gens[latest_message_id].event.referrer,
                )

            if bet_amount <= 0:
                await matcher.finish(
                    Messages.BET_TOO_SMALL + gens[latest_message_id].element,
                    referrer=gens[latest_message_id].event.referrer,
                )

    elif bet_amount <= 0:
        await matcher.finish(
            Messages.BET_TOO_SMALL + gens[latest_message_id].element,
            referrer=gens[latest_message_id].event.referrer,
        )

    return bet_amount, latest_message_id


async def handle_initial_blackjack(
    session: GameSession,
    bet_amount: int,
    latest_message_id: str,
    matcher: Matcher,
    game_manager: GameManager,
    identity: Optional[PlayerIdentity] = None,
) -> bool:
    renderer = game_manager.renderer_for(session.user_id)
    player_blackjack = (
        len(session.player_hand.cards) == 2 and session.player_hand.value == 21
    )
    dealer_blackjack = (
        len(session.dealer_hand.cards) == 2 and session.dealer_hand.value == 21
    )

    if dealer_blackjack and not player_blackjack:
        game_manager.end_game(
            session.user_id,
            GameResult.BUST,
            winnings=-bet_amount,
        )
        await matcher.finish(
            await _render_jpeg_segment(
                renderer.generate_table,
                session.dealer_hand,
                session.player_hand,
                False,
                identity=identity,
                detail=_bet_detail(bet_amount),
            )
            + Messages.DEALER_BLACKJACK_LOSE.format(amount=bet_amount)
            + f"你现在有 {monetary.get(session.user_id)} 个Pt"
            + gens[latest_message_id].element,
            referrer=gens[latest_message_id].event.referrer,
        )
        return True

    if player_blackjack:
        if dealer_blackjack:
            game_manager.end_game(session.user_id, GameResult.PUSH, winnings=0)
            await matcher.finish(
                await _render_jpeg_segment(
                    renderer.generate_table,
                    session.dealer_hand,
                    session.player_hand,
                    False,
                    identity=identity,
                    detail=_bet_detail(bet_amount),
                )
                + Messages.BLACKJACK_PUSH
                + f"你现在有 {monetary.get(session.user_id)} 个Pt"
                + gens[latest_message_id].element,
                referrer=gens[latest_message_id].event.referrer,
            )
        else:
            blackjack_winnings = int(bet_amount * 1.5)
            actual_winnings = game_manager.end_game(
                session.user_id,
                GameResult.BLACKJACK,
                winnings=blackjack_winnings,
            )
            win_msg = Messages.BLACKJACK_WIN.format(
                bet=bet_amount, amount=actual_winnings
            )
            # Plugin message first
            await matcher.send(
                await _render_jpeg_segment(
                    renderer.generate_table,
                    session.dealer_hand,
                    session.player_hand,
                    False,
                    identity=identity,
                    detail=_bet_detail(bet_amount),
                )
                + win_msg
                + f"你现在有 {monetary.get(session.user_id)} 个Pt！"
                + gens[latest_message_id].element,
                referrer=gens[latest_message_id].event.referrer,
            )
            # Daily task
            task_msg = await check_progress(
                session.user_id,
                "blackjack_win",
            )
            if task_msg:
                await matcher.send(
                    task_msg + gens[latest_message_id].element,
                    referrer=gens[latest_message_id].event.referrer,
                )
            # Level-up
            level_msg = await monetary.add_xp(session.user_id, 5)
            if level_msg:
                await matcher.send(
                    level_msg + gens[latest_message_id].element,
                    referrer=gens[latest_message_id].event.referrer,
                )
            await matcher.finish()
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
    identity: Optional[PlayerIdentity] = None,
) -> Tuple[bool, int, str]:
    split_card = False
    renderer = game_manager.renderer_for(session.user_id)

    if (
        session.player_hand.cards[0].get_value()
        == session.player_hand.cards[1].get_value()
    ):
        sentence = Messages.SPLIT_PROMPT
        await matcher.send(
            await _render_jpeg_segment(
                renderer.generate_table,
                session.dealer_hand,
                session.player_hand,
                True,
                identity=identity,
                detail=_bet_detail(bet_amount),
            )
            + sentence
            + Messages.SPLIT_CHOICE
            + gens[latest_message_id].element,
            referrer=gens[latest_message_id].event.referrer,
        )
        resp = await check.wait(timeout=60)

        if resp is None:
            await matcher.send(
                Messages.SPLIT_TIMEOUT + gens[latest_message_id].element,
                referrer=gens[latest_message_id].event.referrer,
            )
            split_card = False
        else:
            msg = str(resp.get_message()).strip()
            latest_message_id = resp.message.id
            gens[latest_message_id] = PG(resp)

            if msg not in ["是", "否"]:
                await matcher.send(
                    Messages.SPLIT_INVALID + gens[latest_message_id].element,
                    referrer=gens[latest_message_id].event.referrer,
                )
                split_card = False
            else:
                split_card = "是" in msg

        if (amount := monetary.get(event.get_user_id())) < bet_amount:
            await matcher.send(
                Messages.SPLIT_NOT_ENOUGH.format(amount=amount)
                + gens[latest_message_id].element,
                referrer=gens[latest_message_id].event.referrer,
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
    identity: Optional[PlayerIdentity] = None,
) -> None:
    renderer = game_manager.renderer_for(session.user_id)
    second_hand = Hand()
    second_hand.add_card(session.player_hand.cards.pop())
    session.player_hand.add_card(game_manager.get_shoe(event.channel.id).deal())
    second_hand.add_card(game_manager.get_shoe(event.channel.id).deal())
    session.split_hand = second_hand

    game_ended_map = {1: False, 2: False}

    for idx, hand in enumerate([session.player_hand, session.split_hand]):
        if hand.value == 21:
            await matcher.send(
                await _render_jpeg_segment(
                    renderer.generate_table,
                    session.dealer_hand,
                    hand,
                    True,
                    identity=identity,
                    detail=_bet_detail(bet_amount // 2),
                )
                + f"【第 {idx + 1} 幅牌】"
                + gens[latest_message_id].element,
                referrer=gens[latest_message_id].event.referrer,
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
                identity=identity,
            )
            game_ended_map[idx + 1] = game_ended

    dealer_result = await play_dealer_turn(
        session.dealer_hand,
        event.channel.id,
        session.user_id,
        latest_message_id,
        game_manager,
        identity=identity,
        detail=_bet_detail(bet_amount),
    )
    await matcher.send(dealer_result, referrer=event.referrer)
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

    actual_winnings = game_manager.end_game(
        event.get_user_id(),
        split_result,
        winnings=total_winnings,
    )
    result_messages += f"你现在有 {monetary.get(event.get_user_id())} 个Pt"
    await matcher.send(
        result_messages + gens[latest_message_id].element,
        referrer=gens[latest_message_id].event.referrer,
    )
    # Daily task and XP for blackjack win
    if actual_winnings > 0:
        task_msg = await check_progress(event.get_user_id(), "blackjack_win")
        if task_msg:
            await matcher.send(
                task_msg + gens[latest_message_id].element,
                referrer=gens[latest_message_id].event.referrer,
            )
        level_msg = await monetary.add_xp(event.get_user_id(), 5)
        if level_msg:
            await matcher.send(
                level_msg + gens[latest_message_id].element,
                referrer=gens[latest_message_id].event.referrer,
            )


async def handle_normal_game(
    session: GameSession,
    bet_amount: int,
    event: MessageEvent,
    latest_message_id: str,
    check: Waiter[MessageEvent],
    matcher: Matcher,
    game_manager: GameManager,
    identity: Optional[PlayerIdentity] = None,
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
        identity=identity,
    )
    if game_ended:
        return

    dealer_result = await play_dealer_turn(
        session.dealer_hand,
        event.channel.id,
        session.user_id,
        latest_message_id,
        game_manager,
        identity=identity,
        detail=_bet_detail(bet_amount),
    )
    await matcher.send(dealer_result, referrer=event.referrer)
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

    actual_winnings = game_manager.end_game(
        event.get_user_id(), game_result, winnings=winnings
    )

    _, hand_result = evaluate_hand_result(
        session.player_hand,
        session.dealer_hand,
        bet_amount,
    )

    result_messages += (
        hand_result + f"，你现在有 {monetary.get(event.get_user_id())} 个Pt"
    )

    await matcher.send(
        result_messages + gens[latest_message_id].element,
        referrer=gens[latest_message_id].event.referrer,
    )

    # Daily task and XP for blackjack win
    if actual_winnings > 0:
        task_msg = await check_progress(event.get_user_id(), "blackjack_win")
        if task_msg:
            await matcher.send(
                task_msg + gens[latest_message_id].element,
                referrer=gens[latest_message_id].event.referrer,
            )
        level_msg = await monetary.add_xp(event.get_user_id(), 5)
        if level_msg:
            await matcher.send(
                level_msg + gens[latest_message_id].element,
                referrer=gens[latest_message_id].event.referrer,
            )
