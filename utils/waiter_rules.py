"""Shared rules for message waiters used by interactive games."""

from collections.abc import Callable
from collections.abc import Awaitable
from collections.abc import Collection

from nonebot.adapters.satori import MessageEvent


def same_channel(channel_id: str) -> Callable[[MessageEvent], Awaitable[bool]]:
    """Build a waiter rule that ignores traffic from every other channel."""

    async def check(event: MessageEvent) -> bool:
        return event.channel.id == channel_id

    return check


def is_force_stop_message(message: str, commands: Collection[str]) -> bool:
    """Return whether a plain-text message is ``/<command> -f``."""

    parts = message.strip().lower().split()
    if len(parts) < 2 or parts[-1] != "-f":
        return False
    return parts[-2].lstrip("/") in commands
