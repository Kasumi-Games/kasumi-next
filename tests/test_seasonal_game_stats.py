"""Game-record queries must respect a season's start/end boundary."""


def test_mines_stats_can_be_limited_to_a_season(sqlite_session):
    from plugins.mines import database
    from plugins.mines.models import Base
    from plugins.mines.models import MinesGame
    from plugins.mines.stats_service import get_mines_stats

    session = sqlite_session(database, Base)
    session.add_all(
        [
            MinesGame(
                user_id="u1", bet_amount=10, mines=3, revealed_count=1,
                result="lose", winnings=-10, timestamp=99,
            ),
            MinesGame(
                user_id="u1", bet_amount=20, mines=3, revealed_count=4,
                result="cashout", winnings=20, timestamp=100,
            ),
            MinesGame(
                user_id="u1", bet_amount=30, mines=3, revealed_count=2,
                result="lose", winnings=-30, timestamp=199,
            ),
            MinesGame(
                user_id="u1", bet_amount=40, mines=3, revealed_count=5,
                result="cashout", winnings=40, timestamp=200,
            ),
        ]
    )
    session.commit()

    stats = get_mines_stats("u1", start_time=100, end_time=200)

    assert stats.total_games == 2
    assert stats.wins == 1
    assert stats.losses == 1
    assert stats.total_wagered == 50
    assert [game.time for game in stats.recent_games] == [199, 100]
