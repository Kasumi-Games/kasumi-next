"""Interaction regressions for the player-facing 流星堂 command."""

from unittest.mock import AsyncMock
from unittest.mock import Mock

import pytest
from nonebot.adapters.satori import Message
from nonebot.exception import FinishedException

import plugins.ryuseido as ryuseido
from plugins.ryuseido.service import PurchaseResult
from plugins.ryuseido.service import SeasonPullStatus
from plugins.ryuseido.service import ShopOffer
from plugins.inventory.render import InventoryListRow


class FinishingMatcher:
    async def finish(self, message=None, **kwargs) -> None:
        raise FinishedException()


async def test_buying_an_offer_is_a_single_step(
    monkeypatch: pytest.MonkeyPatch,
    make_satori_event,
) -> None:
    offer = ShopOffer("A01", "standing_art", "standing_art_test", 500)
    purchase = PurchaseResult(offer, balance_after=700)
    buy = Mock(return_value=purchase)
    send_section = AsyncMock(side_effect=FinishedException())
    monkeypatch.setattr(ryuseido, "get_offer", lambda sku: offer)
    monkeypatch.setattr(ryuseido, "buy_offer", buy)
    monkeypatch.setattr(ryuseido, "_offer_page", lambda selected: 1)
    monkeypatch.setattr(ryuseido, "_send_section", send_section)

    with pytest.raises(FinishedException):
        await ryuseido.handle_shop(
            FinishingMatcher(),
            make_satori_event("/流星堂 购买 A01"),
            Message("购买 A01"),
        )

    buy.assert_called_once_with("user", "A01")
    assert send_section.await_args.kwargs["notice"].startswith("已购入")


async def test_theme_category_opens_the_paginated_listing(
    monkeypatch: pytest.MonkeyPatch,
    make_satori_event,
) -> None:
    offer = ShopOffer("T01", "theme", "theme_sakura", 3000)
    send_section = AsyncMock(side_effect=FinishedException())
    send_preview = AsyncMock(side_effect=FinishedException())
    monkeypatch.setattr(ryuseido, "list_offers", lambda section=None: (offer,))
    monkeypatch.setattr(ryuseido, "_send_section", send_section)
    monkeypatch.setattr(ryuseido, "_send_theme_preview", send_preview)

    with pytest.raises(FinishedException):
        await ryuseido.handle_shop(
            FinishingMatcher(),
            make_satori_event("/流星堂 主题"),
            Message("主题"),
        )

    send_section.assert_awaited_once()
    send_preview.assert_not_awaited()


async def test_theme_listing_explains_preview_and_direct_purchase(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    offer = ShopOffer("T01", "theme", "theme_sakura", 3000)
    send_page = AsyncMock()
    monkeypatch.setattr(ryuseido, "list_offers", lambda section=None: (offer,))
    monkeypatch.setattr(
        ryuseido,
        "_offer_row",
        lambda user_id, selected: InventoryListRow(
            index="T01",
            name="樱色",
            detail="3000 盆栽",
            kind="主题",
            show_art_slot=False,
        ),
    )
    monkeypatch.setattr(ryuseido, "_subtitle", lambda user_id: "盆栽 1200 盆")
    monkeypatch.setattr(ryuseido, "_send_page", send_page)

    await ryuseido._send_section(
        FinishingMatcher(),
        "user",
        "theme",
        1,
        object(),
    )

    assert send_page.await_args.kwargs["footer"] == (
        "/流星堂 预览 <编号> · /流星堂 购买 <编号>"
    )


async def test_shop_home_rows_have_only_one_leading_badge(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    offers = (
        ShopOffer("A01", "standing_art", "art", 500),
        ShopOffer("F01", "avatar_frame", "frame", 1200),
        ShopOffer("T01", "theme", "theme", 3000),
    )
    send_page = AsyncMock()
    monkeypatch.setattr(ryuseido, "list_offers", lambda section=None: offers)
    monkeypatch.setattr(
        ryuseido,
        "season_pull_status",
        lambda user_id: SeasonPullStatus(0, 5, 400, 1, "测试季"),
    )
    monkeypatch.setattr(ryuseido, "_subtitle", lambda user_id: "盆栽 1200 盆")
    monkeypatch.setattr(ryuseido, "_send_page", send_page)

    await ryuseido._send_home(
        FinishingMatcher(),
        "user",
        object(),
    )

    rows = send_page.await_args.args[2]
    assert len(rows) == 4
    assert all(row.show_art_slot is False for row in rows)
    assert all(row.show_trailing is False for row in rows)
