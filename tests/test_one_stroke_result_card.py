"""OneStrokeResultCard: reward math, personal-best read, and rendering.

The card itself is pure — everything comes in through
``OneStrokeResultData`` — so most tests are direct assertions on the data
mapping helpers plus raster-level layout checks in every kit. The
personal-best query is exercised against an in-memory database.
"""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from utils import cards
from plugins.render import BaseKit
from plugins.render import PlayerIdentity
from plugins.one_stroke import database as one_stroke_database
from plugins.render.kits import KITS
from plugins.one_stroke.models import Base
from plugins.one_stroke.models import Graph
from plugins.one_stroke.models import OneStrokeGame
from plugins.one_stroke.database import get_personal_best
from plugins.render.kits.minimal import MinimalKit
from plugins.one_stroke.difficulty import apply_time_decay
from plugins.one_stroke.difficulty import time_decay_factor
from plugins.render.kits.bangdream import BanGDreamKit
from plugins.one_stroke.render.result import OneStrokeResultData
from plugins.one_stroke.render.result import record_text
from plugins.one_stroke.render.result import gain_entries
from plugins.one_stroke.render.result import render_result

IDENTITY = PlayerIdentity(nickname="香澄", level=12)

FULL_DATA = OneStrokeResultData(
    difficulty="普通",
    elapsed_seconds=12.47,
    base_reward=18,
    decay_factor=0.78,
    final_reward=28,
    balance=1204,
    birthday_characters=("户山香澄",),
    previous_best_seconds=15.32,
    is_new_record=True,
    task_name="笔走飞星",
    task_reward=80,
    old_level=12,
    new_level=13,
    level_stickers=120,
)

PLAIN_DATA = OneStrokeResultData(
    difficulty="困难",
    elapsed_seconds=88.02,
    base_reward=30,
    decay_factor=0.11,
    final_reward=3,
    balance=45,
    previous_best_seconds=40.0,
    is_new_record=False,
)


class GainEntriesTest(unittest.TestCase):
    def test_clear_reward_always_leads(self) -> None:
        self.assertEqual(gain_entries(PLAIN_DATA), [("+3 Pt", "通关奖励")])
        self.assertEqual(gain_entries(FULL_DATA)[0], ("+28 Pt", "通关奖励"))

    def test_task_and_level_gains_follow_when_present(self) -> None:
        self.assertEqual(
            gain_entries(FULL_DATA),
            [
                ("+28 Pt", "通关奖励"),
                ("+80 贴纸", "每日任务奖励"),
                ("+120 贴纸", "升级奖励"),
            ],
        )

    def test_task_fallback_without_reward_adds_no_gain(self) -> None:
        # The handler's degraded path: completion known, config unreadable.
        data = OneStrokeResultData(
            difficulty="普通",
            elapsed_seconds=30.0,
            base_reward=10,
            decay_factor=0.5,
            final_reward=5,
            balance=5,
            task_name="每日任务",
            task_reward=0,
        )
        self.assertEqual(gain_entries(data), [("+5 Pt", "通关奖励")])

    def test_no_emoji_reaches_the_card(self) -> None:
        # The bundled CJK font has no emoji glyphs; the shared services'
        # messages contain them, so the card must build its own strings.
        for amount, label in gain_entries(FULL_DATA):
            for ch in amount + label:
                self.assertLess(ord(ch), 0x1F000, f"emoji-range char {ch!r}")
        for ch in record_text(FULL_DATA):
            self.assertLess(ord(ch), 0x1F000)


class RecordTextTest(unittest.TestCase):
    def test_improvement_shows_old_and_new_time(self) -> None:
        self.assertEqual(record_text(FULL_DATA), "个人最佳 15.32 秒 → 12.47 秒")

    def test_first_clear_names_the_difficulty(self) -> None:
        data = OneStrokeResultData(
            difficulty="困难",
            elapsed_seconds=51.5,
            base_reward=30,
            decay_factor=0.3,
            final_reward=9,
            balance=9,
            previous_best_seconds=None,
            is_new_record=True,
        )
        self.assertEqual(record_text(data), "首次通关困难难度")

    def test_leveled_up_requires_both_levels(self) -> None:
        self.assertTrue(FULL_DATA.leveled_up)
        self.assertFalse(PLAIN_DATA.leveled_up)


class RenderTest(unittest.TestCase):
    def test_renders_in_every_kit(self) -> None:
        for name, factory in KITS.items():
            with self.subTest(kit=name):
                image = render_result(FULL_DATA, kit=factory(), identity=IDENTITY)
                self.assertEqual(
                    image.width, cards.CONTENT_WIDTH + 2 * cards.PAGE_PADDING
                )
                self.assertGreater(image.height, 0)

    def test_defaults_to_bangdream_kit_without_identity(self) -> None:
        image = render_result(PLAIN_DATA)
        self.assertGreater(image.width, 0)

    def test_conditional_rows_change_the_height(self) -> None:
        kit = MinimalKit()
        plain = render_result(PLAIN_DATA, kit=kit)

        with_record = OneStrokeResultData(
            difficulty=PLAIN_DATA.difficulty,
            elapsed_seconds=PLAIN_DATA.elapsed_seconds,
            base_reward=PLAIN_DATA.base_reward,
            decay_factor=PLAIN_DATA.decay_factor,
            final_reward=PLAIN_DATA.final_reward,
            balance=PLAIN_DATA.balance,
            previous_best_seconds=90.0,
            is_new_record=True,
        )
        self.assertGreater(
            render_result(with_record, kit=kit).height, plain.height
        )

        self.assertGreater(
            render_result(FULL_DATA, kit=kit, identity=IDENTITY).height,
            plain.height,
        )

    def test_identity_strip_goes_through_the_tier_a_dispatcher(self) -> None:
        for base in (BanGDreamKit, MinimalKit):

            class CountingKit(base):  # type: ignore[misc, valid-type]
                def __init__(self) -> None:
                    super().__init__()
                    self.game_identity_calls = 0

                def game_identity(self, identity, *, width, detail=None):
                    self.game_identity_calls += 1
                    return cards._generic_game_identity(
                        self, identity, width=width, detail=detail
                    )

            kit: BaseKit = CountingKit()
            render_result(FULL_DATA, kit=kit)
            self.assertEqual(kit.game_identity_calls, 0)
            render_result(FULL_DATA, kit=kit, identity=IDENTITY)
            self.assertEqual(kit.game_identity_calls, 1)


class PersonalBestTest(unittest.TestCase):
    def setUp(self) -> None:
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine)
        one_stroke_database.session = sessionmaker(bind=engine)()

    def tearDown(self) -> None:
        one_stroke_database.session.close()
        one_stroke_database.session = None

    @staticmethod
    def _game(user_id: str, difficulty: str, elapsed: float) -> OneStrokeGame:
        return OneStrokeGame(
            user_id=user_id,
            difficulty=difficulty,
            elapsed_seconds=elapsed,
            reward=10,
            base_reward=10,
            timestamp=1_700_000_000,
        )

    def test_none_without_history(self) -> None:
        self.assertIsNone(get_personal_best("u1", "普通"))

    def test_minimum_per_user_and_difficulty(self) -> None:
        db = one_stroke_database.session
        db.add(self._game("u1", "普通", 30.5))
        db.add(self._game("u1", "普通", 12.3))
        db.add(self._game("u1", "困难", 5.0))
        db.add(self._game("u2", "普通", 1.0))
        db.commit()

        self.assertEqual(get_personal_best("u1", "普通"), 12.3)
        self.assertEqual(get_personal_best("u1", "困难"), 5.0)
        self.assertIsNone(get_personal_best("u2", "困难"))


class DecayFactorTest(unittest.TestCase):
    @staticmethod
    def _graph() -> Graph:
        return Graph(
            rows=4,
            cols=4,
            nodes={(r, c) for r in range(4) for c in range(4)},
            edges={
                frozenset(((0, 0), (0, 1))),
                frozenset(((0, 1), (0, 2))),
            },
            start_node=(0, 0),
        )

    def test_factor_matches_apply_time_decay(self) -> None:
        graph = self._graph()
        for elapsed in (0.0, 3.0, 6.5, 20.0, 120.0):
            factor = time_decay_factor(elapsed, graph)
            self.assertEqual(
                apply_time_decay(
                    base_reward=100, elapsed_seconds=elapsed, graph=graph
                ),
                max(0, int(round(100 * factor))),
            )

    def test_factor_is_one_within_the_grace_delay(self) -> None:
        self.assertEqual(time_decay_factor(0.0, self._graph()), 1.0)


if __name__ == "__main__":
    unittest.main()
