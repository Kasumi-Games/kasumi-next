"""A book index and facing-page command reference, rather than button grids."""

from .folio import surface
from ..components import ROSE
from ..components import MUTED


@surface(1240, book=True)
def board(f, entries):
    from plugins.help.entries import SUPPORT_GROUP
    from plugins.help.entries import total_commands
    from plugins.help.entries import commands_by_category

    y = f.title("使用手册", "COMMAND INDEX", f"共 {total_commands(entries)} 条指令")
    columns = [y, y]
    for name, commands in commands_by_category(entries):
        col = min(range(2), key=lambda i: columns[i])
        x = 58 + col * 600
        bottom = f.section(f"{name} / {len(commands)} 项", x, columns[col], 524)
        for index, command in enumerate(commands, 1):
            f.text(f"{index:02d}", x, bottom + 5, 38, 19, MUTED)
            bottom = f.text(command.command, x + 54, bottom, 470, 27) + 14
        columns[col] = bottom + 30
    f.gutter(582, 658, y, max(columns) - 30)
    f.footer(
        f"/help 功能名 查看用法和示例 · 需要帮助？QQ 群 {SUPPORT_GROUP}",
        max(columns) + 20,
    )


@surface(1240, book=True)
def detail(f, entry):
    y = f.title(entry.name, "COMMAND REFERENCE", entry.description)
    a = f.section("用法", 58, y, 622)
    for command, meaning in entry.usage:
        a = f.text(command, 58, a, 622, 28, ROSE)
        a = f.text(meaning, 82, a + 8, 598, 23) + 26
    b = y
    for label, values in entry.params:
        b = f.section(label, 748, b, 434)
        b = f.text(" / ".join(values), 748, b, 434, 24) + 34
    if entry.examples:
        b = f.section("输入示例", 748, b, 434)
        for example in entry.examples:
            b = f.text(example, 748, b, 434, 24, ROSE) + 18
    f.gutter(680, 748, y, max(a, b), padding=24)
    f.footer("/help 查看全部功能", max(a, b) + 28)


def rulebook(f, title, kicker, sections):
    y = f.title(title, kicker, "规则与指令")
    columns = [y, y]
    for index, (name, rows) in enumerate(sections):
        col = 0 if index < 2 else 1
        x = 58 + col * 600
        bottom = f.section(name, x, columns[col], 524)
        for key, label, text in rows:
            if key:
                f.stamp(key, x, bottom, 74, size=22)
                left, width = x + 98, 426
            else:
                left, width = x, 524
            end = f.text(label, left, bottom, width, 26, ROSE)
            end = f.text(text, left, end + 8, width, 23)
            bottom = max(bottom + (72 if key else 0), end + 26)
        columns[col] = bottom + 26
    f.gutter(582, 658, y, max(columns) - 26)
    f.footer("输入对应指令开始游戏 · /help 查看其他功能", max(columns) + 10)
