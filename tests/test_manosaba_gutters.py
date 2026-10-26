"""Book folds belong to reserved gutters, never behind readable content."""

import pytest
from PIL import Image
from PIL import ImageDraw
from PIL import ImageChops

from plugins.render import RenderContext
from plugins.render import PlayerIdentity
from plugins.render.kits import ManosabaKit
from plugins.render.kits.manosaba import components
from plugins.render.kits.manosaba.layouts import folio


def test_hanging_punctuation_stays_inside_its_text_column():
    a = folio.Sheet(ManosabaKit(), 800, RenderContext(pixel_ratio=1), False)
    b = folio.Sheet(ManosabaKit(), 800, RenderContext(pixel_ratio=1), False)
    text = "证言" * 10 + "？"
    a.text(text, 58, 40, 463, 23)
    b.height = a.height
    ink = ImageChops.difference(a.render(), b.render()).convert("RGB").convert("L")
    bounds = ink.point(lambda p: 255 if p > 12 else 0).getbbox()
    assert bounds is not None and bounds[2] <= 58 + 463


def book_fixture(monkeypatch):
    source = Image.new("RGBA", (200, 100), (220, 210, 205, 255))
    draw = ImageDraw.Draw(source)
    draw.rectangle((96, 0, 101, 99), fill=(0, 0, 0, 255))
    draw.rectangle((20, 20, 39, 79), fill=(200, 10, 20, 255))
    draw.rectangle((140, 20, 159, 79), fill=(10, 20, 200, 255))
    draw.rectangle((0, 0, 199, 9), fill=(10, 160, 20, 255))
    original = components.asset
    monkeypatch.setattr(
        components,
        "asset",
        lambda name: source if name == "book.png" else original(name),
    )


@pytest.mark.parametrize("spine", [0.25, 0.7])
def test_stretch_preserves_both_complete_leaves_and_moves_the_binding(
    monkeypatch, spine
):
    book_fixture(monkeypatch)
    paper = components.book_paper(800, 600, spine=spine)
    binding = round(800 * spine)
    # Both leaves' marks, plus their full top edge, survive unequal stretching.
    assert paper.getpixel((round(binding * 0.3), 300)) == (200, 10, 20, 255)
    assert paper.getpixel((round(binding + (800 - binding) * 0.5), 300)) == (
        10,
        20,
        200,
        255,
    )
    assert paper.getpixel((600, 20)) == (10, 160, 20, 255)
    assert max(paper.getpixel((binding, 300))[:3]) < 10
    assert min(paper.getpixel((400, 300))[:3]) > 190


@pytest.mark.parametrize("ratio", [1, 2])
def test_a_full_width_sheet_places_the_binding_in_its_outer_margin(monkeypatch, ratio):
    book_fixture(monkeypatch)
    kit = ManosabaKit()
    monkeypatch.setattr(
        kit, "background", lambda: components.ManosabaBackground(fill=components.PAPER)
    )
    sheet = folio.Sheet(kit, 1120, RenderContext(pixel_ratio=ratio), True)
    sheet.height = 600
    image = sheet.render()
    assert sheet.book_spine < 58
    # The right leaf's blue stain remains in the body; only the binding moves.
    assert image.getpixel((560, 300))[2] > image.getpixel((560, 300))[0]
    assert image.getpixel((sheet.book_spine, 300))[0] < image.getpixel((400, 300))[0]


@pytest.mark.parametrize("with_art", [False, True])
def test_profile_reserves_space_around_its_actual_column_gutter(with_art):
    from plugins.inventory.render.profile import ProfileData
    from plugins.inventory.render.profile import profile_page

    art = Image.new("RGBA", (100, 400), (50, 30, 40, 255)) if with_art else None
    data = ProfileData(
        PlayerIdentity("测试玩家", 24),
        1234,
        description="这段简介应该留在自己的纸页内。" * 3,
        star_stickers=123456,
        bonsai=123456,
        equipped=(
            ("头像框", "魔女审判 双生誓约头像框"),
            ("主题", "魔法少女的魔女审判"),
        ),
        standing_art=art,
    )
    sheet = profile_page(data, ManosabaKit()).compose()
    assert len(sheet.gutters) == 1
    assert not sheet.gutter_conflicts()
    # Neither profile's columns are centered on the canvas; the fold must follow them.
    gutter = sheet.gutters[0]
    assert gutter.x != sheet.width // 2 - gutter.width // 2


@pytest.mark.parametrize("ratio", [1, 2])
def test_the_entire_book_background_follows_the_column_anchor(monkeypatch, ratio):
    book_fixture(monkeypatch)
    kit = ManosabaKit()
    monkeypatch.setattr(
        kit, "background", lambda: components.ManosabaBackground(fill=components.PAPER)
    )
    sheet = folio.Sheet(kit, 800, RenderContext(pixel_ratio=ratio), True)
    sheet.height = 600
    sheet.gutter(330, 430, 120, 500)
    image = sheet.render()
    assert sheet.book_spine == 380
    # The binding is part of the full texture, including above/below the body.
    # This excludes a flat leaf with a narrow separator pasted into its middle.
    for y in (80, 300, 560):
        assert image.getpixel((380, y))[0] < image.getpixel((300, y))[0]
    assert image.getpixel((115, 300))[0] > image.getpixel((115, 300))[1]
    assert image.getpixel((590, 300))[2] > image.getpixel((590, 300))[0]


def test_a_letter_has_no_fold_through_its_full_width_body():
    from datetime import datetime

    from plugins.mailbox.models import ServiceMail
    from plugins.mailbox.render import mail_page

    mail = ServiceMail(
        id=1,
        title="来信",
        content="正文内容" * 40,
        star_kakeras=0,
        attachments=[],
        sender_id="admin",
        created_at=datetime(2026, 10, 27),
        expire_time=datetime(2099, 1, 1),
        is_broadcast=False,
        is_read=True,
        read_at=None,
    )
    sheet = mail_page(mail, (), ManosabaKit()).compose()
    assert sheet.gutters == []
    assert sheet.book_spine < 108


def test_gutter_audit_catches_content_inside_the_reserved_whitespace():
    sheet = folio.Sheet(ManosabaKit(), 800, RenderContext(), True)
    sheet.text("侵入页缝的文字", 350, 180, 250, 24)
    sheet.gutter(330, 430, 120, 500)
    assert sheet.gutter_conflicts()
