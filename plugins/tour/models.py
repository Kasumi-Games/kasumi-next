"""Pure tour value objects and the persisted terminal-run record."""

from __future__ import annotations

from enum import StrEnum
from dataclasses import dataclass

from sqlalchemy import Float
from sqlalchemy import Column
from sqlalchemy import String
from sqlalchemy import Integer
from sqlalchemy.ext.declarative import declarative_base


class CardType(StrEnum):
    TOUR = "tour"
    INSTRUMENT = "instrument"
    STAMINA = "stamina"


class TourOutcome(StrEnum):
    WIN = "win"
    STAMINA = "stamina"
    QUIT = "quit"
    TIMEOUT = "timeout"


class TourDisplayMode(StrEnum):
    IMAGE = "image"
    TEXT = "text"


@dataclass(frozen=True)
class TourCard:
    type: CardType
    value: int
    name: str


@dataclass(frozen=True)
class PerformedAction:
    kind: str
    card_name: str = ""
    card_value: int = 0
    amount: int = 0
    step: int = 0


@dataclass(frozen=True)
class ActionResult:
    changed: bool = False
    terminal: bool = False
    outcome: TourOutcome | None = None
    performed: tuple[PerformedAction, ...] = ()
    invalid_reason: str | None = None
    invalid_step: int | None = None
    ignored_suffix: str = ""


@dataclass(frozen=True)
class TourSnapshot:
    user_id: str
    run_id: str
    difficulty: str
    max_stamina: int
    stamina: int
    day: int
    tour_played_count: int
    selection_count: int
    rested_previous_day: bool
    stamina_used_today: bool
    hand: tuple[TourCard | None, ...]
    deck_size: int
    instrument: TourCard | None
    instrument_equipped: bool
    last_performance: int | None
    is_over: bool
    outcome: TourOutcome | None
    elapsed_seconds: float
    action_count: int
    rest_count: int


Base = declarative_base()


class TourPreference(Base):
    __tablename__ = "tour_preferences"

    user_id = Column(String, primary_key=True)
    display_mode = Column(String, nullable=False, default=TourDisplayMode.IMAGE.value)


class TourGameRecord(Base):
    __tablename__ = "tour_games"

    id = Column(Integer, primary_key=True, autoincrement=True)
    run_id = Column(String, unique=True, nullable=False, index=True)
    user_id = Column(String, nullable=False, index=True)
    difficulty = Column(String, nullable=False, index=True)
    outcome = Column(String, nullable=False)
    tours_completed = Column(Integer, nullable=False)
    day = Column(Integer, nullable=False)
    action_count = Column(Integer, nullable=False)
    rest_count = Column(Integer, nullable=False)
    stamina_remaining = Column(Integer, nullable=False)
    elapsed_seconds = Column(Float, nullable=False)
    reward_pt = Column(Integer, nullable=False)
    seed = Column(Integer, nullable=False)
    timestamp = Column(Integer, nullable=False)
