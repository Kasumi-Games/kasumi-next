import sys
import datetime
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from utils import clock

#: 2026-07-26 23:59 Beijing == 2026-07-26 15:59 UTC.
BEFORE_MIDNIGHT = datetime.datetime(
    2026, 7, 26, 15, 59, tzinfo=datetime.timezone.utc
).timestamp()

#: 2026-07-27 00:01 Beijing == 2026-07-26 16:01 UTC.
AFTER_MIDNIGHT = datetime.datetime(
    2026, 7, 26, 16, 1, tzinfo=datetime.timezone.utc
).timestamp()


class ClockTest(unittest.TestCase):
    """Machine-timezone independence: every assertion here uses fixed epochs,
    so the suite proves the same behavior on a UTC, +8, or +12 server."""

    def test_format_ts_renders_beijing_time(self) -> None:
        self.assertEqual(clock.format_ts(BEFORE_MIDNIGHT), "2026-07-26 23:59")
        self.assertEqual(clock.format_ts(AFTER_MIDNIGHT), "2026-07-27 00:01")

    def test_day_boundary_flips_at_beijing_midnight(self) -> None:
        # The bug this module exists for: on a UTC+12 machine these two
        # timestamps are 03:59 and 04:01 on the SAME local day, and local
        # date() put them on one check-in day.
        self.assertEqual(clock.bot_date(BEFORE_MIDNIGHT).day, 26)
        self.assertEqual(clock.bot_date(AFTER_MIDNIGHT).day, 27)

    def test_bot_now_is_aware_and_utc8(self) -> None:
        now = clock.bot_now()
        self.assertIsNotNone(now.tzinfo)
        self.assertEqual(
            now.utcoffset(), datetime.timedelta(hours=8)
        )

    def test_to_bot_time_round_trips(self) -> None:
        aware = clock.to_bot_time(AFTER_MIDNIGHT)
        self.assertEqual(aware.timestamp(), AFTER_MIDNIGHT)
        self.assertEqual(aware.hour, 0)
        self.assertEqual(aware.minute, 1)

    def test_tz_from_label(self) -> None:
        self.assertEqual(
            clock.tz_from_label("UTC+8").utcoffset(None),
            datetime.timedelta(hours=8),
        )
        self.assertEqual(
            clock.tz_from_label("UTC-5").utcoffset(None),
            datetime.timedelta(hours=-5),
        )
        # Malformed labels degrade to the product default, never raise.
        self.assertEqual(
            clock.tz_from_label("garbage").utcoffset(None),
            datetime.timedelta(hours=8),
        )


class CheckinBoundaryTest(unittest.TestCase):
    """The behavioral sites use the clock: check-in duplicates are judged on
    Beijing days."""

    def test_checkin_dates_straddle_beijing_midnight(self) -> None:
        # Same pair of instants: distinct check-in days product-wise.
        self.assertNotEqual(
            clock.bot_date(BEFORE_MIDNIGHT), clock.bot_date(AFTER_MIDNIGHT)
        )

    def test_daily_and_monetary_use_the_clock(self) -> None:
        daily_src = Path("plugins/daily/__init__.py").read_text(encoding="utf-8")
        monetary_src = Path("plugins/monetary/user_service.py").read_text(
            encoding="utf-8"
        )
        for source, name in ((daily_src, "daily"), (monetary_src, "monetary")):
            with self.subTest(plugin=name):
                self.assertIn("bot_today()", source)
                self.assertIn("bot_date(", source)
                self.assertNotIn("datetime.now().date()", source)

    def test_no_machine_local_formatting_remains(self) -> None:
        # The whole class of bug, pinned: no plugin/util formats a player-
        # facing time via machine-local conversion.
        offenders = []
        for path in Path("plugins").rglob("*.py"):
            if "__pycache__" in str(path):
                continue
            source = path.read_text(encoding="utf-8")
            if "time.localtime(" in source:
                offenders.append(str(path))
            if "fromtimestamp(" in source and "tz=" not in source:
                offenders.append(str(path))
        self.assertEqual(offenders, [])


if __name__ == "__main__":
    unittest.main()
