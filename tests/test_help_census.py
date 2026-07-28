"""Census: every player-facing command matcher must be documented in /help.

The second live round found /抽卡 — and with it the whole inventory/season
command family — absent from the help board. These tests close that class of
bug permanently: they enumerate every registered ``on_command`` matcher (the
same registry the bot dispatches from, so a new plugin cannot hide from them),
subtract superuser-only matchers and the explicit hidden allowlist, and demand
that at least one spelling of everything left resolves to a help entry. A new
player-facing command without a help entry fails here until it is documented
or deliberately allowlisted.

The same registry powers the ranking-alias pins: in season 排行/排行榜 must
mean the Pt ladder (inventory ``seasonrank``) while the level ladder answers
to 等级排行 only (daily ``levelrank``), and the two trigger sets must stay
disjoint so nonebot never logs duplicated-prefix warnings for them.
"""

from __future__ import annotations

import importlib

import pytest
from nonebot.rule import CommandRule
from nonebot.matcher import matchers
from nonebot.permission import SuperUser

from plugins.help import HELP_ENTRIES
from plugins.help.entries import find_entries

#: Everything that registers matchers, mirrored from tests/test_plugin_smoke.py.
PLUGIN_MODULES = (
    "plugins.bang_avatar",
    "plugins.blackjack",
    "plugins.cck",
    "plugins.channels",
    "plugins.daily",
    "plugins.daily_task",
    "plugins.gacha",
    "plugins.guess_chart",
    "plugins.help",
    "plugins.info",
    "plugins.inventory",
    "plugins.mailbox",
    "plugins.mines",
    "plugins.monetary",
    "plugins.nickname",
    "plugins.one_stroke",
    "plugins.passive_manager",
    "plugins.red_envelope",
    "plugins.render",
    "plugins.vits",
    "plugins.whitelist",
)

PLUGIN_DEPENDENCIES = {
    "plugins.blackjack": ["plugins.daily_task", "plugins.cck"],
    "plugins.cck": ["plugins.daily_task"],
    "plugins.daily": ["plugins.daily_task", "plugins.mailbox"],
    "plugins.guess_chart": ["plugins.daily_task"],
    "plugins.mines": ["plugins.daily_task"],
    "plugins.one_stroke": ["plugins.daily_task"],
}

#: Commands a player *can* run that /help deliberately does not advertise.
#: Superuser-only matchers are excluded automatically by permission, so this
#: allowlist is only for hidden technical commands. Every name here must both
#: exist as a registered trigger and stay undocumented — a stale or documented
#: entry fails the allowlist test, which keeps hiding a command a decision
#: rather than a default.
HIDDEN_COMMANDS = frozenset({"id"})


def _import_all_plugins() -> None:
    for module_name in PLUGIN_MODULES:
        for dependency in PLUGIN_DEPENDENCIES.get(module_name, []):
            importlib.import_module(dependency)
        importlib.import_module(module_name)


def _command_matchers() -> list[tuple[frozenset[str], bool]]:
    """Every registered ``on_command`` matcher, as (triggers, superuser?).

    Reads the live nonebot registry rather than grepping source, so aliases
    and permissions are exactly what dispatch sees. Matchers without a
    ``CommandRule`` (``on_message`` listeners, alconna commands) are not
    command surfaces in this sense and are skipped.
    """

    _import_all_plugins()
    found: list[tuple[frozenset[str], bool]] = []
    for priority in matchers:
        for matcher in matchers[priority]:
            rule = getattr(matcher, "rule", None)
            if rule is None:
                continue
            command_rule = next(
                (
                    checker.call
                    for checker in rule.checkers
                    if isinstance(checker.call, CommandRule)
                ),
                None,
            )
            if command_rule is None:
                continue
            triggers = frozenset(
                cmd[0] for cmd in command_rule.cmds if len(cmd) == 1
            )
            superuser = any(
                isinstance(checker.call, SuperUser)
                for checker in matcher.permission.checkers
            )
            found.append((triggers, superuser))
    return found


def _trigger_set(name: str) -> frozenset[str]:
    """The one matcher trigger set containing ``name``; fails on 0 or 2+."""

    owners = {
        triggers for triggers, _ in _command_matchers() if name in triggers
    }
    assert len(owners) == 1, (
        f"expected exactly one matcher to answer to {name!r}, "
        f"found {len(owners)}: {sorted(sorted(t) for t in owners)}"
    )
    return next(iter(owners))


def test_every_player_facing_command_is_documented() -> None:
    missing: list[list[str]] = []
    for triggers, superuser in _command_matchers():
        if superuser or triggers & HIDDEN_COMMANDS:
            continue
        if not any(find_entries(HELP_ENTRIES, trigger) for trigger in triggers):
            missing.append(sorted(triggers))
    assert not missing, (
        "player-facing commands with no help entry (add them to plugin_data "
        f"in plugins/help/__init__.py, or to HIDDEN_COMMANDS on purpose): {missing}"
    )


def test_the_hidden_allowlist_matches_reality() -> None:
    all_triggers: set[str] = set()
    for triggers, _ in _command_matchers():
        all_triggers |= triggers

    stale = HIDDEN_COMMANDS - all_triggers
    assert not stale, f"HIDDEN_COMMANDS lists commands that no longer exist: {sorted(stale)}"

    documented = sorted(
        name for name in HIDDEN_COMMANDS if find_entries(HELP_ENTRIES, name)
    )
    assert not documented, (
        f"HIDDEN_COMMANDS lists commands that ARE documented: {documented} — "
        "remove them from the allowlist"
    )


def test_superuser_only_commands_stay_off_the_board() -> None:
    # The census skips these by permission; this pins that they exist and that
    # nobody documents them by accident.
    for name in ("balanceset", "seasonadmin"):
        triggers = _trigger_set(name)
        assert not any(
            find_entries(HELP_ENTRIES, trigger) for trigger in triggers
        ), f"superuser command {name} leaked into the help entries"


def test_levelrank_answers_to_the_level_spellings_only() -> None:
    assert _trigger_set("levelrank") == {"levelrank", "等级排行", "等级排行榜"}


def test_seasonrank_owns_the_bare_ranking_spellings() -> None:
    assert _trigger_set("seasonrank") == {
        "seasonrank",
        "赛季排行",
        "赛季排行榜",
        "排行",
        "排行榜",
    }


@pytest.mark.parametrize("spelling", ["排行", "排行榜"])
def test_bare_ranking_spellings_belong_to_the_season_ladder(
    spelling: str,
) -> None:
    # _trigger_set already fails if two matchers claim the spelling, which is
    # exactly the duplicated-prefix condition nonebot warns about.
    assert "seasonrank" in _trigger_set(spelling)


def test_the_two_ladders_share_no_trigger() -> None:
    assert not _trigger_set("levelrank") & _trigger_set("seasonrank")
