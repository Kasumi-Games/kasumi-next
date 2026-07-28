"""The BlackKasumi help response is a live, theme-aware ImageKit card."""

from pathlib import Path

import pytest

from plugins.render.kits import KITS

CARD_WIDTH = 864
ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize("kit_name", sorted(KITS))
def test_help_card_renders_in_every_kit(kit_name: str) -> None:
    from plugins.blackjack.help_render import render_help

    image = render_help(KITS[kit_name]())

    assert image.mode == "RGBA"
    assert image.width == CARD_WIDTH
    assert 700 < image.height < 1800


def test_handler_no_longer_loads_the_static_instruction_png() -> None:
    source = (ROOT / "plugins" / "blackjack" / "__init__.py").read_text(
        encoding="utf-8"
    )

    assert "instruction.png" not in source
    assert "help_page(kit).render_async()" in source
