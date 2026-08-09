"""Deterministic tour state machine and process-local session manager."""

from __future__ import annotations

import time
import uuid
import secrets
from typing import Dict
from typing import Optional

from .rules import TOUR_NAMES
from .rules import STAMINA_NAMES
from .rules import INSTRUMENT_NAMES
from .rules import TourDifficultyConfig
from .rules import parse_action
from .models import CardType
from .models import TourCard
from .models import TourOutcome
from .models import ActionResult
from .models import TourSnapshot
from .models import PerformedAction


class TourSession:
    def __init__(
        self,
        user_id: str,
        config: TourDifficultyConfig,
        *,
        seed: int | None = None,
        run_id: str | None = None,
    ) -> None:
        import random

        self.user_id = user_id
        self.config = config
        self.seed = seed if seed is not None else secrets.randbits(63)
        self.run_id = run_id or uuid.uuid4().hex
        self.rng = random.Random(self.seed)
        self.day = 1
        self.hand: list[TourCard | None] = []
        self.deck = self._build_deck()
        self.rng.shuffle(self.deck)
        self.instrument: TourCard | None = None
        self.instrument_equipped = False
        self.last_performance: dict[int, int] = {}
        self.tour_played_count = 0
        self.selection_count = 0
        self.rested_previous_day = False
        self.stamina_used_today = False
        self.stamina = config.initial_stamina
        self.is_over = False
        self.outcome: TourOutcome | None = None
        self.started_at = time.monotonic()
        self.action_count = 0
        self.rest_count = 0
        self.settlement_done = False
        self.settlement_base_reward_pt = 0
        self.settlement_reward_pt = 0
        self.settlement_birthday_names: tuple[str, ...] = ()
        self.settlement_multiplier = 1
        self._draw_cards(4)

    @property
    def difficulty(self) -> str:
        return self.config.key

    @property
    def max_stamina(self) -> int:
        return self.config.initial_stamina

    def elapsed_seconds(self) -> float:
        return max(0.0, time.monotonic() - self.started_at)

    def _build_deck(self) -> list[TourCard]:
        deck: list[TourCard] = []
        for value in range(2, 15):
            for _ in range(2):
                deck.append(TourCard(CardType.TOUR, value, self.rng_choice(TOUR_NAMES)))
        for value in range(2, 11):
            deck.append(
                TourCard(CardType.INSTRUMENT, value, self.rng_choice(INSTRUMENT_NAMES))
            )
        for value in range(2, 11):
            deck.append(
                TourCard(CardType.STAMINA, value, self.rng_choice(STAMINA_NAMES))
            )
        return deck

    def rng_choice(self, values: tuple[str, ...]) -> str:
        return self.rng.choice(values)

    def _draw_cards(self, count: int) -> None:
        for _ in range(count):
            if not self.deck:
                return
            for index, card in enumerate(self.hand):
                if card is None:
                    self.hand[index] = self.deck.pop()
                    break
            else:
                if len(self.hand) < 4:
                    self.hand.append(self.deck.pop())

    def _advance_day_if_needed(self) -> bool:
        if self.selection_count != 3:
            return False
        self.selection_count = 0
        self.day += 1
        self.rested_previous_day = False
        self.stamina_used_today = False
        self._draw_cards(3)
        return True

    def _tour_action(self, index: int, step: int) -> tuple[PerformedAction | None, str | None]:
        card = self.hand[index]
        if card is None:
            return None, "empty_slot"
        cost = card.value
        if self.instrument is not None and self.instrument_equipped:
            last = self.last_performance.get(self.instrument.value)
            if last is not None and last <= card.value:
                return None, "low_compatibility"
            cost = max(0, card.value - self.instrument.value)
        self.hand[index] = None
        self.selection_count += 1
        self.action_count += 1
        self.rested_previous_day = False
        self.stamina -= cost
        if self.stamina > self.max_stamina:
            self.stamina = self.max_stamina
        if self.instrument is not None and self.instrument_equipped:
            self.last_performance[self.instrument.value] = card.value
        self.tour_played_count += 1
        event = PerformedAction(
            kind="tour",
            card_name=card.name,
            card_value=card.value,
            amount=cost,
            step=step,
        )
        if self.stamina <= 0:
            self.mark_terminal(TourOutcome.STAMINA)
            return event, None
        if self.tour_played_count >= 26:
            self.mark_terminal(TourOutcome.WIN)
            return event, None
        self._advance_day_if_needed()
        return event, None

    def _select_card(self, number: int, step: int) -> tuple[PerformedAction | None, str | None]:
        index = number - 1
        if index < 0 or index >= len(self.hand) or self.hand[index] is None:
            return None, "empty_slot"
        card = self.hand[index]
        assert card is not None
        if card.type is CardType.TOUR:
            return self._tour_action(index, step)

        self.hand[index] = None
        self.selection_count += 1
        self.action_count += 1
        self.rested_previous_day = False
        if card.type is CardType.INSTRUMENT:
            self.instrument = card
            self.instrument_equipped = True
            event = PerformedAction(
                kind="instrument", card_name=card.name, card_value=card.value, step=step
            )
        else:
            restored = 0
            if not self.stamina_used_today:
                old = self.stamina
                self.stamina = min(self.max_stamina, self.stamina + card.value)
                restored = self.stamina - old
                self.stamina_used_today = True
            event = PerformedAction(
                kind="food", card_name=card.name, card_value=card.value, amount=restored, step=step
            )
        self._advance_day_if_needed()
        return event, None

    def _toggle_instrument(self) -> tuple[PerformedAction | None, str | None]:
        if self.instrument is None:
            return None, "no_instrument"
        if self.config.allow_unequip:
            self.instrument_equipped = not self.instrument_equipped
            status = "装备" if self.instrument_equipped else "卸下"
            return PerformedAction(kind="instrument_toggle", card_name=f"已{status}乐器"), None
        self.instrument = None
        self.instrument_equipped = False
        return PerformedAction(kind="instrument_toggle", card_name="已丢弃乐器"), None

    def _rest(self) -> ActionResult:
        if self.rested_previous_day:
            return ActionResult(invalid_reason="rest_consecutive")
        if self.selection_count > 0:
            return ActionResult(invalid_reason="rest_after_action")
        cards = [card for card in self.hand if card is not None]
        self.rng.shuffle(cards)
        self.deck = cards + self.deck
        self.hand = []
        self._draw_cards(4)
        self.day += 1
        self.selection_count = 0
        self.rested_previous_day = True
        self.stamina_used_today = False
        self.action_count += 1
        self.rest_count += 1
        return ActionResult(
            changed=True,
            performed=(PerformedAction(kind="rest"),),
        )

    def apply(self, raw: str) -> ActionResult:
        if self.is_over:
            return ActionResult(invalid_reason="game_over")
        if self.stamina <= 0:
            self.mark_terminal(TourOutcome.STAMINA)
            return ActionResult(terminal=True, outcome=self.outcome)
        command = parse_action(raw)
        if command.kind == "invalid":
            return ActionResult(invalid_reason="invalid_input")
        if command.kind == "quit":
            self.mark_terminal(TourOutcome.QUIT)
            return ActionResult(changed=True, terminal=True, outcome=self.outcome)
        if command.kind == "rest":
            return self._rest()

        performed: list[PerformedAction] = []
        ignored_suffix = ""
        invalid_reason = None
        invalid_step = None
        for position, char in enumerate(command.digits, start=1):
            before_selection = self.selection_count
            if char == "0":
                event, error = self._toggle_instrument()
            else:
                event, error = self._select_card(int(char), position)
            if event is not None:
                performed.append(event)
            if error is not None:
                invalid_reason = error
                invalid_step = position
                ignored_suffix = command.digits[position:]
                break
            if self.is_over:
                ignored_suffix = command.digits[position:]
                break
            if before_selection > 0 and self.selection_count == 0:
                ignored_suffix = command.digits[position:]
                invalid_step = position
                break

        return ActionResult(
            changed=bool(performed),
            terminal=self.is_over,
            outcome=self.outcome,
            performed=tuple(performed),
            invalid_reason=invalid_reason,
            invalid_step=invalid_step,
            ignored_suffix=ignored_suffix,
        )

    def mark_terminal(self, outcome: TourOutcome | str) -> None:
        self.is_over = True
        self.outcome = TourOutcome(outcome)

    def snapshot(self) -> TourSnapshot:
        last = None
        if self.instrument is not None:
            last = self.last_performance.get(self.instrument.value)
        return TourSnapshot(
            user_id=self.user_id,
            run_id=self.run_id,
            difficulty=self.difficulty,
            max_stamina=self.max_stamina,
            stamina=self.stamina,
            day=self.day,
            tour_played_count=self.tour_played_count,
            selection_count=self.selection_count,
            rested_previous_day=self.rested_previous_day,
            stamina_used_today=self.stamina_used_today,
            hand=tuple(self.hand),
            deck_size=len(self.deck),
            instrument=self.instrument,
            instrument_equipped=self.instrument_equipped,
            last_performance=last,
            is_over=self.is_over,
            outcome=self.outcome,
            elapsed_seconds=self.elapsed_seconds(),
            action_count=self.action_count,
            rest_count=self.rest_count,
        )

class TourGameManager:
    def __init__(self) -> None:
        self._sessions: Dict[str, TourSession] = {}

    def is_in_game(self, user_id: str) -> bool:
        return user_id in self._sessions

    def start(
        self,
        user_id: str,
        config: TourDifficultyConfig,
        *,
        seed: int | None = None,
    ) -> Optional[TourSession]:
        if self.is_in_game(user_id):
            return None
        session = TourSession(user_id, config, seed=seed)
        self._sessions[user_id] = session
        return session

    def get(self, user_id: str) -> Optional[TourSession]:
        return self._sessions.get(user_id)

    def end(self, user_id: str) -> Optional[TourSession]:
        return self._sessions.pop(user_id, None)

    def active_sessions(self) -> tuple[TourSession, ...]:
        return tuple(self._sessions.values())
