"""Persistence service for completed, failed and abandoned tour runs."""

from __future__ import annotations

import time

from .models import TourOutcome
from .models import TourGameRecord
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
