from __future__ import annotations

import importlib

import pytest

PLUGIN_MODULES = [
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
]

PLUGIN_DEPENDENCIES = {
    "plugins.blackjack": ["plugins.daily_task", "plugins.cck"],
    "plugins.cck": ["plugins.daily_task"],
    "plugins.daily": ["plugins.daily_task", "plugins.mailbox"],
    "plugins.guess_chart": ["plugins.daily_task"],
    "plugins.mines": ["plugins.daily_task"],
    "plugins.one_stroke": ["plugins.daily_task"],
}


@pytest.mark.parametrize("module_name", PLUGIN_MODULES)
def test_plugin_imports_without_startup_side_effects(module_name: str) -> None:
    for dependency in PLUGIN_DEPENDENCIES.get(module_name, []):
        importlib.import_module(dependency)
    module = importlib.import_module(module_name)
    assert module is not None
