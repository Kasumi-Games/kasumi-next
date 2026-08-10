"""Persistence service for completed, failed and abandoned tour runs."""

from __future__ import annotations

import time

from sqlalchemy import and_
from sqlalchemy import func

from .models import TourOutcome
from .models import TourGameRecord
from .models import TourPreference
from .models import TourDisplayMode
from .session import TourSession
from .database import get_session


def record_result(
    session: TourSession,
    outcome: TourOutcome,
    reward_pt: int,
) -> TourGameRecord:
    db = get_session()
    existing = (
        db.query(TourGameRecord)
        .filter(TourGameRecord.run_id == session.run_id)
        .first()
    )
    if existing is not None:
        return existing
    record = TourGameRecord(
        run_id=session.run_id,
        user_id=session.user_id,
        difficulty=session.difficulty,
        outcome=outcome.value,
        tours_completed=session.tour_played_count,
        day=session.day,
        action_count=session.action_count,
        rest_count=session.rest_count,
        stamina_remaining=session.stamina,
        elapsed_seconds=session.elapsed_seconds(),
        reward_pt=reward_pt,
        seed=session.seed,
        timestamp=int(time.time()),
    )
    db.add(record)
    db.commit()
    return record


def get_leaderboard(
    difficulty: str,
    limit: int = 10,
    *,
    start_time: int | None = None,
    end_time: int | None = None,
) -> list[TourGameRecord]:
    """Return each player's fastest clear for one difficulty."""

    db = get_session()
    best_query = db.query(
        TourGameRecord.user_id.label("user_id"),
        func.min(TourGameRecord.elapsed_seconds).label("best_elapsed"),
    ).filter(
        TourGameRecord.difficulty == difficulty,
        TourGameRecord.outcome == TourOutcome.WIN.value,
    )
    if start_time is not None:
        best_query = best_query.filter(TourGameRecord.timestamp >= start_time)
    if end_time is not None:
        best_query = best_query.filter(TourGameRecord.timestamp < end_time)
    best_times = best_query.group_by(TourGameRecord.user_id).subquery()

    query = (
        db.query(TourGameRecord)
        .join(
            best_times,
            and_(
                TourGameRecord.user_id == best_times.c.user_id,
                TourGameRecord.elapsed_seconds == best_times.c.best_elapsed,
            ),
        )
        .filter(
            TourGameRecord.difficulty == difficulty,
            TourGameRecord.outcome == TourOutcome.WIN.value,
        )
        .order_by(
            TourGameRecord.elapsed_seconds.asc(),
            TourGameRecord.timestamp.asc(),
        )
    )
    if start_time is not None:
        query = query.filter(TourGameRecord.timestamp >= start_time)
    if end_time is not None:
        query = query.filter(TourGameRecord.timestamp < end_time)

    result: list[TourGameRecord] = []
    seen_users: set[str] = set()
    for row in query.all():
        if row.user_id in seen_users:
            continue
        seen_users.add(row.user_id)
        result.append(row)
        if len(result) >= limit:
            break
    return result


def get_display_mode(user_id: str) -> TourDisplayMode:
    db = get_session()
    preference = (
        db.query(TourPreference)
        .filter(TourPreference.user_id == user_id)
        .first()
    )
    if preference is None:
        return TourDisplayMode.IMAGE
    try:
        return TourDisplayMode(preference.display_mode)
    except ValueError:
        return TourDisplayMode.IMAGE


def set_display_mode(
    user_id: str,
    mode: TourDisplayMode | str,
) -> TourDisplayMode:
    db = get_session()
    resolved = TourDisplayMode(mode)
    preference = (
        db.query(TourPreference)
        .filter(TourPreference.user_id == user_id)
        .first()
    )
    if preference is None:
        preference = TourPreference(user_id=user_id, display_mode=resolved.value)
        db.add(preference)
    else:
        preference.display_mode = resolved.value
    db.commit()
    return resolved
