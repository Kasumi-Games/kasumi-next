"""Pure blackjack rules shared by the live game and strategy analysis."""

from __future__ import annotations

import math

DEALER_STAND_TOTAL = 17


def dealer_should_hit(total: int) -> bool:
    """Return whether Kasumi draws another card for a resolved hand total."""

    return total < DEALER_STAND_TOTAL


def is_natural_blackjack(card_count: int, total: int) -> bool:
    """Return whether a two-card hand is a BlackKasumi natural."""

    return card_count == 2 and total == 21


def is_split_pair(first_value: int, second_value: int) -> bool:
    """Return whether the live game offers a split for two card values."""

    return first_value == second_value


def blackjack_winnings(bet_amount: int) -> int:
    """Return the live game's net payout for a natural blackjack.

    ``int`` is intentional: the handler has always rounded a 1.5x payout
    down to whole Pt, so strategy calculations must do the same.
    """

    return int(bet_amount * 1.5)


def surrender_loss(bet_amount: int) -> int:
    """Return the live game's whole-Pt loss for a surrender."""

    return math.ceil(bet_amount / 2)


def can_surrender(play_round: int) -> bool:
    """Return whether surrender is available before this hand's next action."""

    return play_round == 1
