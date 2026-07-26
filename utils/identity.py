"""Handler-side assembly of :class:`~plugins.render.PlayerIdentity`.

The Tier A surfaces (game identity strip, player card, gacha reveal) all need
the same three facts about a player. This module is the one place that gathers
them, so three game plugins and the profile command do not each grow their own
copy.

Same rules as ``utils.theming``: call from the event loop thread only (the
inventory/monetary sessions are process-global and not thread safe), never
raise, never write. On any failure the returned identity degrades — a missing
nickname becomes the user id tail, a missing level becomes ``None`` — because
an identity strip must never be the reason a game board fails to render.

Avatars are deliberately not fetched here: the only existing avatar path
(``plugins.bang_avatar.utils.get_group_member_head``) downloads per call with
no cache, which is unacceptable on a surface that renders once per game move.
Callers that already hold an avatar image pass it via ``avatar=``.
"""

from nonebot.log import logger

from plugins.render import PlayerIdentity
from plugins.render.types import ImageSource


def identity_for(
    user_id: str,
    *,
    avatar: ImageSource | None = None,
) -> PlayerIdentity:
    """Assemble a player's identity for rendering. Never raises.

    Args:
        user_id: Player id.
        avatar: Optional avatar image the caller already holds.

    Returns:
        Identity with the best data available.
    """

    return PlayerIdentity(
        nickname=_nickname(user_id),
        level=_level(user_id),
        avatar=avatar,
    )


def _nickname(user_id: str) -> str:
    try:
        from plugins.nickname import get

        nickname = get(user_id)
    except Exception:
        logger.opt(exception=True).warning("nickname unavailable for identity")
        nickname = None
    if nickname:
        return str(nickname)
    # A recognizable stand-in beats an empty strip: the id tail is what group
    # members see in @-mentions when no nickname is set.
    return f"玩家{user_id[-4:]}" if len(user_id) >= 4 else f"玩家{user_id}"


def _level(user_id: str) -> int | None:
    try:
        from plugins import monetary

        return int(monetary.get_level(user_id))
    except Exception:
        logger.opt(exception=True).warning("level unavailable for identity")
        return None
