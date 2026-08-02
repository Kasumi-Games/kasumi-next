"""Interaction regressions for the player-facing 流星堂 command."""

from unittest.mock import Mock
from unittest.mock import AsyncMock

import pytest
from nonebot.exception import FinishedException
from nonebot.adapters.satori import Message

import plugins.ryuseido as ryuseido
from plugins.inventory.render import InventoryListRow
from plugins.ryuseido.service import ShopOffer
from plugins.ryuseido.service import PurchaseResult
from plugins.ryuseido.service import SeasonPullStatus


class FinishingMatcher:
    def __init__(self) -> None:
        self.calls = []

    async def finish(self, message=None, **kwargs) -> None:
        self.calls.append((message, kwargs))
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
    assert send_section.await_args.kwargs["notice"] == "已购入 A01"
    assert "余额" not in send_section.await_args.kwargs["notice"]


async def test_bonus_pull_is_a_single_step(
    monkeypatch: pytest.MonkeyPatch,
    make_satori_event,
) -> None:
    status = SeasonPullStatus(0, 5, 400, 1, "测试季")
    send_home = AsyncMock(side_effect=FinishedException())
    send_bonus_pull = AsyncMock(side_effect=FinishedException())
    monkeypatch.setattr(ryuseido, "season_pull_status", lambda user_id: status)
    monkeypatch.setattr(ryuseido, "_send_home", send_home)
    monkeypatch.setattr(ryuseido, "_send_bonus_pull", send_bonus_pull)

    with pytest.raises(FinishedException):
        await ryuseido.handle_shop(
            FinishingMatcher(),
            make_satori_event("/流星堂 加抽"),
            Message("加抽"),
        )

    send_bonus_pull.assert_awaited_once()
    send_home.assert_not_awaited()


async def test_bonus_pull_error_is_returned_without_shop_name_prefix(
    monkeypatch: pytest.MonkeyPatch,
    make_satori_event,
) -> None:
    matcher = FinishingMatcher()
    status = SeasonPullStatus(0, 5, 400, 1, "测试季")
    monkeypatch.setattr(ryuseido, "season_pull_status", lambda user_id: status)
    monkeypatch.setattr(ryuseido, "_send_home", AsyncMock())
    monkeypatch.setattr(
        ryuseido,
        "_send_bonus_pull",
        AsyncMock(side_effect=ValueError("盆栽不足，需要 400 盆")),
    )

    with pytest.raises(FinishedException):
        await ryuseido.handle_shop(
            matcher,
            make_satori_event("/流星堂 加抽"),
            Message("加抽"),
        )

    reply = str(matcher.calls[0][0])
    assert "盆栽不足，需要 400 盆" in reply
    assert "流星堂：" not in reply


async def test_usage_error_has_no_redundant_shop_name_prefix(
    make_satori_event,
) -> None:
    matcher = FinishingMatcher()

    with pytest.raises(FinishedException):
        await ryuseido.handle_shop(
            matcher,
            make_satori_event("/流星堂 购买"),
            Message("购买"),
        )

    reply = str(matcher.calls[0][0])
    assert reply.startswith("用法：/流星堂 购买")
    assert "流星堂：" not in reply


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
    assert send_page.await_args.kwargs["title"] == "流星堂"
    assert send_page.await_args.kwargs["subtitle"] == "主题"
    assert send_page.await_args.kwargs["panel_footer"] == "第 1/1 页"


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
    assert send_page.await_args.kwargs["title"] == "流星堂"
    assert send_page.await_args.kwargs["subtitle"] == "旧藏流转"
    assert "盆栽" not in send_page.await_args.kwargs["subtitle"]
