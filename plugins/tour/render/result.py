"""Tour terminal result card."""

from __future__ import annotations

from dataclasses import dataclass

from PIL import Image

from utils import cards
from plugins.render import Fill
from plugins.render import VStack
from plugins.render import BaseKit
from plugins.render import AutoPage
from plugins.render import Component
from plugins.render import PlayerIdentity
from plugins.render.kits.bangdream import BanGDreamKit

from ..models import TourOutcome
from ..models import TourSnapshot


@dataclass(frozen=True)
class TourResultData:
    snapshot: TourSnapshot
    outcome: TourOutcome
    reward_pt: int
    balance: int
    elapsed_seconds: float
    base_reward_pt: int | None = None
    birthday_names: tuple[str, ...] = ()
    multiplier: int = 1
    task_name: str | None = None
    task_reward: int = 0
    old_level: int | None = None
    new_level: int | None = None
    level_stickers: int = 0

    @property
    def positive(self) -> bool:
        return self.outcome is TourOutcome.WIN


def _headline(data: TourResultData) -> str:
    if data.outcome is TourOutcome.WIN:
        return "巡演完成！"
    if data.outcome is TourOutcome.TIMEOUT:
        return "巡演超时"
    if data.outcome is TourOutcome.QUIT:
        return "已退出巡演"
    return "巡演失败"


def _subtitle(data: TourResultData) -> str:
    labels = {
        TourOutcome.WIN: "通关",
        TourOutcome.STAMINA: "体力耗尽",
        TourOutcome.QUIT: "主动退出",
        TourOutcome.TIMEOUT: "超时",
    }
    return f"{labels[data.outcome]} · {data.reward_pt:+d} Pt"


def _body(kit: BaseKit, data: TourResultData) -> Component:
    snapshot = data.snapshot
    base_reward = data.reward_pt if data.base_reward_pt is None else data.base_reward_pt
    sections: list[Component] = [
        cards.panel_section(
            kit,
            VStack(
                [
                    cards.stat_row(kit, "难度", snapshot.difficulty),
                    cards.stat_row(kit, "完成场数", f"{snapshot.tour_played_count}/26"),
                    cards.stat_row(kit, "耗时", f"{data.elapsed_seconds:.0f} 秒"),
                    cards.stat_row(kit, "剩余体力", f"{snapshot.stamina}/{snapshot.max_stamina}"),
                    cards.stat_row(kit, "当前余额", f"{data.balance} Pt"),
                ],
                gap=14,
                align="stretch",
            ),
        )
    ]
    if data.reward_pt:
        reward_rows: list[Component] = [
            cards.stat_row(kit, "基础奖励", f"{base_reward} Pt")
        ]
        if data.multiplier > 1 and data.birthday_names:
            reward_rows.append(
                cards.stat_row(
                    kit,
                    "生日加成",
                    f"x{data.multiplier} · {'和'.join(data.birthday_names)}",
                )
            )
        reward_rows.extend(
            [
                kit.separator(length=Fill()),
                cards.gain_rows(kit, [(f"+{data.reward_pt} Pt", "巡演奖励")]),
            ]
        )
        sections.append(cards.panel_section(kit, VStack(reward_rows, gap=14, align="stretch")))
    rewards: list[Component] = []
    if data.task_name:
        rewards.append(cards.task_progress(kit, f"每日任务 · {data.task_name}", 1, 1))
    if data.old_level is not None and data.new_level is not None:
        rewards.append(cards.level_up(kit, data.old_level, data.new_level))
    sticker_gains: list[tuple[str, str]] = []
    if data.task_reward:
        sticker_gains.append((f"+{data.task_reward} 张", "每日任务奖励"))
    if data.level_stickers:
        sticker_gains.append((f"+{data.level_stickers} 张", "升级奖励"))
    if sticker_gains:
        rewards.append(cards.gain_rows(kit, sticker_gains))
    if rewards:
        sections.append(cards.panel_section(kit, VStack(rewards, gap=14, align="stretch")))
    return VStack(sections, gap=20, align="stretch")


def result_page(
    data: TourResultData,
    kit: BaseKit | None = None,
    identity: PlayerIdentity | None = None,
) -> AutoPage:
    kit = kit or BanGDreamKit()
    sections: list[Component] = []
    if identity is not None:
        sections.append(
            cards.game_identity(
                kit,
                identity,
                width=cards.CONTENT_WIDTH,
                detail=f"{data.snapshot.difficulty} · {data.snapshot.tour_played_count}/26",
            )
        )
    sections.append(cards.headline(kit, _headline(data), positive=data.positive))
    sections.append(_body(kit, data))
    return cards.card_page(
        kit,
        title="巡演",
        subtitle=_subtitle(data),
        article_title="RESULT",
        body=VStack(sections, gap=24, align="stretch"),
        owner_name=identity.nickname if identity is not None else None,
    )


def render_result(
    data: TourResultData,
    kit: BaseKit | None = None,
    identity: PlayerIdentity | None = None,
) -> Image.Image:
    return result_page(data, kit, identity=identity).render()
