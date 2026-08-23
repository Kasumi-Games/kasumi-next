"""Exact optimal strategy and a rule-faithful Blackjack simulator.

The live plugin draws every card with replacement (``Shoe.deal``), so an
infinite-shoe dynamic programme is exact for its expected values.  This module
deliberately imports the live ``Shoe``/``Hand`` implementations and shared
settlement helpers: the Monte-Carlo path therefore follows the production deal
order, ace handling, rounding and early-stop behaviour.
"""

from __future__ import annotations

import math
import random
from enum import StrEnum
from typing import Iterable
from functools import lru_cache
from collections import Counter
from collections import defaultdict
from dataclasses import dataclass

from .rules import is_split_pair
from .rules import surrender_loss
from .rules import dealer_should_hit
from .rules import blackjack_winnings
from .rules import is_natural_blackjack
from .models import Card
from .models import Hand
from .models import Shoe

# Card values, not ranks.  Ten covers 10/J/Q/K, exactly as ``Shoe.deal`` does.
CARD_PROBABILITIES: tuple[tuple[int, float], ...] = tuple(
    (value, 1 / 13) for value in range(1, 10)
) + ((10, 4 / 13),)
DEALER_UPCARDS = (2, 3, 4, 5, 6, 7, 8, 9, 10, 1)
PAIR_VALUES = (2, 3, 4, 5, 6, 7, 8, 9, 10, 1)


class Action(StrEnum):
    HIT = "H"
    STAND = "S"
    DOUBLE = "D"
    SURRENDER = "R"
    SPLIT = "P"


@dataclass(frozen=True)
class StrategyConfig:
    """The parts of a live round that can alter an optimal decision.

    A table assumes the player can fund an extra base bet.  If they cannot,
    the live plugin rejects double/split, so setting ``allow_extra_stake`` to
    ``False`` produces the correct fallback chart.  Whole-Pt rounding means a
    one-Pt bet is not strategically identical to an even bet.
    """

    bet_amount: int = 100
    allow_extra_stake: bool = True

    def __post_init__(self) -> None:
        if self.bet_amount <= 0:
            raise ValueError("bet_amount must be positive")


@dataclass(frozen=True)
class ExactResult:
    net_per_initial_bet: float
    expected_total_stake: float

    @property
    def net_per_total_staked(self) -> float:
        return self.net_per_initial_bet / self.expected_total_stake


@dataclass(frozen=True)
class SimulationResult:
    rounds: int
    seed: int
    net_per_initial_bet: float
    net_per_total_staked: float
    expected_total_stake: float
    standard_error: float
    confidence_interval_95: tuple[float, float]
    opening_actions: dict[str, int]


@dataclass(frozen=True)
class PlayedHand:
    status: str
    total: int
    stake: int


@dataclass(frozen=True)
class OutcomeProfile:
    """Exact probabilities for a resolved game result at one strategy cell."""

    win: float
    push: float
    loss: float

    @property
    def win_rate(self) -> float:
        """Probability of a positive net Pt result; pushes are excluded."""

        return self.win


@dataclass(frozen=True)
class StrategyCell:
    """Player-facing action and its exact eventual round outcome rates."""

    action: Action
    outcomes: OutcomeProfile


def _total(hard_total: int, aces: int) -> int:
    return hard_total + (10 if aces and hard_total + 10 <= 21 else 0)


def _add_card(hard_total: int, aces: int, card: int) -> tuple[int, int]:
    return hard_total + card, aces + (card == 1)


def _dealer_blackjack_probability(upcard: int) -> float:
    if upcard == 1:
        return 4 / 13
    if upcard == 10:
        return 1 / 13
    return 0.0


class OptimalStrategy:
    """Solve the current plugin rules for a fixed bet and bankroll state."""

    def __init__(self, config: StrategyConfig = StrategyConfig()) -> None:
        self.config = config

    @staticmethod
    def _tie_break(options: Iterable[tuple[float, Action]]) -> tuple[float, Action]:
        # The ordering only resolves mathematically equal choices.  Preferring
        # fewer commitments makes a displayed table easier to use.
        priority = {
            Action.STAND: 4,
            Action.HIT: 3,
            Action.DOUBLE: 2,
            Action.SURRENDER: 1,
            Action.SPLIT: 0,
        }
        return max(options, key=lambda option: (option[0], priority[option[1]]))

    @lru_cache(maxsize=None)
    def dealer_finish(self, hard_total: int, aces: int) -> dict[int, float]:
        total = _total(hard_total, aces)
        if not dealer_should_hit(total):
            return {total if total <= 21 else 22: 1.0}

        outcomes: defaultdict[int, float] = defaultdict(float)
        for card, probability in CARD_PROBABILITIES:
            for result, conditional_probability in self.dealer_finish(
                *_add_card(hard_total, aces, card)
            ).items():
                outcomes[result] += probability * conditional_probability
        return dict(outcomes)

    @lru_cache(maxsize=None)
    def dealer_distribution(
        self, upcard: int, blackjack_ruled_out: bool
    ) -> dict[int, float]:
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
            for result, conditional_probability in self.dealer_finish(
                upcard + hole, (upcard == 1) + (hole == 1)
            ).items():
                outcomes[result] += probability * conditional_probability / normalizer
        return dict(outcomes)

    @lru_cache(maxsize=None)
    def stand_value(self, total: int, upcard: int, blackjack_ruled_out: bool) -> float:
        stake = self.config.bet_amount
        return sum(
            probability
            * (
                stake
                if dealer_total == 22 or total > dealer_total
                else -stake
                if total < dealer_total
                else 0
            )
            for dealer_total, probability in self.dealer_distribution(
                upcard, blackjack_ruled_out
            ).items()
        )

    @lru_cache(maxsize=None)
    def after_hit_decision(
        self, hard_total: int, aces: int, upcard: int, blackjack_ruled_out: bool
    ) -> tuple[float, Action]:
        total = _total(hard_total, aces)
        if total > 21:
            return -float(self.config.bet_amount), Action.HIT
        if total == 21:
            return self.stand_value(total, upcard, blackjack_ruled_out), Action.STAND

        stand = self.stand_value(total, upcard, blackjack_ruled_out)
        hit = sum(
            probability
            * self.after_hit_decision(
                *_add_card(hard_total, aces, card), upcard, blackjack_ruled_out
            )[0]
            for card, probability in CARD_PROBABILITIES
        )
        return self._tie_break(((stand, Action.STAND), (hit, Action.HIT)))

    @lru_cache(maxsize=None)
    def first_action_decision(
        self,
        hard_total: int,
        aces: int,
        upcard: int,
        blackjack_ruled_out: bool,
        allow_double: bool,
    ) -> tuple[float, Action]:
        total = _total(hard_total, aces)
        if total == 21:
            return self.stand_value(total, upcard, blackjack_ruled_out), Action.STAND

        stand = self.stand_value(total, upcard, blackjack_ruled_out)
        hit = sum(
            probability
            * self.after_hit_decision(
                *_add_card(hard_total, aces, card), upcard, blackjack_ruled_out
            )[0]
            for card, probability in CARD_PROBABILITIES
        )
        options: list[tuple[float, Action]] = [
            (stand, Action.STAND),
            (hit, Action.HIT),
            (-float(surrender_loss(self.config.bet_amount)), Action.SURRENDER),
        ]
        if allow_double and self.config.allow_extra_stake:
            double = 2 * sum(
                probability
                * (
                    -self.config.bet_amount
                    if _total(*_add_card(hard_total, aces, card)) > 21
                    else self.stand_value(
                        _total(*_add_card(hard_total, aces, card)),
                        upcard,
                        blackjack_ruled_out,
                    )
                )
                for card, probability in CARD_PROBABILITIES
            )
            options.append((double, Action.DOUBLE))
        return self._tie_break(options)

    @lru_cache(maxsize=None)
    def split_value(self, pair: int, upcard: int, blackjack_ruled_out: bool) -> float:
        # The live game gives one card to each hand, then permits hit/stand or
        # surrender only.  A split 21 is merely a standing 21, not a natural.
        return 2 * sum(
            probability
            * self.first_action_decision(
                pair + card,
                (pair == 1) + (card == 1),
                upcard,
                blackjack_ruled_out,
                False,
            )[0]
            for card, probability in CARD_PROBABILITIES
        )

    def opening_decision(
        self, first_card: int, second_card: int, upcard: int
    ) -> tuple[float, Action]:
        """Return the first legal optimal action after the dealer peek."""

        hard_total = first_card + second_card
        aces = (first_card == 1) + (second_card == 1)
        blackjack_ruled_out = upcard in (1, 10)
        normal = self.first_action_decision(
            hard_total,
            aces,
            upcard,
            blackjack_ruled_out,
            True,
        )
        if not is_split_pair(first_card, second_card) or not self.config.allow_extra_stake:
            return normal
        return self._tie_break(
            (
                normal,
                (self.split_value(first_card, upcard, blackjack_ruled_out), Action.SPLIT),
            )
        )

    @staticmethod
    def _merge_hand_distribution(
        outcomes: Iterable[tuple[PlayedHand, float]]
    ) -> tuple[tuple[PlayedHand, float], ...]:
        merged: defaultdict[PlayedHand, float] = defaultdict(float)
        for hand, probability in outcomes:
            merged[hand] += probability
        return tuple(merged.items())

    @lru_cache(maxsize=None)
    def _after_hit_hand_distribution(
        self, hard_total: int, aces: int, upcard: int, blackjack_ruled_out: bool
    ) -> tuple[tuple[PlayedHand, float], ...]:
        total = _total(hard_total, aces)
        if total > 21:
            return ((PlayedHand("bust", total, self.config.bet_amount), 1.0),)
        if total == 21:
            return ((PlayedHand("stand", total, self.config.bet_amount), 1.0),)

        _, action = self.after_hit_decision(
            hard_total, aces, upcard, blackjack_ruled_out
        )
        if action is Action.STAND:
            return ((PlayedHand("stand", total, self.config.bet_amount), 1.0),)

        return self._merge_hand_distribution(
            (
                (outcome, probability * conditional_probability)
                for card, probability in CARD_PROBABILITIES
                for outcome, conditional_probability in self._after_hit_hand_distribution(
                    *_add_card(hard_total, aces, card), upcard, blackjack_ruled_out
                )
            )
        )

    @lru_cache(maxsize=None)
    def _first_hand_distribution(
        self,
        hard_total: int,
        aces: int,
        upcard: int,
        blackjack_ruled_out: bool,
        allow_double: bool,
    ) -> tuple[tuple[PlayedHand, float], ...]:
        total = _total(hard_total, aces)
        _, action = self.first_action_decision(
            hard_total, aces, upcard, blackjack_ruled_out, allow_double
        )
        if action is Action.SURRENDER:
            return ((PlayedHand("surrender", total, self.config.bet_amount), 1.0),)
        if action is Action.STAND:
            return ((PlayedHand("stand", total, self.config.bet_amount), 1.0),)
        if action is Action.DOUBLE:
            return self._merge_hand_distribution(
                (
                    (
                        PlayedHand(
                            "bust" if _total(*_add_card(hard_total, aces, card)) > 21 else "stand",
                            _total(*_add_card(hard_total, aces, card)),
                            self.config.bet_amount * 2,
                        ),
                        probability,
                    )
                    for card, probability in CARD_PROBABILITIES
                )
            )

        return self._merge_hand_distribution(
            (
                (outcome, probability * conditional_probability)
                for card, probability in CARD_PROBABILITIES
                for outcome, conditional_probability in self._after_hit_hand_distribution(
                    *_add_card(hard_total, aces, card), upcard, blackjack_ruled_out
                )
            )
        )

    def _settlement_amount(self, hand: PlayedHand, dealer_total: int) -> int:
        return self._settle_hand(hand, dealer_total)

    def _single_hand_outcomes(
        self,
        hand_distribution: Iterable[tuple[PlayedHand, float]],
        upcard: int,
        blackjack_ruled_out: bool,
    ) -> OutcomeProfile:
        result = defaultdict(float)
        for hand, hand_probability in hand_distribution:
            for dealer_total, dealer_probability in self.dealer_distribution(
                upcard, blackjack_ruled_out
            ).items():
                amount = self._settlement_amount(hand, dealer_total)
                result["win" if amount > 0 else "push" if amount == 0 else "loss"] += (
                    hand_probability * dealer_probability
                )
        return OutcomeProfile(result["win"], result["push"], result["loss"])

    @lru_cache(maxsize=None)
    def _split_hand_distribution(
        self, pair: int, upcard: int, blackjack_ruled_out: bool
    ) -> tuple[tuple[PlayedHand, float], ...]:
        return self._merge_hand_distribution(
            (
                (outcome, probability * conditional_probability)
                for card, probability in CARD_PROBABILITIES
                for outcome, conditional_probability in self._first_hand_distribution(
                    pair + card,
                    (pair == 1) + (card == 1),
                    upcard,
                    blackjack_ruled_out,
                    False,
                )
            )
        )

    def _split_outcomes(
        self, pair: int, upcard: int, blackjack_ruled_out: bool
    ) -> OutcomeProfile:
        hands = self._split_hand_distribution(pair, upcard, blackjack_ruled_out)
        result = defaultdict(float)
        for dealer_total, dealer_probability in self.dealer_distribution(
            upcard, blackjack_ruled_out
        ).items():
            for left_hand, left_probability in hands:
                for right_hand, right_probability in hands:
                    amount = self._settlement_amount(
                        left_hand, dealer_total
                    ) + self._settlement_amount(right_hand, dealer_total)
                    result[
                        "win" if amount > 0 else "push" if amount == 0 else "loss"
                    ] += dealer_probability * left_probability * right_probability
        return OutcomeProfile(result["win"], result["push"], result["loss"])

    def first_action_cell(self, hard_total: int, aces: int, upcard: int) -> StrategyCell:
        """Return a non-pair opening cell once a dealer natural is ruled out."""

        blackjack_ruled_out = upcard in (1, 10)
        _, action = self.first_action_decision(
            hard_total, aces, upcard, blackjack_ruled_out, True
        )
        outcomes = self._single_hand_outcomes(
            self._first_hand_distribution(
                hard_total, aces, upcard, blackjack_ruled_out, True
            ),
            upcard,
            blackjack_ruled_out,
        )
        return StrategyCell(action, outcomes)

    def opening_cell(self, first_card: int, second_card: int, upcard: int) -> StrategyCell:
        """Return the player-facing cell, including split-round settlement."""

        blackjack_ruled_out = upcard in (1, 10)
        _, action = self.opening_decision(first_card, second_card, upcard)
        if action is Action.SPLIT:
            outcomes = self._split_outcomes(
                first_card, upcard, blackjack_ruled_out
            )
        else:
            outcomes = self._single_hand_outcomes(
                self._first_hand_distribution(
                    first_card + second_card,
                    (first_card == 1) + (second_card == 1),
                    upcard,
                    blackjack_ruled_out,
                    True,
                ),
                upcard,
                blackjack_ruled_out,
            )
        return StrategyCell(action, outcomes)

    def exact_result(self) -> ExactResult:
        """Calculate expected net Pt and stake per initial bet unit."""

        bet_amount = self.config.bet_amount
        net = 0.0
        total_stake = 0.0
        for first_card, first_probability in CARD_PROBABILITIES:
            for upcard, upcard_probability in CARD_PROBABILITIES:
                for second_card, second_probability in CARD_PROBABILITIES:
                    probability = first_probability * upcard_probability * second_probability
                    hard_total = first_card + second_card
                    aces = (first_card == 1) + (second_card == 1)
                    total = _total(hard_total, aces)
                    dealer_blackjack_probability = _dealer_blackjack_probability(upcard)

                    if total == 21:
                        hand_net = blackjack_winnings(bet_amount) * (
                            1 - dealer_blackjack_probability
                        )
                        stake = bet_amount
                    else:
                        no_blackjack_net, action = self.opening_decision(
                            first_card, second_card, upcard
                        )
                        hand_net = (
                            -bet_amount * dealer_blackjack_probability
                            + (1 - dealer_blackjack_probability) * no_blackjack_net
                        )
                        stake = bet_amount * (
                            dealer_blackjack_probability
                            + (1 - dealer_blackjack_probability)
                            * (
                                2
                                if action in (Action.DOUBLE, Action.SPLIT)
                                else 1
                            )
                        )
                    net += probability * hand_net
                    total_stake += probability * stake

        return ExactResult(
            net_per_initial_bet=net / bet_amount,
            expected_total_stake=total_stake / bet_amount,
        )

    def _play_hand(
        self, hand: Hand, upcard: int, shoe: Shoe, *, allow_double: bool
    ) -> PlayedHand:
        hard_total, aces = _hand_state(hand)
        blackjack_ruled_out = upcard in (1, 10)
        _, action = self.first_action_decision(
            hard_total, aces, upcard, blackjack_ruled_out, allow_double
        )
        if action is Action.SURRENDER:
            return PlayedHand("surrender", hand.value, self.config.bet_amount)
        if action is Action.DOUBLE:
            hand.add_card(shoe.deal())
            return PlayedHand(
                "bust" if hand.value > 21 else "stand",
                hand.value,
                self.config.bet_amount * 2,
            )
        if action is Action.STAND:
            return PlayedHand("stand", hand.value, self.config.bet_amount)

        while action is Action.HIT:
            hand.add_card(shoe.deal())
            if hand.value > 21:
                return PlayedHand("bust", hand.value, self.config.bet_amount)
            hard_total, aces = _hand_state(hand)
            _, action = self.after_hit_decision(
                hard_total, aces, upcard, blackjack_ruled_out
            )
        return PlayedHand("stand", hand.value, self.config.bet_amount)

    def _settle_hand(self, hand: PlayedHand, dealer_total: int) -> int:
        if hand.status == "surrender":
            return -surrender_loss(self.config.bet_amount)
        if hand.status == "bust":
            return -hand.stake
        if dealer_total > 21 or hand.total > dealer_total:
            return hand.stake
        if hand.total < dealer_total:
            return -hand.stake
        return 0

    @staticmethod
    def _finish_dealer(dealer_hand: Hand, shoe: Shoe) -> int:
        while dealer_should_hit(dealer_hand.value):
            dealer_hand.add_card(shoe.deal())
        return dealer_hand.value

    def simulate(self, rounds: int, seed: int = 20260815) -> SimulationResult:
        """Replay live-round control flow under the optimal policy.

        Notably, a normal-hand bust/surrender does *not* draw out the dealer,
        while a split round always does.  That distinction has no isolated EV
        effect but is necessary to preserve the production RNG stream.
        """

        if rounds <= 0:
            raise ValueError("rounds must be positive")

        shoe = Shoe(random.Random(seed))
        profit_sum = 0
        profit_square_sum = 0
        total_staked = 0
        opening_actions: Counter[str] = Counter()
        bet_amount = self.config.bet_amount

        for _ in range(rounds):
            player_hand = Hand()
            dealer_hand = Hand()
            player_hand.add_card(shoe.deal())
            dealer_hand.add_card(shoe.deal())
            player_hand.add_card(shoe.deal())
            dealer_hand.add_card(shoe.deal())
            upcard = _card_value(dealer_hand.cards[0])

            player_blackjack = is_natural_blackjack(
                len(player_hand.cards), player_hand.value
            )
            dealer_blackjack = is_natural_blackjack(
                len(dealer_hand.cards), dealer_hand.value
            )
            if dealer_blackjack:
                profit = 0 if player_blackjack else -bet_amount
                stake = bet_amount
                opening_actions["dealer_blackjack"] += 1
            elif player_blackjack:
                profit = blackjack_winnings(bet_amount)
                stake = bet_amount
                opening_actions["player_blackjack"] += 1
            else:
                first_card = _card_value(player_hand.cards[0])
                second_card = _card_value(player_hand.cards[1])
                _, action = self.opening_decision(first_card, second_card, upcard)
                opening_actions[action.value] += 1

                if action is Action.SPLIT:
                    second_hand = Hand()
                    second_hand.add_card(player_hand.cards.pop())
                    player_hand._recalculate_value()
                    player_hand.add_card(shoe.deal())
                    second_hand.add_card(shoe.deal())
                    first_outcome = self._play_hand(
                        player_hand, upcard, shoe, allow_double=False
                    )
                    second_outcome = self._play_hand(
                        second_hand, upcard, shoe, allow_double=False
                    )
                    dealer_total = self._finish_dealer(dealer_hand, shoe)
                    profit = self._settle_hand(
                        first_outcome, dealer_total
                    ) + self._settle_hand(second_outcome, dealer_total)
                    stake = first_outcome.stake + second_outcome.stake
                else:
                    outcome = self._play_hand(
                        player_hand, upcard, shoe, allow_double=True
                    )
                    stake = outcome.stake
                    # ``handle_normal_game`` returns straight away on these
                    # paths, so the real dealer draws no additional cards.
                    if outcome.status in ("bust", "surrender"):
                        profit = self._settle_hand(outcome, dealer_hand.value)
                    else:
                        profit = self._settle_hand(
                            outcome, self._finish_dealer(dealer_hand, shoe)
                        )

            profit_sum += profit
            profit_square_sum += profit * profit
            total_staked += stake

        mean = profit_sum / rounds / bet_amount
        variance = max(0.0, profit_square_sum / rounds - (profit_sum / rounds) ** 2)
        standard_error = math.sqrt(variance / rounds) / bet_amount
        return SimulationResult(
            rounds=rounds,
            seed=seed,
            net_per_initial_bet=mean,
            net_per_total_staked=profit_sum / total_staked,
            expected_total_stake=total_staked / rounds / bet_amount,
            standard_error=standard_error,
            confidence_interval_95=(
                mean - 1.96 * standard_error,
                mean + 1.96 * standard_error,
            ),
            opening_actions=dict(opening_actions),
        )


def _card_value(card: Card) -> int:
    return 1 if card.rank == "A" else min(card.get_value(), 10)


def _hand_state(hand: Hand) -> tuple[int, int]:
    values = [_card_value(card) for card in hand.cards]
    return sum(values), values.count(1)


def dealer_label(upcard: int) -> str:
    return "A" if upcard == 1 else str(upcard)


def pair_label(pair: int) -> str:
    return "A,A" if pair == 1 else f"{pair},{pair}"
