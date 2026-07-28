"""The /赛季 overview card: active and upcoming states."""

from plugins.inventory.render import SeasonInfoData
from plugins.inventory.render import SeasonRewardRow
from plugins.inventory.render import season_info_page
from plugins.inventory.render import render_season_info
from plugins.render.kits import KasumiKit
from plugins.render.kits import MangaKit
from plugins.render.kits import MinimalKit


START = 1_700_000_000
END = START + 10 * 24 * 60 * 60
NOW = START + 3 * 24 * 60 * 60


def _active_data() -> SeasonInfoData:
    return SeasonInfoData(
        season_name="星之鼓动",
        state="active",
        starts_at=START,
        ends_at=END,
        now=NOW,
        points=2480,
        rank=7,
        reward_rows=(
            SeasonRewardRow(
                placement="第 1 名",
                rewards=("星星贴纸 500张", "星之鼓动冠军头像框"),
            ),
            SeasonRewardRow(
                placement="第 4–10 名",
                rewards=("星星贴纸 200张", "星之鼓动前十头像框"),
            ),
        ),
        banner_name="星之鼓动 限定卡池",
        featured_names=("户山香澄",),
    )


def _collect_text(component) -> list[str]:
    result: list[str] = []

    def visit(node) -> None:
        text = getattr(node, "text", None)
        if isinstance(text, str):
            result.append(text)
        for name in ("children", "child"):
            value = getattr(node, name, None)
            if isinstance(value, (list, tuple)):
                for child in value:
                    visit(child)
            elif value is not None:
                visit(value)

    visit(component)
    return result


def test_active_card_contains_the_player_rewards_and_banner() -> None:
    page = season_info_page(_active_data(), MinimalKit())
    text = " ".join(_collect_text(page.child))

    assert "星之鼓动" in text
    assert "星之鼓动 · 进行中" not in text
    assert "赛季状态" in text
    assert "进行中" in text
    assert "距赛季结束" in text
    assert "7 天 0 小时" in text
    assert "2,480 Pt" in text
    assert "第 7 名" in text
    assert "排名奖励" in text
    assert "星之鼓动前十头像框" in text
    assert "星之鼓动 限定卡池" in text
    assert "户山香澄" in text
    assert "/赛季排行 · /赛季趋势 · /抽卡" in text


def test_upcoming_card_is_a_preview_without_stale_standing() -> None:
    data = SeasonInfoData(
        season_name="星之鼓动",
        state="upcoming",
        starts_at=START,
        ends_at=END,
        now=START - 2 * 60 * 60,
        points=None,
        rank=None,
        reward_rows=_active_data().reward_rows,
        banner_name="星之鼓动 限定卡池",
        featured_names=("户山香澄",),
    )
    text = " ".join(_collect_text(season_info_page(data, MinimalKit()).child))

    assert "即将开始" in text
    assert "距赛季开始" in text
    assert "2 小时 0 分钟" in text
    assert "开赛后 Pt、战绩与排行榜将从零开始统计" in text
    assert "我的 Pt" not in text
    assert "当前排名" not in text


def test_season_info_renders_in_multiple_themes() -> None:
    for kit_cls in (MinimalKit, MangaKit, KasumiKit):
        image = render_season_info(_active_data(), kit_cls())
        assert image.width == 864
        assert image.height > 700
