"""The /装扮 装备 token resolver and its handler messages.

Live feedback round 3: 装扮 装备 demanded raw item ids. Players now type what
they read — the display name, a theme alias, or the id — case-insensitively.
Resolution order is exact id → theme token → unique name among OWNED
cosmetics → catalog-wide unique name; anything ambiguous or unknown stays a
text error listing the near matches. The DB is the real ``items.json`` catalog
synced into an in-memory sqlite session.
"""

from __future__ import annotations

from typing import Any
from typing import Callable

import pytest
from nonebot.exception import FinishedException
from nonebot.adapters.satori import Message

import plugins.inventory as inventory
from plugins.inventory import models
from plugins.inventory import service


class RecordingMatcher:
    """Stands in for ``Matcher``: records every send, finish raises."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, Any, dict[str, Any]]] = []

    async def send(self, message: Any = None, **kwargs: Any) -> None:
        self.calls.append(("send", message, kwargs))

    async def finish(self, message: Any = None, **kwargs: Any) -> None:
        self.calls.append(("finish", message, kwargs))
        raise FinishedException()


@pytest.fixture
def catalog_db(sqlite_session):
    """In-memory inventory DB seeded from the real ``items.json`` catalog."""

    from plugins.inventory import database
    from plugins.inventory.catalog import sync_catalog

    session = sqlite_session(database, models.Base)
    sync_catalog()
    return session


def _seed_duplicate_named(session, name: str = "重名测试立绘") -> None:
    for item_id in ("dup_art_a", "dup_art_b"):
        session.add(
            models.Item(
                item_id=item_id,
                category="cosmetic",
                name=name,
                stackable=False,
                visible=True,
                sort_order=99,
                metadata_json="{}",
            )
        )
        session.add(
            models.CosmeticItem(
                item_id=item_id, cosmetic_type="standing_art", rarity=3
            )
        )
    session.commit()


# ---------------------------------------------------------------------------
# Token resolution matrix
# ---------------------------------------------------------------------------


def test_resolves_exact_item_id(catalog_db) -> None:
    item = inventory._resolve_cosmetic_token("user", "theme_kasumi_starbeat")
    assert item.item_id == "theme_kasumi_starbeat"


def test_catalog_sync_purges_retired_title_records(catalog_db) -> None:
    from plugins.inventory.catalog import sync_catalog

    catalog_db.add(
        models.Item(
            item_id="title_development_only",
            category="cosmetic",
            name="开发称号",
            stackable=False,
            visible=True,
            sort_order=1,
            metadata_json="{}",
        )
    )
    catalog_db.add(
        models.CosmeticItem(
            item_id="title_development_only", cosmetic_type="title", rarity=1
        )
    )
    catalog_db.add(
        models.UserItem(
            user_id="user",
            item_id="title_development_only",
            scope_type=models.PERMANENT_SCOPE_TYPE,
            scope_id=models.PERMANENT_SCOPE_ID,
            quantity=1,
            updated_at=1,
        )
    )
    catalog_db.add(
        models.EquippedItem(
            user_id="user",
            slot="title",
            item_id="title_development_only",
            updated_at=1,
        )
    )
    catalog_db.add(
        models.ItemTransaction(
            user_id="user",
            item_id="title_development_only",
            scope_type=models.PERMANENT_SCOPE_TYPE,
            scope_id=models.PERMANENT_SCOPE_ID,
            delta=1,
            quantity_after=1,
            reason="test",
            created_at=1,
        )
    )
    catalog_db.commit()

    sync_catalog()

    assert service.get_item("title_development_only") is None
    assert (
        catalog_db.query(models.CosmeticItem)
        .filter(models.CosmeticItem.cosmetic_type == "title")
        .count()
        == 0
    )
    assert catalog_db.query(models.UserItem).filter_by(item_id="title_development_only").count() == 0
    assert catalog_db.query(models.EquippedItem).filter_by(slot="title").count() == 0
    assert catalog_db.query(models.ItemTransaction).filter_by(item_id="title_development_only").count() == 0


def test_resolves_item_id_case_insensitively(catalog_db) -> None:
    item = inventory._resolve_cosmetic_token("user", "THEME_KASUMI_STARBEAT")
    assert item.item_id == "theme_kasumi_starbeat"


def test_resolves_display_name(catalog_db) -> None:
    item = inventory._resolve_cosmetic_token("user", "星之鼓动主题")
    assert item.item_id == "theme_kasumi_starbeat"


def test_resolves_theme_alias(catalog_db) -> None:
    for token in ("香澄", "starbeat", "Starbeat", "kasumi"):
        item = inventory._resolve_cosmetic_token("user", token)
        assert item.item_id == "theme_kasumi_starbeat", token
    assert (
        inventory._resolve_cosmetic_token("user", "扬帆").item_id
        == "theme_s1_sailing"
    )


def test_resolves_non_theme_cosmetic_by_name_with_space(catalog_db) -> None:
    item = inventory._resolve_cosmetic_token("user", "户山香澄 抬头看，星星在跳动")
    assert item.item_id == "standing_art_kasumi_starbeat"


def test_catalog_wide_unique_name_matches_without_ownership(catalog_db) -> None:
    # 星之鼓动冠军头像框 is a frame the player does not own; the name is unique in the
    # catalog, so it still resolves (ownership is checked at equip time).
    item = inventory._resolve_cosmetic_token("user", "星之鼓动冠军头像框")
    assert item.item_id == "frame_starbeat_champion"


def test_owned_name_match_wins_over_catalog_duplicate(catalog_db) -> None:
    _seed_duplicate_named(catalog_db)
    service.grant_item("user", "dup_art_b", 1, "test")
    item = inventory._resolve_cosmetic_token("user", "重名测试立绘")
    assert item.item_id == "dup_art_b"


def test_ambiguous_catalog_name_lists_the_candidates(catalog_db) -> None:
    _seed_duplicate_named(catalog_db)
    with pytest.raises(ValueError) as error:
        inventory._resolve_cosmetic_token("user", "重名测试立绘")
    message = str(error.value)
    assert "匹配到多个装扮" in message
    assert "dup_art_a" in message
    assert "dup_art_b" in message


def test_ambiguous_owned_name_lists_the_candidates(catalog_db) -> None:
    _seed_duplicate_named(catalog_db)
    service.grant_item("user", "dup_art_a", 1, "test")
    service.grant_item("user", "dup_art_b", 1, "test")
    with pytest.raises(ValueError) as error:
        inventory._resolve_cosmetic_token("user", "重名测试立绘")
    assert "匹配到多个装扮" in str(error.value)


def test_unknown_token_lists_near_matches(catalog_db) -> None:
    with pytest.raises(ValueError) as error:
        inventory._resolve_cosmetic_token("user", "冠军")
    message = str(error.value)
    assert "没有找到装扮「冠军」" in message
    assert "相近的装扮" in message
    assert "星之鼓动冠军头像框" in message


def test_unknown_token_without_near_matches_points_at_the_listing(
    catalog_db,
) -> None:
    with pytest.raises(ValueError) as error:
        inventory._resolve_cosmetic_token("user", "qqxyz")
    assert "没有找到装扮「qqxyz」" in str(error.value)


# ---------------------------------------------------------------------------
# Handler messages
# ---------------------------------------------------------------------------


async def _invoke(text: str, make_satori_event: Callable[..., Any]) -> str:
    matcher = RecordingMatcher()
    event = make_satori_event(f"/装扮 {text}".rstrip())
    with pytest.raises(FinishedException):
        await inventory.handle_cosmetic(matcher, event, Message(text))  # type: ignore[arg-type]
    assert [kind for kind, _, _ in matcher.calls] == ["finish"]
    return str(matcher.calls[0][1])


async def test_equip_by_name_uses_display_name_and_chinese_slot(
    catalog_db, make_satori_event: Callable[..., Any]
) -> None:
    service.grant_item("user", "theme_kasumi_starbeat", 1, "test")
    reply = await _invoke("装备 星之鼓动主题", make_satori_event)
    assert "已装备 星之鼓动主题 到 主题。" in reply
    assert service.get_equipped("user")["theme"] == "theme_kasumi_starbeat"


async def test_equip_by_alias_and_by_id_report_the_same_success(
    catalog_db, make_satori_event: Callable[..., Any]
) -> None:
    service.grant_item("user", "theme_kasumi_starbeat", 1, "test")
    assert "已装备 星之鼓动主题 到 主题。" in await _invoke(
        "装备 香澄", make_satori_event
    )
    assert "已装备 星之鼓动主题 到 主题。" in await _invoke(
        "装备 theme_kasumi_starbeat", make_satori_event
    )


async def test_equip_standing_art_name_with_space(
    catalog_db, make_satori_event: Callable[..., Any]
) -> None:
    service.grant_item("user", "standing_art_kasumi_starbeat", 1, "test")
    reply = await _invoke("装备 户山香澄 抬头看，星星在跳动", make_satori_event)
    assert "已装备 户山香澄 抬头看，星星在跳动 到 立绘。" in reply
    assert (
        service.get_equipped("user")["standing_art"]
        == "standing_art_kasumi_starbeat"
    )


async def test_equip_unowned_cosmetic_stays_a_text_error(
    catalog_db, make_satori_event: Callable[..., Any]
) -> None:
    reply = await _invoke("装备 星之鼓动冠军头像框", make_satori_event)
    assert "还没有拥有 星之鼓动冠军头像框" in reply


async def test_equip_unknown_token_replies_near_matches(
    catalog_db, make_satori_event: Callable[..., Any]
) -> None:
    reply = await _invoke("装备 鼓动", make_satori_event)
    assert "没有找到装扮「鼓动」" in reply
    assert "相近的装扮" in reply


async def test_listing_shows_typeable_names_and_the_profile_hint(
    catalog_db, make_satori_event: Callable[..., Any]
) -> None:
    service.grant_item("user", "theme_kasumi_starbeat", 1, "test")
    service.grant_item("user", "standing_art_kasumi_starbeat", 1, "test")
    service.equip_cosmetic("user", "standing_art_kasumi_starbeat")

    reply = await _invoke("", make_satori_event)
    assert "<img" in reply
    rows = service.list_inventory("user", category="cosmetic", include_season=False)
    data = inventory._cosmetic_list_data(
        "user", rows, page=1, total_pages=1, offset=0
    )
    assert [(row.index, row.name, row.kind) for row in data.rows] == [
        (1, "星之鼓动主题", "主题"),
        (2, "户山香澄 抬头看，星星在跳动", "立绘"),
    ]
    assert data.rows[1].equipped is True
    assert "立绘：户山香澄 抬头看，星星在跳动" in data.equipped_summary
    assert "装扮 装备 <序号或名称>" in data.footer


async def test_cosmetic_listing_paginates_and_number_can_be_equipped(
    catalog_db, make_satori_event: Callable[..., Any]
) -> None:
    cosmetics = inventory._catalog_cosmetics()[:12]
    for item in cosmetics:
        service.grant_item("user", item.item_id, 1, "test")

    first = await _invoke("", make_satori_event)
    second = await _invoke("2", make_satori_event)
    assert "<img" in first
    assert "<img" in second
    rows = service.list_inventory("user", category="cosmetic", include_season=False)
    page1 = inventory._cosmetic_list_data(
        "user", rows[:10], page=1, total_pages=2, offset=0
    )
    page2 = inventory._cosmetic_list_data(
        "user", rows[10:12], page=2, total_pages=2, offset=10
    )
    assert [row.index for row in page1.rows] == list(range(1, 11))
    assert [row.index for row in page2.rows] == [11, 12]

    reply = await _invoke("装备 12", make_satori_event)
    assert f"已装备 {cosmetics[11].name}" in reply


async def test_unequip_keeps_chinese_slot_words(
    catalog_db, make_satori_event: Callable[..., Any]
) -> None:
    service.grant_item("user", "standing_art_kasumi_starbeat", 1, "test")
    service.equip_cosmetic("user", "standing_art_kasumi_starbeat")
    assert "已卸下装扮。" in await _invoke("卸下 立绘", make_satori_event)
    assert "standing_art" not in service.get_equipped("user")
    assert "这个位置没有装备装扮。" in await _invoke("卸下 主题", make_satori_event)
