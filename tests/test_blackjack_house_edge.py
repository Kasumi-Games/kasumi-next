from __future__ import annotations

from types import SimpleNamespace
from functools import lru_cache
from collections import defaultdict

import pytest
from nonebot.adapters.satori import Message

CARD_PROBABILITIES = (
    (1, 1 / 13),
    (2, 1 / 13),
    (3, 1 / 13),
    (4, 1 / 13),
    (5, 1 / 13),
    (6, 1 / 13),
    (7, 1 / 13),
    (8, 1 / 13),
    (9, 1 / 13),
    (10, 4 / 13),
)


def _total(hard_total: int, aces: int) -> int:
    return hard_total + (10 if aces and hard_total + 10 <= 21 else 0)


def _add_card(hard_total: int, aces: int, card: int) -> tuple[int, int]:
    return hard_total + card, aces + (card == 1)


@lru_cache(maxsize=None)
def _dealer_finish(hard_total: int, aces: int) -> dict[int, float]:
    total = _total(hard_total, aces)
    if total >= 17:
        return {total if total <= 21 else 22: 1.0}

    outcomes: defaultdict[int, float] = defaultdict(float)
    for card, probability in CARD_PROBABILITIES:
        for result, conditional_probability in _dealer_finish(
            *_add_card(hard_total, aces, card)
        ).items():
            outcomes[result] += probability * conditional_probability
    return dict(outcomes)


@lru_cache(maxsize=None)
def _dealer_distribution(upcard: int, blackjack_ruled_out: bool) -> dict[int, float]:
    possible_holes = [
        (card, probability)
        for card, probability in CARD_PROBABILITIES
        if not (
            blackjack_ruled_out
            and ((upcard == 1 and card == 10) or (upcard == 10 and card == 1))
        )
    ]
    normalizer = sum(probability for _, probability in possible_holes)
    outcomes: defaultdict[int, float] = defaultdict(float)
    for hole, probability in possible_holes:
        for result, conditional_probability in _dealer_finish(
            upcard + hole, (upcard == 1) + (hole == 1)
        ).items():
            outcomes[result] += (
                probability * conditional_probability / normalizer
            )
    return dict(outcomes)


@lru_cache(maxsize=None)
def _stand_ev(total: int, upcard: int, blackjack_ruled_out: bool) -> float:
    return sum(
        probability
        * (
            1
            if dealer_total == 22 or total > dealer_total
            else -1
            if total < dealer_total
            else 0
        )
        for dealer_total, probability in _dealer_distribution(
            upcard, blackjack_ruled_out
        ).items()
    )


@lru_cache(maxsize=None)
def _after_hit_ev(
    hard_total: int,
    aces: int,
    upcard: int,
    blackjack_ruled_out: bool,
) -> float:
    total = _total(hard_total, aces)
    if total > 21:
        return -1.0
    if total == 21:
        return _stand_ev(total, upcard, blackjack_ruled_out)

    # Surrender is intentionally absent: this state is only reached after a hit.
    return max(
        _stand_ev(total, upcard, blackjack_ruled_out),
        sum(
            probability
            * _after_hit_ev(
                *_add_card(hard_total, aces, card),
                upcard,
                blackjack_ruled_out,
            )
            for card, probability in CARD_PROBABILITIES
        ),
    )


@lru_cache(maxsize=None)
def _first_action_ev(
    hard_total: int,
    aces: int,
    upcard: int,
    blackjack_ruled_out: bool,
    allow_double: bool,
) -> float:
    total = _total(hard_total, aces)
    if total == 21:
        return _stand_ev(total, upcard, blackjack_ruled_out)

    outcomes = [
        _stand_ev(total, upcard, blackjack_ruled_out),
        sum(
            probability
            * _after_hit_ev(
                *_add_card(hard_total, aces, card),
                upcard,
                blackjack_ruled_out,
            )
            for card, probability in CARD_PROBABILITIES
        ),
        -0.5,
    ]
    if allow_double:
        outcomes.append(
            2
            * sum(
                probability
                * (
                    -1
                    if _total(*_add_card(hard_total, aces, card)) > 21
                    else _stand_ev(
                        _total(*_add_card(hard_total, aces, card)),
                        upcard,
                        blackjack_ruled_out,
                    )
                )
                for card, probability in CARD_PROBABILITIES
            )
        )
    return max(outcomes)


def _split_ev(pair: int, upcard: int, blackjack_ruled_out: bool) -> float:
    return 2 * sum(
        probability
        * _first_action_ev(
            pair + card,
            (pair == 1) + (card == 1),
            upcard,
            blackjack_ruled_out,
            False,
        )
        for card, probability in CARD_PROBABILITIES
    )


def _dealer_blackjack_probability(upcard: int) -> float:
    if upcard == 1:
        return 4 / 13
    if upcard == 10:
        return 1 / 13
    return 0.0


def _optimal_player_edge() -> float:
    edge = 0.0

    for first_card, first_probability in CARD_PROBABILITIES:
        for upcard, upcard_probability in CARD_PROBABILITIES:
            for second_card, second_probability in CARD_PROBABILITIES:
                probability = (
                    first_probability * upcard_probability * second_probability
                )
                hard_total = first_card + second_card
                aces = (first_card == 1) + (second_card == 1)
                total = _total(hard_total, aces)
                dealer_blackjack_probability = _dealer_blackjack_probability(upcard)

                if total == 21:
                    hand_edge = 1.5 * (1 - dealer_blackjack_probability)
                else:
                    blackjack_ruled_out = dealer_blackjack_probability > 0
                    hand_edge = _first_action_ev(
                        hard_total,
                        aces,
                        upcard,
                        blackjack_ruled_out,
                        True,
                    )
                    if first_card == second_card:
                        hand_edge = max(
                            hand_edge,
                            _split_ev(
                                first_card,
                                upcard,
                                blackjack_ruled_out,
                            ),
                        )
                    hand_edge = (
                        dealer_blackjack_probability * -1
                        + (1 - dealer_blackjack_probability) * hand_edge
                    )

                edge += probability * hand_edge

    return edge


def _hand(*ranks: str):
    from plugins.blackjack.models import Card
    from plugins.blackjack.models import Hand

    hand = Hand()
    for rank in ranks:
        hand.add_card(Card("happy", rank))
    return hand


def test_surrender_is_only_available_on_a_hands_first_action():
    from plugins.blackjack.rules import can_surrender

    assert can_surrender(1) is True
    assert can_surrender(2) is False
    assert can_surrender(99) is False


@pytest.mark.asyncio
async def test_surrender_after_a_hit_is_rejected(monkeypatch):
    from plugins.blackjack.handlers import gens
    from plugins.blackjack.handlers import play_player_turn
    from plugins.blackjack.messages import Messages

    class Renderer:
        def generate_table(self, *args, **kwargs):
            return object()

    class Shoe:
        def deal(self):
            from plugins.blackjack.models import Card

            return Card("happy", "2")

    class Manager:
        def __init__(self):
            self.ended = []

        def renderer_for(self, user_id):
            return Renderer()

        def get_split_state(self, user_id):
            return 0

        def get_shoe(self, channel_id):
            return Shoe()

        def end_game(self, *args, **kwargs):
            self.ended.append((args, kwargs))

    class Matcher:
        def __init__(self):
            self.sent = []

        async def send(self, message=None, **kwargs):
            self.sent.append(str(message))

    class Response:
        def __init__(self, text, message_id):
            self.text = text
            self.message = SimpleNamespace(id=message_id)

        def get_message(self):
            return Message(self.text)

    class Check:
        def __init__(self):
            self.responses = iter(
                [
                    Response("h", "hit"),
                    Response("q", "late-surrender"),
                    Response("s", "stand"),
                ]
            )

        def __call__(self, timeout):
            async def responses():
                yield next(self.responses)

            return responses()

    event = SimpleNamespace(
        channel=SimpleNamespace(id="c1"),
        get_user_id=lambda: "u1",
    )
    matcher = Matcher()
    manager = Manager()
    player_hand = _hand("5", "5")
    dealer_hand = _hand("10", "6")
    generator = SimpleNamespace(
        element=Message(),
        event=SimpleNamespace(referrer=None),
    )
    gens["initial"] = generator
    monkeypatch.setattr("plugins.blackjack.handlers.PG", lambda event: generator)
    monkeypatch.setattr(
        "plugins.blackjack.handlers.image_to_bytes",
        lambda image: b"image",
    )

    _, game_ended, final_bet = await play_player_turn(
        player_hand,
        dealer_hand,
        20,
        event,
        "initial",
        Check(),
        matcher,
        manager,
        show_initial_message=False,
    )

    assert game_ended is False
    assert final_bet == 20
    assert player_hand.value == 12
    assert manager.ended == []
    assert any(Messages.SURRENDER_NOT_FIRST in message for message in matcher.sent)


@pytest.mark.asyncio
async def test_dealer_opening_blackjack_ends_the_game_before_player_action(
    monkeypatch,
):
    from plugins.blackjack.models import GameResult
    from plugins.blackjack.session import GameSession
    from plugins.blackjack.handlers import gens
    from plugins.blackjack.handlers import handle_initial_blackjack

    class Renderer:
        def generate_table(self, *args, **kwargs):
            return object()

    class Manager:
        def __init__(self):
            self.ended = []

        def renderer_for(self, user_id):
            return Renderer()

        def end_game(self, user_id, result, winnings=0):
            self.ended.append((user_id, result, winnings))
            return winnings

    class Matcher:
        def __init__(self):
            self.finished = []

        async def finish(self, message=None, **kwargs):
            self.finished.append(message)

        async def send(self, message=None, **kwargs):
            raise AssertionError("dealer blackjack must finish, not continue")

    monkeypatch.setattr(
        "plugins.blackjack.handlers.image_to_bytes",
        lambda image: b"image",
    )
    gens["opening"] = SimpleNamespace(
        element=Message(),
        event=SimpleNamespace(referrer=None),
    )
    manager = Manager()
    matcher = Matcher()
    session = GameSession(
        user_id="u1",
        channel_id="c1",
        bet_amount=20,
        player_hand=_hand("10", "9"),
        dealer_hand=_hand("A", "K"),
    )

    handled = await handle_initial_blackjack(
        session,
        20,
        "opening",
        matcher,
        manager,
    )

    assert handled is True
    assert manager.ended == [("u1", GameResult.BUST, -20)]
    assert len(matcher.finished) == 1


def test_optimal_strategy_has_a_house_edge():
    # This exact infinite-shoe calculation mirrors the public game rules.
    # Keep a margin so harmless float refactors do not make the test brittle.
    edge = _optimal_player_edge()

    assert edge == pytest.approx(-0.00412385962, abs=1e-10)
    assert edge < -0.0035


def test_ev_analysis_matches_the_independent_exact_calculation():
    from scripts.analyze_blackjack_ev import exact_optimal_result

    edge, expected_stake = exact_optimal_result()

    assert edge == pytest.approx(_optimal_player_edge(), abs=1e-12)
    assert expected_stake == pytest.approx(1.1162074157, abs=1e-10)
