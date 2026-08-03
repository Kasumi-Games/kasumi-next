from __future__ import annotations

from types import SimpleNamespace

import pytest
from nonebot.adapters.satori import Message


def _hand(*ranks: str):
    from plugins.blackjack.models import Card
    from plugins.blackjack.models import Hand

    hand = Hand()
    for rank in ranks:
        hand.add_card(Card("happy", rank))
    return hand


@pytest.mark.asyncio
async def test_split_round_with_a_busted_hand_is_settled_and_recorded_once(
    monkeypatch,
):
    from plugins.blackjack.models import GameResult
    from plugins.blackjack.session import GameManager
    from plugins.blackjack.handlers import gens
    from plugins.blackjack.handlers import handle_split_game

    class Renderer:
        def generate_table(self, *args, **kwargs):
            return object()

        def generate_hand(self, *args, **kwargs):
            return object()

    class Shoe:
        def __init__(self):
            self.cards = iter(
                [
                    # One card for each split hand, then the first hand hits.
                    _hand("5").cards[0],
                    _hand("8").cards[0],
                    _hand("10").cards[0],
                ]
            )

        def deal(self):
            return next(self.cards)

    class Response:
        def __init__(self, text: str, message_id: str):
            self.text = text
            self.message = SimpleNamespace(id=message_id)

        def get_message(self):
            return Message(self.text)

    class Check:
        def __init__(self):
            self.responses = iter(
                [
                    Response("h", "first-hand-bust"),
                    Response("s", "second-hand-stand"),
                ]
            )

        def __call__(self, timeout):
            async def responses():
                yield next(self.responses)

            return responses()

    class Matcher:
        async def send(self, message=None, **kwargs):
            return None

    generator = SimpleNamespace(
        element=Message(),
        event=SimpleNamespace(referrer=None),
    )
    gens["initial"] = generator
    monkeypatch.setattr("plugins.blackjack.handlers.PG", lambda event: generator)

    async def render_segment(*args, **kwargs):
        return Message()

    monkeypatch.setattr(
        "plugins.blackjack.handlers._render_jpeg_segment", render_segment
    )

    balance_changes: list[int] = []
    monkeypatch.setattr("plugins.blackjack.session.monetary.get", lambda user_id: 100)
    monkeypatch.setattr(
        "plugins.blackjack.session.monetary.cost",
        lambda user_id, amount, reason: balance_changes.append(-amount),
    )
    monkeypatch.setattr(
        "plugins.blackjack.session.monetary.add",
        lambda user_id, amount, reason: balance_changes.append(amount),
    )
    monkeypatch.setattr("plugins.blackjack.handlers.monetary.get", lambda user_id: 80)

    recorded_games: list[dict] = []
    monkeypatch.setattr(
        "plugins.blackjack.session.BlackjackGameService.record_game",
        lambda **kwargs: recorded_games.append(kwargs),
    )

    manager = GameManager(renderer=Renderer())
    manager._shoes["channel"] = Shoe()
    assert manager.start_game("user", 10)
    # Mirror the extra stake and state established by handle_split_decision.
    balance_changes.append(-10)
    manager.set_player_bet("user", 20)
    manager.set_split_state("user", 1)

    session = manager.create_session(
        "user",
        "channel",
        20,
        _hand("10", "10"),
        _hand("10", "7"),
        renderer=Renderer(),
    )
    event = SimpleNamespace(
        channel=SimpleNamespace(id="channel"),
        get_user_id=lambda: "user",
        referrer=None,
    )

    await handle_split_game(
        session,
        20,
        event,
        "initial",
        Check(),
        Matcher(),
        manager,
    )

    assert recorded_games == [
        {
            "user_id": "user",
            "bet_amount": 20,
            "result": GameResult.PUSH,
            "winnings": 0,
            "is_split": True,
        }
    ]
    assert balance_changes == [-10, -10, 20]
    assert not manager.is_in_game("user")
