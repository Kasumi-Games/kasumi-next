"""Render tests for the mines Tier B cards (result + stats).

These exercise the two new render modules with handler-shaped data only: no
database, no event loop, no matcher. The handler-side wiring is covered by
source-level assertions at the bottom, which pin the hard rules the batch was
built against (renderers never touch the DB, no emoji reaches a card, the
matplotlib chart is gone from this flow).
"""

from __future__ import annotations

import re
import importlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _load_plugin_dependencies(*module_names: str) -> None:
    for module_name in module_names:
        importlib.import_module(module_name)


def _result_data(**overrides):
    _load_plugin_dependencies("plugins.daily_task")
    from plugins.mines.models import GameResult
    from plugins.mines.render.result import MinesResultData

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


def _stats(records):
    from plugins.mines.stats_service import MinesStats

    wins = sum(1 for record in records if record.amount > 0)
    losses = sum(1 for record in records if record.amount < 0)
    total = len(records)
    return MinesStats(
        user_id="u1",
        total_games=total,
        wins=wins,
        losses=losses,
        win_rate=wins / total if total else 0.0,
        total_wagered=200 * total,
        total_won=sum(r.amount for r in records if r.amount > 0),
        total_lost=abs(sum(r.amount for r in records if r.amount < 0)),
        net_profit=sum(r.amount for r in records),
        avg_bet=200.0,
        avg_win=320.0,
        avg_loss=208.1,
        biggest_win=1200,
        biggest_loss=1000,
        recent_games=records,
    )


def _records(amounts):
    from plugins.mines.stats_service import MinesGameRecord

    return [
        MinesGameRecord(
            time=1_700_000_000 - index * 3600,
            amount=amount,
            is_win=amount > 0,
            bet_amount=200,
            mines=5,
            revealed_count=4,
        )
        for index, amount in enumerate(amounts)
    ]


def _identity():
    from plugins.render import PlayerIdentity

    return PlayerIdentity(nickname="香澄", level=42)


def test_result_card_measures_in_every_kit():
    _load_plugin_dependencies("plugins.daily_task")
    from plugins.render.core import Constraints
    from plugins.render.core import RenderContext
    from plugins.render.kits import KITS
    from plugins.mines.models import GameResult
    from plugins.mines.render.result import result_page

    full = _result_data(
        task_name="见好就收",
        task_reward=80,
        old_level=41,
        new_level=42,
        level_stickers=120,
    )
    loss = _result_data(
        outcome=GameResult.LOSE, payout=0, multiplier=3.32, balance=1231
    )
    ctx = RenderContext()
    constraints = Constraints(max_width=2000, max_height=6000)
    for name, factory in KITS.items():
        kit = factory()
        for data in (full, loss):
            page = result_page(data, kit, identity=_identity())
            size = page.child.measure(ctx, constraints)
            assert size.width > 0, name
            assert size.height > 0, name


def test_result_card_renders_and_is_deterministic():
    from plugins.render.kits import KITS
    from plugins.mines.render.result import render_result

    kit = KITS["minimal"]()
    data = _result_data()
    first = render_result(data, kit, identity=_identity())
    second = render_result(data, kit, identity=_identity())
    assert first.width == second.width
    assert first.tobytes() == second.tobytes()


def test_result_card_renders_without_identity_or_rewards():
    from plugins.render.kits import KITS
    from plugins.mines.render.result import render_result

    image = render_result(_result_data(), KITS["midnight"]())
    assert image.width > 0
    assert image.height > 0


def test_reward_rows_only_render_when_they_fired():
    from plugins.render.kits import KITS
    from plugins.mines.render.result import render_result

    kit = KITS["minimal"]()
    bare = render_result(_result_data(), kit, identity=_identity())
    rewarded = render_result(
        _result_data(
            task_name="见好就收",
            task_reward=80,
            old_level=41,
            new_level=42,
            level_stickers=120,
        ),
        kit,
        identity=_identity(),
    )
    assert rewarded.height > bare.height


def test_win_and_loss_result_cards_differ_in_the_monochrome_kit():
    from plugins.render.kits import KITS
    from plugins.mines.models import GameResult
    from plugins.mines.render.result import render_result

    kit_win = KITS["manga"]()
    kit_loss = KITS["manga"]()
    win = render_result(_result_data(), kit_win, identity=_identity())
    loss = render_result(
        _result_data(outcome=GameResult.LOSE, payout=0, balance=1231),
        kit_loss,
        identity=_identity(),
    )
    assert win.tobytes() != loss.tobytes()


def test_result_data_net_and_positivity():
    from plugins.mines.models import GameResult

    assert _result_data().net == 1465
    assert _result_data().positive is True
    lose = _result_data(outcome=GameResult.LOSE, payout=0)
    assert lose.net == -200
    assert lose.positive is False
    win = _result_data(outcome=GameResult.WIN)
    assert win.positive is True


def test_stats_card_measures_in_every_kit():
    _load_plugin_dependencies("plugins.daily_task")
    from plugins.render.core import Constraints
    from plugins.render.core import RenderContext
    from plugins.render.kits import KITS
    from plugins.mines.render.stats import stats_page

    stats = _stats(_records([120, -200, 0, 340, -80, 900, -60]))
    ctx = RenderContext()
    constraints = Constraints(max_width=2000, max_height=6000)
    for name, factory in KITS.items():
        page = stats_page(stats, factory())
        size = page.child.measure(ctx, constraints)
        assert size.width > 0, name
        assert size.height > 0, name


def test_stats_card_renders_and_is_deterministic():
    from plugins.render.kits import KITS
    from plugins.mines.render.stats import render_stats

    kit = KITS["minimal"]()
    stats = _stats(_records([120, -200, 340]))
    first = render_stats(stats, kit)
    second = render_stats(stats, kit)
    assert first.tobytes() == second.tobytes()


def test_stats_card_renders_without_recent_games():
    from plugins.render.kits import KITS
    from plugins.mines.render.stats import render_stats

    stats = _stats(_records([120, -200, 340]))
    without = _stats([])
    kit = KITS["minimal"]()
    with_strip = render_stats(stats, kit)
    bare = render_stats(without, kit)
    assert bare.height < with_strip.height


def test_stats_form_strip_caps_at_thirty_slots():
    from plugins.mines.render import stats as stats_module

    records = _records([100] * 45)
    assert len(list(reversed(records))[-stats_module._FORM_SLOTS :]) == 30
    # 30 cells at 20px with 4px gaps must fit the 720px panel interior.
    strip_width = (
        stats_module._FORM_SLOTS * stats_module._FORM_CELL_WIDTH
        + (stats_module._FORM_SLOTS - 1) * stats_module._FORM_CELL_GAP
    )
    from utils import cards

    assert strip_width <= cards.INNER_WIDTH


def test_stats_form_uses_fixed_semantic_green_and_red_in_every_theme():
    from plugins.mines.render import stats as stats_module

    assert stats_module.WIN_COLOR == (54, 179, 111, 255)
    assert stats_module.LOSS_COLOR == (229, 75, 83, 255)
    assert stats_module.WIN_COLOR != stats_module.LOSS_COLOR


def test_render_modules_never_touch_the_database():
    for module in ("result", "stats"):
        source = (ROOT / "plugins" / "mines" / "render" / f"{module}.py").read_text(
            encoding="utf-8"
        )
        assert "get_session" not in source, module
        assert ".query(" not in source, module
        assert "from ..database" not in source, module


def test_no_emoji_reaches_a_mines_card():
    # The bundled CJK font has no emoji glyphs; any emoji routed into a card
    # renders as an empty box (hard rule 4 for this batch).
    emoji = re.compile(
        "[\U0001f000-\U0001faff\U00002700-\U000027bf\U0001f900-\U0001f9ff"
        "\U00002600-\U000026ff\U0000fe0f]"
    )
    for module in ("result", "stats", "field"):
        source = (ROOT / "plugins" / "mines" / "render" / f"{module}.py").read_text(
            encoding="utf-8"
        )
        assert not emoji.search(source), module


def test_matplotlib_is_gone_from_the_mines_flow():
    plugin_root = ROOT / "plugins" / "mines"
    for path in plugin_root.rglob("*.py"):
        source = path.read_text(encoding="utf-8")
        assert "import matplotlib" not in source, path
        assert "pyplot" not in source, path
        assert "create_win_loss_chart" not in source, path


def test_end_flow_sends_the_board_and_one_result_card():
    source = (ROOT / "plugins" / "mines" / "__init__.py").read_text(encoding="utf-8")
    # Each of the three end paths sends the revealed board, then exactly one
    # result card via the shared helper.
    assert source.count("_send_result_card(") >= 4  # def + three call sites
    # The old three-message tail is gone from the handler.
    assert "task_msg + gens" not in source
    assert "level_msg + gens" not in source
