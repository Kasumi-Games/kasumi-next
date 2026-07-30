"""Structured view over the hand-maintained ``plugin_data`` dict.

``plugins/help/__init__.py`` stays the single source of truth for what this bot
documents; nothing in here invents a command, a description, or an example that
the dict does not already carry. This module only re-shapes it into the three
things a card needs and a ``\\n``-joined string never did:

* one :class:`HelpCommand` per typeable command instead of one row per plugin,
  recovered from the ``"/信息|info"`` and ``"/转账|transfer <昵称> <数量>"`` key
  syntax. ``常用功能`` alone holds four commands and the old dump showed none of
  them;
* the enumerable value sets the usage prose spells out as a sentence
  (``难度可选为 easy, normal, hard, …``), which the detail card renders as chips
  instead of as a 60-character run-on line;
* a category per plugin, which is the one piece of grouping metadata the dict
  does not carry. :data:`CATEGORY_BY_PLUGIN` supplies it and anything unlisted
  falls into :data:`DEFAULT_CATEGORY`, so adding a plugin to ``plugin_data``
  never breaks the board — it just lands in 其他 until it is categorised.

Nothing here imports ``plugins.help`` itself: the builders take the dict as an
argument so this module stays importable, and testable, on its own.
"""

import re
import difflib
from typing import Any
from typing import Mapping
from typing import Sequence
from dataclasses import dataclass

#: Support group printed on the board, from ``plugins/help/__init__.py``.
SUPPORT_GROUP = "908979461"

#: Category shown for a plugin that :data:`CATEGORY_BY_PLUGIN` does not name.
DEFAULT_CATEGORY = "其他"

#: Board order. Categories outside this tuple are appended, sorted, at the end.
CATEGORY_ORDER = ("游戏", "养成", "社交", "工具", DEFAULT_CATEGORY)

#: Which board section a plugin's commands belong to. Keys are ``plugin_data``
#: keys; a key that disappears from the dict simply stops being used.
CATEGORY_BY_PLUGIN = {
    "猜卡面": "游戏",
    "猜谱面": "游戏",
    "一笔画": "游戏",
    "黑香澄": "游戏",
    "探险": "游戏",
    "娶群友": "游戏",
    "常用功能": "养成",
    "每日任务": "养成",
    "昵称": "养成",
    "抽卡": "养成",
    "仓库": "养成",
    "装扮": "养成",
    "流星堂": "养成",
    "个人资料": "养成",
    "赛季": "养成",
    "邮箱": "社交",
    "红包": "社交",
    "help": "工具",
    "about": "工具",
    "tts": "工具",
}

#: ``<难度:简单|普通|困难>`` — an enumeration written into a command string.
_INLINE_PARAM = re.compile(r"<([^<>:|]{1,8}):([^<>]+)>")

#: Prose that introduces an enumeration, and the label to file it under when
#: the words before the marker do not supply one.
_ENUM_MARKERS = (("可选为", None), ("缩写为", "缩写"))

#: The clause a prose enumeration ends at. Full-width punctuation only: the
#: half-width comma is the separator *inside* the enumeration, which is what
#: keeps ``难度可选为 easy, normal, hard, expert，支持缩写为 ez, …`` from folding
#: the abbreviations into the difficulty list.
_CLAUSE_END = re.compile(r"[，。；]")

_VALUE_SEPARATOR = re.compile(r"[,、]")

#: Trailing word before an enumeration marker, which is its label.
_LABEL_TAIL = re.compile(r"([一-鿿A-Za-z]{1,6})$")


@dataclass(frozen=True)
class HelpCommand:
    """One typeable command and everything that hangs off it.

    Attributes:
        command: The string a player types, e.g. ``/猜卡面``.
        summary: What the command does, from its usage line.
        aliases: Alternate triggers, flags, sub-triggers and argument forms —
            ``cck``, ``猜猜看``, ``-f``, ``bzd``, ``<难度>``.
    """

    command: str
    summary: str
    aliases: tuple[str, ...] = ()


@dataclass(frozen=True)
class HelpEntry:
    """One ``plugin_data`` entry, unpacked.

    Attributes:
        name: The token ``/help <name>`` accepts, and the display name.
        description: One-line description of the plugin.
        category: Board section, from :data:`CATEGORY_BY_PLUGIN`.
        usage: ``(command, meaning)`` pairs, in declaration order.
        examples: Example invocations.
        commands: One entry per distinct command in ``usage``.
        params: ``(label, values)`` pairs recovered from the usage text.
    """

    name: str
    description: str
    category: str
    usage: tuple[tuple[str, str], ...] = ()
    examples: tuple[str, ...] = ()
    commands: tuple[HelpCommand, ...] = ()
    params: tuple[tuple[str, tuple[str, ...]], ...] = ()


def entries_from(data: Mapping[str, Mapping[str, Any]]) -> tuple[HelpEntry, ...]:
    """Build the entry list from a ``plugin_data``-shaped mapping.

    Args:
        data: Plugin name to ``{"description", "usage", "examples"}`` mapping.

    Returns:
        One entry per plugin, in declaration order.
    """

    entries: list[HelpEntry] = []
    for name, info in data.items():
        raw = tuple((str(k), str(v)) for k, v in (info.get("usage") or {}).items())
        # Params come off the raw text; the displayed text is then trimmed of
        # the clause they were lifted out of. Order matters.
        params = _params(raw)
        usage = tuple((command, _trim_meaning(meaning)) for command, meaning in raw)
        entries.append(
            HelpEntry(
                name=str(name),
                description=str(info.get("description", "")),
                category=CATEGORY_BY_PLUGIN.get(name, DEFAULT_CATEGORY),
                usage=usage,
                examples=tuple(str(x) for x in (info.get("examples") or ())),
                commands=_commands(usage),
                params=params,
            )
        )
    return tuple(entries)


def total_commands(entries: Sequence[HelpEntry]) -> int:
    """Count every documented command across ``entries``."""

    return sum(len(entry.commands) for entry in entries)


def commands_by_category(
    entries: Sequence[HelpEntry],
) -> tuple[tuple[str, tuple[HelpCommand, ...]], ...]:
    """Group every command by its plugin's category.

    Args:
        entries: Entries to group.

    Returns:
        ``(category, commands)`` pairs in :data:`CATEGORY_ORDER`, with empty
        categories dropped and unknown ones appended in sorted order.
    """

    grouped: dict[str, list[HelpCommand]] = {}
    for entry in entries:
        grouped.setdefault(entry.category, []).extend(entry.commands)

    known = [name for name in CATEGORY_ORDER if grouped.get(name)]
    extra = sorted(name for name in grouped if name not in CATEGORY_ORDER)
    return tuple((name, tuple(grouped[name])) for name in [*known, *extra])


def find_entries(
    entries: Sequence[HelpEntry], token: str
) -> tuple[HelpEntry, ...]:
    """Resolve a player-typed token to the entries it names.

    The plugin name wins outright when it matches, which keeps ``/help about``
    pointing at the bot-introduction entry. Otherwise every command and alias
    is fair game, so a player can
    type the thing they actually remember — ``cck``, ``mines``, ``/签到``.

    Args:
        entries: Entries to search.
        token: Raw player input.

    Returns:
        Matching entries; empty when nothing matches.
    """

    needle = _token(token)
    if not needle:
        return ()

    exact = tuple(entry for entry in entries if _token(entry.name) == needle)
    if exact:
        return exact
    return tuple(entry for entry in entries if needle in _search_tokens(entry))


def suggest_names(
    entries: Sequence[HelpEntry], token: str, limit: int = 3
) -> tuple[str, ...]:
    """Return the entry names closest to a token that matched nothing.

    Args:
        entries: Entries to search.
        token: Raw player input.
        limit: Maximum number of suggestions.

    Returns:
        Entry names, closest first, or an empty tuple when nothing is close.
        The caller says "发送 /help 看全部" in that case rather than presenting
        three arbitrary plugins as though they were near misses.
    """

    needle = _token(token)
    index: dict[str, str] = {}
    for entry in entries:
        for candidate in _search_tokens(entry):
            index.setdefault(candidate, entry.name)

    names: list[str] = []
    matches = difflib.get_close_matches(needle, list(index), n=limit * 2, cutoff=0.4)
    for match in matches:
        name = index[match]
        if name not in names:
            names.append(name)
    return tuple(names[:limit])


def _search_tokens(entry: HelpEntry) -> set[str]:
    tokens = {_token(entry.name)}
    for command in entry.commands:
        tokens.add(_token(command.command))
        tokens.update(
            _token(alias)
            for alias in command.aliases
            if not alias.startswith(("<", "-"))
        )
    return {token for token in tokens if token}


def _token(text: str) -> str:
    return text.strip().lstrip("/").casefold()


def _commands(usage: tuple[tuple[str, str], ...]) -> tuple[HelpCommand, ...]:
    """Fold usage lines into one record per distinct command.

    ``"/黑香澄"``, ``"/黑香澄 <数量>"`` and ``"/黑香澄 -h"`` are three ways to run
    one command, so they become one tile with two argument forms attached. A
    line that does not start with ``/`` is a bare sub-trigger — ``bzd``, ``r``,
    ``提示`` — and belongs to the plugin's first command.
    """

    commands: list[dict[str, Any]] = []
    by_token: dict[str, dict[str, Any]] = {}

    for key, meaning in usage:
        head, _, tail = key.partition(" ")
        tail = tail.strip()
        names = _names(head)

        if not head.startswith("/") and commands:
            _extend(commands[0], [key])
            continue

        target = next(
            (by_token[token] for token in map(_token, names) if token in by_token), None
        )
        if target is None:
            target = {"command": names[0], "summary": meaning, "aliases": []}
            commands.append(target)
            _extend(target, names[1:])
        else:
            _extend(target, [name for name in names if _token(name) != _token(target["command"])])
        for name in names:
            by_token.setdefault(_token(name), target)
        if tail:
            _extend(target, [tail])

    return tuple(
        HelpCommand(
            command=item["command"],
            summary=item["summary"],
            aliases=tuple(item["aliases"]),
        )
        for item in commands
    )


def _extend(command: dict[str, Any], names: Sequence[str]) -> None:
    """Append alias spellings, ignoring ones already covered.

    Comparison is by :func:`_token`, so ``/邮件`` does not join a command that
    already answers to ``邮件``.
    """

    known = {_token(command["command"])} | {_token(a) for a in command["aliases"]}
    for name in names:
        if name and _token(name) not in known:
            command["aliases"].append(name)
            known.add(_token(name))


def _names(head: str) -> tuple[str, ...]:
    """Split ``/猜卡面|cck|猜猜看`` into its trigger words.

    A head that carries a placeholder (``<歌曲名称|ID>``) is left whole: the
    pipe in there separates two spellings of one argument, not two commands.
    """

    if "<" in head:
        return (head,)
    return tuple(part for part in head.split("|") if part) or (head,)


def _params(
    usage: tuple[tuple[str, str], ...],
) -> tuple[tuple[str, tuple[str, ...]], ...]:
    """Recover enumerable value sets from the usage text.

    ``猜卡面`` documents twelve difficulty names inside one sentence. That is a
    value set wearing a sentence's clothes; pulled out it becomes a chip grid
    the player can read, and copy, one value at a time.
    """

    found: dict[str, tuple[str, ...]] = {}
    for command, meaning in usage:
        for label, values in _inline_params(command):
            found.setdefault(label, values)
        for label, values, _ in _prose_enumerations(meaning):
            found.setdefault(label, values)
    return tuple(found.items())


def _inline_params(command: str) -> list[tuple[str, tuple[str, ...]]]:
    found: list[tuple[str, tuple[str, ...]]] = []
    for label, body in _INLINE_PARAM.findall(command):
        values = tuple(part.strip() for part in body.split("|") if part.strip())
        if len(values) > 1:
            found.append((label.strip(), values))
    return found


def _prose_enumerations(meaning: str) -> list[tuple[str, tuple[str, ...], int]]:
    """Value sets written into a usage description, with where they start.

    Returns ``(label, values, marker_index)`` for every enumeration of two or
    more values. A one-value "enumeration" — ``谱面难度可选为 1-30`` — is a range
    written in prose, not a set, so it is left in the sentence where it reads
    correctly.
    """

    found: list[tuple[str, tuple[str, ...], int]] = []
    for marker, fixed_label in _ENUM_MARKERS:
        index = meaning.find(marker)
        if index < 0:
            continue
        label = fixed_label or _label_before(meaning[:index])
        clause = _CLAUSE_END.split(meaning[index + len(marker) :], 1)[0]
        values = tuple(
            part.strip() for part in _VALUE_SEPARATOR.split(clause) if part.strip()
        )
        if label and len(values) > 1:
            found.append((label, values, index))
    return found


def _trim_meaning(meaning: str) -> str:
    """Drop the clause that spells an enumeration out as a sentence.

    The values are rendered as chips on the same card, so leaving the prose
    version in place prints them twice — and the prose version is the one that
    gets ellipsized. Only clauses whose values were actually lifted out are cut.
    """

    cut = len(meaning)
    for _, _, index in _prose_enumerations(meaning):
        boundary = max((meaning.rfind(mark, 0, index) for mark in "，。；"), default=-1)
        cut = min(cut, index if boundary < 0 else boundary)
    return meaning[:cut].strip() or meaning


def _label_before(text: str) -> str:
    match = _LABEL_TAIL.search(text.strip())
    return match.group(1) if match else ""
