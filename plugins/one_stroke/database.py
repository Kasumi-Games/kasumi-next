from nonebot import require
from sqlalchemy import and_, create_engine, func
from sqlalchemy.orm import sessionmaker

require("nonebot_plugin_localstore")

import nonebot_plugin_localstore as store  # noqa: E402

from .models import Base, OneStrokeGame  # noqa: E402


database_path = store.get_data_file("one_stroke", "games.db")

session = None


def init_database() -> None:
    global session
    engine = create_engine(f"sqlite:///{database_path.resolve()}")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()


def get_session():
    global session
    if session is None:
        init_database()
    return session


def get_leaderboard(difficulty: str, limit: int = 10) -> list[OneStrokeGame]:
    db = get_session()

    best_time_subquery = (
        db.query(
            OneStrokeGame.user_id.label("user_id"),
            func.min(OneStrokeGame.elapsed_seconds).label("best_elapsed"),
        )
        .filter(OneStrokeGame.difficulty == difficulty)
        .group_by(OneStrokeGame.user_id)
        .subquery()
    )

    rows = (
        db.query(OneStrokeGame)
        .join(
            best_time_subquery,
            and_(
                OneStrokeGame.user_id == best_time_subquery.c.user_id,
                OneStrokeGame.elapsed_seconds == best_time_subquery.c.best_elapsed,
            ),
        )
        .filter(OneStrokeGame.difficulty == difficulty)
        .order_by(OneStrokeGame.elapsed_seconds.asc(), OneStrokeGame.timestamp.asc())
        .all()
    )

    # In tie cases, keep only one row per user.
    result: list[OneStrokeGame] = []
    seen_users: set[str] = set()
    for row in rows:
        if row.user_id in seen_users:
            continue
        seen_users.add(row.user_id)
        result.append(row)
        if len(result) >= limit:
            break
    return result
