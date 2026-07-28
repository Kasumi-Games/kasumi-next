"""Pure blackjack rules shared by handlers and balance tests."""


def can_surrender(play_round: int) -> bool:
    """Return whether surrender is available before this hand's next action."""

    return play_round == 1
