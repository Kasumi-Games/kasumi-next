"""The product clock: every player-facing time is Beijing time.

The player base lives on QQ in UTC+8, but the bot may run on a server in any
timezone. Found in sandbox testing on a UTC+12 machine: ``datetime.now()`` /
``fromtimestamp()`` default to machine-local time, which shifted every
displayed season/mail time by four hours and — worse — moved the *check-in day
boundary* and the *daily-task day* to machine-local midnight instead of Beijing
midnight.

Rules:
- Any ``date()`` used as a day boundary (check-in streaks, daily tasks,
  birthdays) must come from :func:`bot_today` / :func:`bot_date`.
- Any timestamp shown to a player must go through :func:`format_ts`.
- Raw epoch comparisons (season start/end, expiry) are timezone-free and
  need nothing from this module.
"""

import datetime

#: The product timezone. Seasons.json carries "UTC+8" as well; if the product
#: ever moves, change both together.
BOT_TZ = datetime.timezone(datetime.timedelta(hours=8), name="UTC+8")


def bot_now() -> datetime.datetime:
    """Now, as an aware datetime in the product timezone."""

    return datetime.datetime.now(tz=BOT_TZ)


def bot_today() -> datetime.date:
    """Today's date at the product timezone's day boundary."""

    return bot_now().date()


def bot_date(timestamp: float) -> datetime.date:
    """The product-timezone date an epoch timestamp falls on."""

    return datetime.datetime.fromtimestamp(timestamp, tz=BOT_TZ).date()


def to_bot_time(timestamp: float) -> datetime.datetime:
    """An epoch timestamp as an aware datetime in the product timezone."""

    return datetime.datetime.fromtimestamp(timestamp, tz=BOT_TZ)


def format_ts(timestamp: float, fmt: str = "%Y-%m-%d %H:%M") -> str:
    """Format an epoch timestamp in the product timezone."""

    return to_bot_time(timestamp).strftime(fmt)


def tz_from_label(label: str) -> datetime.timezone:
    """Parse a ``UTC+8`` / ``UTC-5`` style label into a timezone.

    Falls back to :data:`BOT_TZ` on anything unparseable, because a malformed
    config label must never take a display path down.
    """

    try:
        if label.upper().startswith("UTC") and len(label) > 3:
            hours = float(label[3:])
            return datetime.timezone(datetime.timedelta(hours=hours), name=label)
    except (ValueError, TypeError):
        pass
    return BOT_TZ
