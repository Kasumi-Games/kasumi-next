"""The /黑香澄统计 card: data mapping, kit coverage, and the blackjacks count.

The render tests build :class:`StatsCardData` straight from a
:class:`BlackjackStats` instance — the same object the handler gets from
``get_blackjack_stats`` — so the mapping test doubles as a contract check
that the card never reads a field the service does not provide.
"""

from __future__ import annotations

import pytest

from plugins.render import PlayerIdentity
from plugins.render.kits import KasumiKit
from plugins.render.kits import MinimalKit
from plugins.render.kits import MidnightKit
from plugins.render.kits import BanGDreamKit

#: Page width every toolkit card renders at: CONTENT_WIDTH + 2 * PAGE_PADDING.
CARD_WIDTH = 864


def _stats(**overrides):
    from plugins.blackjack.stats_service import BlackjackStats

    base = dict(
        user_id="u1",
        total_games=137,
        wins=57,
        losses=74,
        pushes=6,
        blackjacks=9,
        win_rate=57 / 137,
        total_wagered=27400,
        total_won=18240,
        total_lost=19480,
        net_profit=-1240,
        avg_bet=200.0,
        avg_win=320.0,
        avg_loss=263.2,
        biggest_win=1200,
        biggest_loss=1000,
        recent_games=[],
    )
    base.update(overrides)
    return BlackjackStats(**base)


def _identity() -> PlayerIdentity:
    return PlayerIdentity(nickname="Kasumi", level=12)


def test_stats_card_data_maps_every_service_field():
    from plugins.blackjack.stats_render import stats_card_data

    identity = _identity()
    data = stats_card_data(_stats(), identity)

    assert data.identity is identity
    assert data.total_games == 137
    assert data.wins == 57
    assert data.losses == 74
    assert data.pushes == 6
    assert data.blackjacks == 9
    assert data.win_rate == pytest.approx(57 / 137)
    assert data.total_wagered == 27400
    assert data.total_won == 18240
    assert data.total_lost == 19480
    assert data.net_profit == -1240
    assert data.avg_bet == pytest.approx(200.0)
    assert data.avg_win == pytest.approx(320.0)
    assert data.avg_loss == pytest.approx(263.2)
    assert data.biggest_win == 1200
    assert data.biggest_loss == 1000


@pytest.mark.parametrize(
    "kit_cls", [BanGDreamKit, KasumiKit, MinimalKit, MidnightKit]
)
def test_stats_card_renders_in_multiple_kits(kit_cls):
    from plugins.blackjack.stats_render import render_stats
    from plugins.blackjack.stats_render import stats_card_data

    data = stats_card_data(_stats(), _identity())
    image = render_stats(data, kit_cls())

    assert image.size[0] == CARD_WIDTH
    assert image.size[1] > 400


def test_stats_card_renders_with_positive_profit_and_no_level():
    from plugins.blackjack.stats_render import render_stats
    from plugins.blackjack.stats_render import stats_card_data

    stats = _stats(net_profit=1240, win_rate=1.0, losses=0, pushes=0, wins=137)
    data = stats_card_data(stats, PlayerIdentity(nickname="玩家1234", level=None))
    image = render_stats(data, MinimalKit())

    assert image.size[0] == CARD_WIDTH


def test_get_user_stats_counts_blackjacks(sqlite_session):
    from plugins.blackjack import database
    from plugins.blackjack.models import Base
    from plugins.blackjack.models import GameResult
    from plugins.blackjack.game_service import BlackjackGameService
    from plugins.blackjack.stats_service import get_blackjack_stats

    sqlite_session(database, Base)
    BlackjackGameService.record_game("u1", 20, GameResult.WIN, 20)
    BlackjackGameService.record_game("u1", 20, GameResult.BLACKJACK, 30)
    BlackjackGameService.record_game("u1", 20, GameResult.BUST, -20)
    BlackjackGameService.record_game("u1", 20, GameResult.PUSH, 0)

    raw = BlackjackGameService.get_user_stats("u1")
    assert raw["total_games"] == 4
    assert raw["wins"] == 2  # WIN + BLACKJACK
    assert raw["blackjacks"] == 1
    assert raw["losses"] == 1
    assert raw["pushes"] == 1

    stats = get_blackjack_stats("u1")
    assert stats.blackjacks == 1
    assert stats.wins == 2

    empty = BlackjackGameService.get_user_stats("nobody")
    assert empty["blackjacks"] == 0
    assert get_blackjack_stats("nobody").blackjacks == 0


def test_get_user_stats_can_be_limited_to_a_season(sqlite_session, monkeypatch):
    from plugins.blackjack import database
    from plugins.blackjack.models import Base
    from plugins.blackjack.models import GameResult
    from plugins.blackjack.game_service import BlackjackGameService
    from plugins.blackjack.stats_service import get_blackjack_stats

    sqlite_session(database, Base)
    timestamps = iter((99, 100, 199, 200))
    monkeypatch.setattr("plugins.blackjack.game_service.time.time", lambda: next(timestamps))
    for result, winnings in (
        (GameResult.WIN, 10),
        (GameResult.BLACKJACK, 15),
        (GameResult.BUST, -10),
        (GameResult.WIN, 10),
    ):
        BlackjackGameService.record_game("u1", 10, result, winnings)

    stats = get_blackjack_stats("u1", start_time=100, end_time=200)

    assert stats.total_games == 2
    assert stats.wins == 1
    assert stats.blackjacks == 1
    assert stats.recent_games[0].time == 199
