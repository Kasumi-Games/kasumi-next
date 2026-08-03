"""Calculate and simulate the best possible player EV under Kasumi's rules."""

from __future__ import annotations

import math
import random
import argparse
from functools import lru_cache
from collections import Counter
from collections import defaultdict

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
            outcomes[result] += probability * conditional_probability / normalizer
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
def _after_hit_decision(
    hard_total: int,
    aces: int,
    upcard: int,
    blackjack_ruled_out: bool,
) -> tuple[float, str]:
    total = _total(hard_total, aces)
    if total > 21:
        return -1.0, "bust"
    if total == 21:
        return _stand_ev(total, upcard, blackjack_ruled_out), "stand"

    stand = _stand_ev(total, upcard, blackjack_ruled_out)
    hit = sum(
        probability
        * _after_hit_decision(
            *_add_card(hard_total, aces, card),
            upcard,
            blackjack_ruled_out,
        )[0]
        for card, probability in CARD_PROBABILITIES
    )
    return max((stand, "stand"), (hit, "hit"), key=lambda item: item[0])


@lru_cache(maxsize=None)
def _first_action_decision(
    hard_total: int,
    aces: int,
    upcard: int,
    blackjack_ruled_out: bool,
    allow_double: bool,
) -> tuple[float, str]:
    total = _total(hard_total, aces)
    if total == 21:
        return _stand_ev(total, upcard, blackjack_ruled_out), "stand"

    options = [
        (_stand_ev(total, upcard, blackjack_ruled_out), "stand"),
        (
            sum(
                probability
                * _after_hit_decision(
                    *_add_card(hard_total, aces, card),
                    upcard,
                    blackjack_ruled_out,
                )[0]
                for card, probability in CARD_PROBABILITIES
            ),
            "hit",
        ),
        (-0.5, "surrender"),
    ]
    if allow_double:
        options.append(
            (
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
                ),
                "double",
            )
        )
    return max(options, key=lambda item: item[0])


@lru_cache(maxsize=None)
def _split_ev(pair: int, upcard: int, blackjack_ruled_out: bool) -> float:
    return 2 * sum(
        probability
        * _first_action_decision(
            pair + card,
            (pair == 1) + (card == 1),
            upcard,
            blackjack_ruled_out,
            False,
        )[0]
        for card, probability in CARD_PROBABILITIES
    )


def _dealer_blackjack_probability(upcard: int) -> float:
    if upcard == 1:
        return 4 / 13
    if upcard == 10:
        return 1 / 13
    return 0.0


def _opening_decision(
    first_card: int,
    second_card: int,
    upcard: int,
    blackjack_ruled_out: bool,
) -> tuple[float, str]:
    hard_total = first_card + second_card
    aces = (first_card == 1) + (second_card == 1)
    normal = _first_action_decision(
        hard_total,
        aces,
        upcard,
        blackjack_ruled_out,
        True,
    )
    if first_card != second_card:
        return normal
    split = (_split_ev(first_card, upcard, blackjack_ruled_out), "split")
    return max(normal, split, key=lambda item: item[0])


def exact_optimal_result() -> tuple[float, float]:
    """Return expected net profit and expected total stake per initial unit."""
    edge = 0.0
    expected_stake = 0.0

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
                    stake = 1.0
                else:
                    blackjack_ruled_out = dealer_blackjack_probability > 0
                    no_blackjack_edge, action = _opening_decision(
                        first_card,
                        second_card,
                        upcard,
                        blackjack_ruled_out,
                    )
                    hand_edge = (
                        dealer_blackjack_probability * -1
                        + (1 - dealer_blackjack_probability) * no_blackjack_edge
                    )
                    stake = (
                        dealer_blackjack_probability
                        + (1 - dealer_blackjack_probability)
                        * (2 if action in {"double", "split"} else 1)
                    )

                edge += probability * hand_edge
                expected_stake += probability * stake

    return edge, expected_stake


def _sample_card(rng: random.Random) -> int:
    draw = rng.randrange(13)
    return draw + 1 if draw < 9 else 10


def _state(cards: list[int]) -> tuple[int, int]:
    return sum(cards), cards.count(1)


def _dealer_total(cards: list[int], rng: random.Random) -> int:
    hard_total, aces = _state(cards)
    while _total(hard_total, aces) < 17:
        hard_total, aces = _add_card(hard_total, aces, _sample_card(rng))
    total = _total(hard_total, aces)
    return total if total <= 21 else 22


def _play_hand(
    cards: list[int],
    upcard: int,
    blackjack_ruled_out: bool,
    allow_double: bool,
    rng: random.Random,
) -> tuple[str, int, int]:
    hard_total, aces = _state(cards)
    _, action = _first_action_decision(
        hard_total,
        aces,
        upcard,
        blackjack_ruled_out,
        allow_double,
    )

    if action == "surrender":
        return "surrender", 0, 1
    if action == "double":
        hard_total, aces = _add_card(hard_total, aces, _sample_card(rng))
        total = _total(hard_total, aces)
        return ("bust" if total > 21 else "stand"), total, 2
    if action == "stand":
        return "stand", _total(hard_total, aces), 1

    while action == "hit":
        hard_total, aces = _add_card(hard_total, aces, _sample_card(rng))
        total = _total(hard_total, aces)
        if total > 21:
            return "bust", total, 1
        _, action = _after_hit_decision(
            hard_total,
            aces,
            upcard,
            blackjack_ruled_out,
        )
    return "stand", _total(hard_total, aces), 1


def _settle_hand(status: str, total: int, stake: int, dealer_total: int) -> float:
    if status == "surrender":
        return -0.5
    if status == "bust":
        return -stake
    if dealer_total == 22 or total > dealer_total:
        return float(stake)
    if total < dealer_total:
        return float(-stake)
    return 0.0


def simulate(rounds: int, seed: int) -> dict[str, object]:
    rng = random.Random(seed)
    profit_sum = 0.0
    profit_square_sum = 0.0
    total_staked = 0
    opening_actions: Counter[str] = Counter()

    for _ in range(rounds):
        first_card = _sample_card(rng)
        upcard = _sample_card(rng)
        second_card = _sample_card(rng)
        hole_card = _sample_card(rng)
        player_blackjack = {first_card, second_card} == {1, 10}
        dealer_blackjack = {upcard, hole_card} == {1, 10}

        if dealer_blackjack:
            profit = 0.0 if player_blackjack else -1.0
            stake = 1
            opening_actions["dealer_blackjack"] += 1
        elif player_blackjack:
            profit = 1.5
            stake = 1
            opening_actions["player_blackjack"] += 1
        else:
            blackjack_ruled_out = upcard in {1, 10}
            _, action = _opening_decision(
                first_card,
                second_card,
                upcard,
                blackjack_ruled_out,
            )
            opening_actions[action] += 1

            if action == "split":
                hands = [
                    _play_hand(
                        [first_card, _sample_card(rng)],
                        upcard,
                        blackjack_ruled_out,
                        False,
                        rng,
                    )
                    for _ in range(2)
                ]
            else:
                hands = [
                    _play_hand(
                        [first_card, second_card],
                        upcard,
                        blackjack_ruled_out,
                        True,
                        rng,
                    )
                ]

            stake = sum(hand[2] for hand in hands)
            dealer_total = _dealer_total([upcard, hole_card], rng)
            profit = sum(_settle_hand(*hand, dealer_total) for hand in hands)

        profit_sum += profit
        profit_square_sum += profit * profit
        total_staked += stake

    mean = profit_sum / rounds
    variance = max(0.0, profit_square_sum / rounds - mean * mean)
    standard_error = math.sqrt(variance / rounds)
    return {
        "rounds": rounds,
        "seed": seed,
        "net_per_initial_bet": mean,
        "net_per_total_staked": profit_sum / total_staked,
        "expected_total_stake": total_staked / rounds,
        "standard_error": standard_error,
        "confidence_interval_95": (
            mean - 1.96 * standard_error,
            mean + 1.96 * standard_error,
        ),
        "opening_actions": dict(opening_actions),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--rounds", type=int, default=1_000_000)
    parser.add_argument("--seed", type=int, default=20260803)
    args = parser.parse_args()

    edge, expected_stake = exact_optimal_result()
    simulation = simulate(args.rounds, args.seed)
    low, high = simulation["confidence_interval_95"]

    print(f"exact net / initial bet: {edge:.10%}")
    print(f"exact RTP / initial bet: {1 + edge:.10%}")
    print(f"exact expected total stake: {expected_stake:.10f}")
    print(f"exact net / total staked: {edge / expected_stake:.10%}")
    print(f"simulated rounds: {args.rounds:,} (seed={args.seed})")
    print(f"simulated net / initial bet: {simulation['net_per_initial_bet']:.10%}")
    print(f"simulated net / total staked: {simulation['net_per_total_staked']:.10%}")
    print(f"simulated expected total stake: {simulation['expected_total_stake']:.10f}")
    print(f"95% CI / initial bet: [{low:.10%}, {high:.10%}]")
    print(f"opening actions: {simulation['opening_actions']}")


if __name__ == "__main__":
    main()
