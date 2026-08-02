"""Live-test fixes for the three game plugins (one_stroke / mines / blackjack).

Three findings from the live Koishi run, pinned here so they stay fixed:

1. The one-stroke board background drifted between moves of the SAME game
   because the renderer re-rolled ``random.choice`` on every render. The pick
   is now a crc32 of the session's stable identity (player, channel, creation
   stamp), so every re-render of one game lands on the same file while a new
   game may differ.
2. The mines result card labeled sticker gains by their source
   (「星星贴纸 · 每日任务」). Gain labels name the thing; the task and
   level rows above the strip already carry the source.
3. The game identity strips shipped with the initial-badge fallback. Every
   ``identity_for`` call site in the three handlers now passes the cached
   avatar from ``utils.avatar.get_avatar``.
"""

from __future__ import annotations

import re
import importlib
from zlib import crc32
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

#: Matches an ``identity_for(...)`` call with up to one level of nested
#: parentheses in its arguments (``event.get_user_id()``, ``get_avatar(...)``).
_IDENTITY_CALL = re.compile(r"identity_for\((?:[^()]|\([^()]*\))*\)")


def _one_stroke_session():
    from plugins.one_stroke.models import Graph
    from plugins.one_stroke.session import GameSession

    graph = Graph(
        rows=2,
        cols=2,
        nodes={(0, 0), (0, 1), (1, 0), (1, 1)},
        edges={
            frozenset(((0, 0), (0, 1))),
            frozenset(((0, 0), (1, 0))),
        },
        start_node=(0, 0),
    )
    return GameSession(
        user_id="u1",
        channel_id="c1",
        difficulty_name="普通",
        reward=100,
        graph=graph,
    )


def test_one_stroke_created_at_survives_timer_resets_and_moves():
    session = _one_stroke_session()
    stamp = session.created_at
    session.restart_timer()
    session.move("D")
    session.reset()
    assert session.created_at == stamp


def test_one_stroke_background_index_is_crc32_of_stable_identity():
    from plugins.one_stroke.render import graph as graph_module

    session = _one_stroke_session()
    key = f"{session.user_id}:{session.channel_id}:{session.created_at}"
    assert graph_module._background_index(session, 7) == crc32(
        key.encode("utf-8")
    ) % 7
    for count in (1, 3, 12):
        index = graph_module._background_index(session, count)
        assert 0 <= index < count
        assert index == graph_module._background_index(session, count)


def test_one_stroke_background_is_stable_across_moves_of_one_game():
    from plugins.one_stroke.render import graph as graph_module
    from plugins.render.kits.bangdream import BanGDreamKit

    class RecordingKit(BanGDreamKit):
        def __init__(self):
            super().__init__()
            self.sources = []

        def background(self, source=None):
            self.sources.append(source)
            return source

    session = _one_stroke_session()
    kit = RecordingKit()

    graph_module._background(kit, session)
    session.restart_timer()  # the handler resets the timer after the first send
    graph_module._background(kit, session)
    session.move("D")
    graph_module._background(kit, session)
    session.reset()  # an "R" mid-game keeps the background too
    graph_module._background(kit, session)

    assert len(kit.sources) == 4
    assert kit.sources[0] is not None
    assert len(set(kit.sources)) == 1


def test_one_stroke_board_render_is_deterministic_for_one_game():
    from plugins.one_stroke.render import graph as graph_module
    from plugins.render.kits.bangdream import BanGDreamKit

    session = _one_stroke_session()
    # Freeze the live-reward clock so the title bar cannot differ between the
    # two renders; the board and background are what this test pins.
    session.elapsed_seconds = lambda: 1.0
    first = graph_module.render(session, kit=BanGDreamKit())
    second = graph_module.render(session, kit=BanGDreamKit())
    assert first.tobytes() == second.tobytes()


def test_mines_sticker_gains_are_labeled_by_the_thing():
    source = (ROOT / "plugins" / "mines" / "render" / "result.py").read_text(
        encoding="utf-8"
    )
    assert "星星贴纸 · " not in source
    assert '"星星贴纸"' in source


def test_mines_reward_panel_merges_sticker_gains_into_one_row():
    importlib.import_module("plugins.daily_task")
    from plugins.render.kits import KITS
    from plugins.mines.models import GameResult
    from plugins.mines.render.result import MinesResultData
    from plugins.mines.render.result import render_result

    def data(**overrides):
        base = dict(
            outcome=GameResult.CASHOUT,
            bet_amount=200,
            payout=1665,
            multiplier=8.33,
            revealed_count=8,
            safe_cells=20,
            mines=5,
            balance=3096,
        )
        base.update(overrides)
        return MinesResultData(**base)

    kit = KITS["minimal"]()
    bare = render_result(data(), kit)
    task_only = render_result(data(task_name="见好就收", task_reward=80), kit)
    task_and_level = render_result(
        data(
            task_name="见好就收",
            task_reward=80,
            old_level=41,
            new_level=42,
            level_stickers=120,
        ),
        kit,
    )
    # Each fired reward adds its own row; the sticker strip itself stays one
    # merged 「星星贴纸」 row rather than one row per source.
    assert bare.height < task_only.height < task_and_level.height


def test_game_handlers_fetch_the_cached_avatar_for_every_identity():
    handlers = {
        "plugins/one_stroke/__init__.py": [
            "avatar = await get_avatar(event.get_user_id())",
            "identity = identity_for(event.get_user_id(), avatar=avatar)",
            "identity_for(event.get_user_id(), avatar=avatar),",
        ],
        "plugins/mines/__init__.py": [
            "avatar = await get_avatar(event.get_user_id())",
            "identity = identity_for(event.get_user_id(), avatar=avatar)",
        ],
        "plugins/blackjack/__init__.py": [
            "avatar = await get_avatar(event.get_user_id())",
            "identity = identity_for(event.get_user_id(), avatar=avatar)",
            "identity_for(user_id, avatar=await get_avatar(user_id))",
        ],
    }
    for relative, snippets in handlers.items():
        source = (ROOT / relative).read_text(encoding="utf-8")
        assert "from utils.avatar import get_avatar" in source, relative
        for snippet in snippets:
            assert snippet in source, (relative, snippet)
        calls = _IDENTITY_CALL.findall(source)
        assert calls, relative
        for call in calls:
            assert "avatar=" in call, (relative, call)


def test_game_preview_surfaces_keep_the_player_identity_strip():
    """The visual census must exercise the same identity-bearing shape as live games."""

    source = (ROOT / "scripts" / "preview_renderers.py").read_text(encoding="utf-8")
    assert 'PlayerIdentity(nickname="香澄", level=42)' in source
    assert "generate_hand(\n        dealer,\n        second_card_back=True,\n        identity=identity," in source
    assert "generate_table(\n        dealer,\n        player,\n        dealer_card_back=True,\n        identity=identity," in source
    assert "field_module.render(\n        field,\n        kit=_kit(kit_name),\n        identity=identity," in source
    assert "graph_module.render(\n        session,\n        kit=_kit(kit_name),\n        identity=identity," in source


def test_blackjack_renderer_is_pinned_per_game_not_shared_globally():
    """Two waiting blackjack games must not overwrite each other's theme."""

    from plugins.blackjack.models import Hand
    from plugins.blackjack.session import GameManager

    default_renderer = object()
    kasumi_renderer = object()
    midnight_renderer = object()
    manager = GameManager(renderer=default_renderer)

    manager.create_session("kasumi", "c1", 100, Hand(), Hand(), kasumi_renderer)
    manager.create_session("midnight", "c2", 100, Hand(), Hand(), midnight_renderer)

    assert manager.renderer_for("kasumi") is kasumi_renderer
    assert manager.renderer_for("midnight") is midnight_renderer
    assert manager.renderer_for("no-active-game") is default_renderer


def test_blackjack_handlers_never_render_from_the_global_renderer():
    """Every table/hand path must resolve the renderer for its active player."""

    source = (ROOT / "plugins" / "blackjack" / "handlers.py").read_text(
        encoding="utf-8"
    )
    assert "game_manager.renderer." not in source
    assert "game_manager.renderer_for(" in source
