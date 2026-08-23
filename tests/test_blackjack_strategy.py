from __future__ import annotations

import pytest


def test_exact_strategy_matches_the_current_live_rule_set() -> None:
    from plugins.blackjack.strategy import StrategyConfig
    from plugins.blackjack.strategy import OptimalStrategy

    result = OptimalStrategy(StrategyConfig(bet_amount=100)).exact_result()

    # The result is expressed per initial stake.  Keeping it pinned catches
    # accidental rules drift (dealer soft-17, natural payout, surrender
    # rounding, split/double permissions, or a change from replacement draws).
    assert result.net_per_initial_bet == pytest.approx(-0.00412385962, abs=1e-10)
    assert result.expected_total_stake == pytest.approx(1.1162074157, abs=1e-10)


def test_seeded_simulation_agrees_with_the_exact_strategy_value() -> None:
    from plugins.blackjack.strategy import StrategyConfig
    from plugins.blackjack.strategy import OptimalStrategy

    strategy = OptimalStrategy(StrategyConfig(bet_amount=100))
    exact = strategy.exact_result()
    simulated = strategy.simulate(1_000_000, seed=20260815)

    low, high = simulated.confidence_interval_95
    assert low <= exact.net_per_initial_bet <= high
    assert simulated.expected_total_stake == pytest.approx(
        exact.expected_total_stake, abs=0.002
    )


def test_one_pt_rounding_is_included_in_the_calculation() -> None:
    from plugins.blackjack.rules import surrender_loss
    from plugins.blackjack.rules import blackjack_winnings
    from plugins.blackjack.strategy import StrategyConfig
    from plugins.blackjack.strategy import OptimalStrategy

    assert blackjack_winnings(1) == 1
    assert surrender_loss(1) == 1

    one_pt = OptimalStrategy(StrategyConfig(bet_amount=1)).exact_result()
    even_pt = OptimalStrategy(StrategyConfig(bet_amount=100)).exact_result()
    assert one_pt.net_per_initial_bet != even_pt.net_per_initial_bet


def test_strategy_cells_expose_exact_round_win_probabilities() -> None:
    from plugins.blackjack.strategy import Action
    from plugins.blackjack.strategy import StrategyConfig
    from plugins.blackjack.strategy import OptimalStrategy

    strategy = OptimalStrategy(StrategyConfig(bet_amount=100))
    surrender = strategy.first_action_cell(16, 0, 10)
    split = strategy.opening_cell(8, 8, 10)

    assert surrender.action is Action.SURRENDER
    assert surrender.outcomes.win_rate == 0
    assert split.action is Action.SPLIT
    assert sum((split.outcomes.win, split.outcomes.push, split.outcomes.loss)) == pytest.approx(1)
