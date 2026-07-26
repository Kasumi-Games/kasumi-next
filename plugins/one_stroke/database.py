from nonebot import require
from sqlalchemy import and_
from sqlalchemy import func
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

require("nonebot_plugin_localstore")

import nonebot_plugin_localstore as store  # noqa: E402

from .models import Base  # noqa: E402
from .models import OneStrokeGame  # noqa: E402

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


def get_personal_best(user_id: str, difficulty: str) -> float | None:
    """The player's fastest clear on one difficulty, or ``None``.

    Read-only. The result card queries it *before* the finished round is
    recorded, so a run is compared against the player's history and a first
    clear reads as ``None`` rather than as its own record.
    """

    db = get_session()
    best = (
        db.query(func.min(OneStrokeGame.elapsed_seconds))
        .filter(
            OneStrokeGame.user_id == user_id,
            OneStrokeGame.difficulty == difficulty,
        )
        .scalar()
    )
    return float(best) if best is not None else None


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
