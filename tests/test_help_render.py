from __future__ import annotations

import pytest

from plugins.help import HELP_ENTRIES
from plugins.help import plugin_data
from plugins.help.render import render_board
from plugins.help.render import render_detail
from plugins.render.kits import KITS
from plugins.help.entries import entries_from
from plugins.help.entries import find_entries
from plugins.help.entries import suggest_names
from plugins.help.entries import total_commands
from plugins.help.entries import commands_by_category


def test_every_documented_plugin_becomes_an_entry() -> None:
    assert len(HELP_ENTRIES) == len(plugin_data)
    assert [entry.name for entry in HELP_ENTRIES] == list(plugin_data)


def test_every_entry_has_at_least_one_command() -> None:
    for entry in HELP_ENTRIES:
        assert entry.commands, f"{entry.name} produced no command"
        assert all(command.command for command in entry.commands)


def test_alias_forms_fold_into_one_command() -> None:
    # "/黑香澄", "/黑香澄 <数量>" and "/黑香澄 -h" are one command with two
    # argument forms; "/黑香澄统计" is a second command.
    entry = find_entries(HELP_ENTRIES, "黑香澄")[0]
    assert [command.command for command in entry.commands] == ["/黑香澄", "/黑香澄统计"]
    assert "-h" in entry.commands[0].aliases

    # A bare sub-trigger belongs to the plugin's first command.
    mail = find_entries(HELP_ENTRIES, "猜卡面")[0]
    assert len(mail.commands) == 1
    assert "bzd" in mail.commands[0].aliases


def test_enumerations_move_from_prose_to_params() -> None:
    entry = find_entries(HELP_ENTRIES, "猜卡面")[0]
    labels = dict(entry.params)
    assert len(labels["难度"]) == 12
    assert "超级猫猫" in labels["难度"]
    # The sentence that listed them is trimmed so the card does not say it twice.
    assert all("可选为" not in meaning for _, meaning in entry.usage)


def test_a_single_value_stays_in_the_sentence() -> None:
    entry = find_entries(HELP_ENTRIES, "猜谱面")[0]
    assert "谱面难度" not in dict(entry.params)
    assert any("1-30" in meaning for _, meaning in entry.usage)


def test_inline_parameter_sets_are_recovered() -> None:
    entry = find_entries(HELP_ENTRIES, "一笔画")[0]
    assert dict(entry.params)["难度"] == ("简单", "普通", "困难")


def test_every_command_lands_in_exactly_one_category() -> None:
    grouped = commands_by_category(HELP_ENTRIES)
    counted = sum(len(commands) for _, commands in grouped)
    assert counted == total_commands(HELP_ENTRIES)
    assert counted == sum(len(entry.commands) for entry in HELP_ENTRIES)


def test_lookup_prefers_the_plugin_name_then_falls_back_to_aliases() -> None:
    assert [entry.name for entry in find_entries(HELP_ENTRIES, "about")] == ["about"]
    assert [entry.name for entry in find_entries(HELP_ENTRIES, "info")] == ["常用功能"]
    assert [entry.name for entry in find_entries(HELP_ENTRIES, "cck")] == ["猜卡面"]
    assert [entry.name for entry in find_entries(HELP_ENTRIES, "/签到")] == ["常用功能"]
    assert find_entries(HELP_ENTRIES, "香澄不存在") == ()


def test_a_near_miss_gets_suggestions_and_a_wild_guess_gets_none() -> None:
    assert "猜卡面" in suggest_names(HELP_ENTRIES, "猜卡")
    # Nothing close: the handler says "发送 /help 看全部" instead of dressing up
    # three arbitrary plugins as near misses.
    assert suggest_names(HELP_ENTRIES, "完全不相干的东西") == ()


def test_entries_from_tolerates_an_undocumented_plugin() -> None:
    entries = entries_from({"新功能": {"description": "", "usage": {}}})
    assert entries[0].category == "其他"
    assert entries[0].commands == ()
    assert commands_by_category(entries) == ()


@pytest.mark.parametrize("kit_name", sorted(KITS))
def test_board_renders_in_every_kit(kit_name: str) -> None:
    image = render_board(HELP_ENTRIES, KITS[kit_name]())
    assert image.mode == "RGBA"
    assert image.width == 864
    # ~1700 is the density-mitigation budget from the board's design spec
    # (docs/design/image-responses/15-cluster-utility.md); past the compact
    # threshold the board must stay under it. Measured 1503-1549 at 31 commands.
    assert 800 < image.height <= 1700


def test_the_census_board_flips_to_compact_tiles() -> None:
    # 31 documented commands is past COMPACT_THRESHOLD: tiles drop the muted
    # alias sub-line (the documented density mitigation) while a small board
    # keeps the two-line tiles.
    from plugins.render import Fixed
    from plugins.help.render import board

    assert total_commands(HELP_ENTRIES) > board.COMPACT_THRESHOLD
    assert board._use_compact_tiles(HELP_ENTRIES)

    few = HELP_ENTRIES[:4]
    assert total_commands(few) <= board.COMPACT_THRESHOLD
    assert not board._use_compact_tiles(few)

    kit = KITS["bangdream"]()
    command = commands_by_category(HELP_ENTRIES)[0][1][0]
    compact_tile = board._tile(kit, command, True)
    assert compact_tile.height == Fixed(board.COMPACT_TILE_HEIGHT)
    assert board.COMPACT_TILE_HEIGHT < board.TILE_HEIGHT


@pytest.mark.parametrize("kit_name", ["bangdream", "manga"])
def test_detail_renders_with_and_without_chips(kit_name: str) -> None:
    kit = KITS[kit_name]()
    with_chips = find_entries(HELP_ENTRIES, "猜卡面")[0]
    without_chips = find_entries(HELP_ENTRIES, "娶群友")[0]
    assert with_chips.params and not without_chips.params

    tall = render_detail(with_chips, kit)
    short = render_detail(without_chips, kit)
    assert tall.width == short.width == 864
    assert tall.height > short.height


def test_renderers_default_to_a_kit_of_their_own() -> None:
    assert render_board(HELP_ENTRIES).width == 864
    assert render_detail(HELP_ENTRIES[0]).width == 864


def test_command_tiles_use_a_tighter_corner_than_the_footer() -> None:
    # 92px 高的指令磁贴吃不下 bangdream 的默认圆角 48（实机看是一墙气泡）；
    # 磁贴显式收到 20，底部整宽 footer 面板保持套件默认。
    from plugins.help.render import board

    kit = KITS["bangdream"]()
    command = commands_by_category(HELP_ENTRIES)[0][1][0]
    tile = board._tile(kit, command)
    assert board.TILE_RADIUS == 20
    assert tile.radius == board.TILE_RADIUS
    assert board._meta_panel(kit).radius == 48


def test_footer_left_aligns_usage_and_right_aligns_support() -> None:
    from plugins.help.render import board

    footer = board._meta_panel(KITS["bangdream"]())
    texts: list[str] = []
    stack = [footer]
    while stack:
        node = stack.pop()
        value = getattr(node, "text", None)
        if isinstance(value, str):
            texts.append(value)
        for attribute in ("child", "children"):
            child = getattr(node, attribute, None)
            if isinstance(child, (list, tuple)):
                stack.extend(child)
            elif child is not None:
                stack.append(child)

    assert texts == [
        "需要帮助？QQ 群 908979461",
        "输入 /help 功能名，查看用法和示例",
    ]
    assert footer.child.align_x == "end"
    usage, support = footer.child.child.children
    assert usage.align_x == "start"
    assert support.align_x == "end"
